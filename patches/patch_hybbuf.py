#!/usr/bin/env python3
"""
Geteilter hybris-Nativpuffer als Renderziel.

Bisher legt der Simulator den Puffer an: entweder vom Kernel-Heap
(nur unter Zink brauchbar, weil hybris-EGL kein
EGL_EXT_image_dma_buf_import kennt) oder gar nicht, dann Readback.

Neu ist der umgekehrte Weg: der Presenter legt ueber
EGL_HYBRIS_native_buffer2 einen Puffer an, serialisiert ihn und haelt
die Beschreibung auf einem Socket bereit. Der Simulator holt sie sich,
stellt den Puffer mit eglHybrisCreateRemoteBuffer wieder her und haengt
ihn als FBO-Farbattachment ein.

Der Vorteil: es funktioniert unter allen Backends, und der Presenter
kann denselben Puffer als GL-Textur benutzen statt ihn zu kopieren.

Die bisherigen Wege bleiben als Rueckfallebene erhalten.
"""

import sys

P = '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5/src/osgViewer/GraphicsWindowEGL.cpp'

METHOD = r'''
    /* --- Geteilter hybris-Nativpuffer ----------------------------
     *
     * Der Presenter legt den Puffer an und haelt seine Beschreibung
     * auf einem Unix-Socket bereit: drei Ints (stride, Anzahl Ints,
     * Anzahl Deskriptoren), dann die Ints, die Deskriptoren als
     * Beipack. Wir stellen den Puffer daraus wieder her.
     */
    bool tryHybrisBuffer(int w, int h)
    {
        const char* sp = ::getenv("FGFS_HYB_SOCKET");
        if (!sp || !*sp) return false;

        typedef unsigned (*PFN_Remote)(EGLint, EGLint, EGLint, EGLint,
                                       EGLint, int, int*, int, int*,
                                       void**);
        typedef void* (*PFN_Image)(EGLDisplay, EGLContext, EGLenum,
                                   void*, const EGLint*);
        typedef void  (*PFN_Target)(unsigned, void*);

        PFN_Remote Remote = (PFN_Remote)
            eglGetProcAddress("eglHybrisCreateRemoteBuffer");
        PFN_Image  Image  = (PFN_Image)
            eglGetProcAddress("eglCreateImageKHR");
        PFN_Target Target = (PFN_Target)
            eglGetProcAddress("glEGLImageTargetTexture2DOES");
        if (!Remote || !Image || !Target) {
            OSG_WARN << "GraphicsWindowEGL: hybris-Puffer nicht "
                        "verfuegbar" << std::endl;
            return false;
        }

        int s = ::socket(AF_UNIX, SOCK_STREAM, 0);
        if (s < 0) return false;

        struct sockaddr_un sa;
        memset(&sa, 0, sizeof sa);
        sa.sun_family = AF_UNIX;
        ::strncpy(sa.sun_path, sp, sizeof(sa.sun_path) - 1);
        if (::connect(s, (struct sockaddr*)&sa, sizeof sa) < 0) {
            OSG_WARN << "GraphicsWindowEGL: kein Presenter auf " << sp
                     << std::endl;
            ::close(s);
            return false;
        }

        int head[3] = { 0, 0, 0 };
        int ints[128];
        int fds[16];
        char cbuf[CMSG_SPACE(16 * sizeof(int))];
        struct iovec iov[2];
        struct msghdr msg;

        iov[0].iov_base = head;  iov[0].iov_len = sizeof head;
        iov[1].iov_base = ints;  iov[1].iov_len = sizeof ints;
        memset(&msg, 0, sizeof msg);
        msg.msg_iov = iov;  msg.msg_iovlen = 2;
        msg.msg_control = cbuf;
        msg.msg_controllen = sizeof cbuf;

        if (::recvmsg(s, &msg, 0) <= 0) { ::close(s); return false; }

        struct cmsghdr* cm = CMSG_FIRSTHDR(&msg);
        if (!cm || cm->cmsg_type != SCM_RIGHTS) { ::close(s); return false; }

        const int stride = head[0];
        const int nints  = head[1];
        const int nfds   = head[2];
        if (nints <= 0 || nints > 128 || nfds <= 0 || nfds > 16) {
            ::close(s); return false;
        }
        memcpy(fds, CMSG_DATA(cm), nfds * sizeof(int));

        /* Android-Gralloc: RGBA8888, von GPU beschreibbar, von der
           CPU lesbar (der Presenter darf notfalls direkt hineinsehen). */
        const EGLint usage = 0x00000100 | 0x00000200
                           | 0x00000003 | 0x00000030;

        void* buf = nullptr;
        if (!Remote(w, h, usage, 1 /* RGBA8888 */, stride,
                    nints, ints, nfds, fds, &buf) || !buf) {
            OSG_WARN << "GraphicsWindowEGL: CreateRemoteBuffer "
                        "fehlgeschlagen" << std::endl;
            ::close(s);
            return false;
        }

        void* img = Image(_display, EGL_NO_CONTEXT,
                          0x3140 /* EGL_NATIVE_BUFFER_HYBRIS */,
                          buf, nullptr);
        if (!img) {
            OSG_WARN << "GraphicsWindowEGL: EGLImage aus hybris-Puffer "
                        "fehlgeschlagen 0x" << std::hex << eglGetError()
                     << std::dec << std::endl;
            ::close(s);
            return false;
        }

        Target(GL_TEXTURE_2D, img);

        _hybSocket = s;          /* offen halten, sonst faellt der
                                    Puffer beim Presenter weg */
        _hybShared = true;
        _hybStride = stride;
        OSG_WARN << "GraphicsWindowEGL: geteilter hybris-Puffer, "
                 << w << "x" << h << ", stride=" << stride << std::endl;
        return true;
    }
'''


def main():
    try:
        s = open(P, encoding='utf-8', errors='surrogateescape').read()
    except FileNotFoundError:
        print("nicht gefunden - im Container ausfuehren:", P)
        return 1

    if '_hybShared' in s:
        print("bereits gepatcht")
        return 0

    # 1. Reihenfolge: hybris zuerst, dann dma-heap
    old1 = '''        /* Erst den geteilten Weg versuchen: Puffer vom Kernel-Heap,
           als EGLImage importiert. Klappt das, rendert die GPU direkt
           in Speicher, den der Presenter ohne Kopie liest. */
        _dmabufFd = allocDmaHeap(size_t(w) * size_t(h) * 4u);
        bool shared = false;

        if (_dmabufFd >= 0) {'''
    new1 = '''        bool shared = false;

        /* Zuerst der Weg ueber einen Puffer, den der Presenter
           bereitstellt. Der funktioniert unter allen Backends, weil er
           ohne EGL_EXT_image_dma_buf_import auskommt. */
        if (tryHybrisBuffer(w, h)) shared = true;

        /* Sonst ein Puffer vom Kernel-Heap. Den kann nur Mesa
           importieren, also nur unter Zink. */
        if (!shared) _dmabufFd = allocDmaHeap(size_t(w) * size_t(h) * 4u);

        if (!shared && _dmabufFd >= 0) {'''
    if old1 not in s:
        print("FEHLER: Allokationsblock nicht gefunden")
        return 1
    s = s.replace(old1, new1, 1)

    # 2. Publish: beim geteilten Puffer nur melden
    old2 = '''        /* Zero-Copy: die GPU hat bereits in den geteilten Puffer
           gerendert. Es bleibt nur, den Frame als fertig zu melden. */
        if (_dmabufFd >= 0) {'''
    new2 = '''        /* Der Presenter besitzt den Puffer und hat ihn selbst als
           Textur - wir melden nur, dass der Frame fertig ist. */
        if (_hybShared) {
            glFlush();
            g_shm.publishDmabuf(getpid(), 0, uint32_t(_hybStride) * 4u,
                                0x48594252 /* HYBR */);
            ++_frameCount;
            return;
        }

        /* Zero-Copy: die GPU hat bereits in den geteilten Puffer
           gerendert. Es bleibt nur, den Frame als fertig zu melden. */
        if (_dmabufFd >= 0) {'''
    if old2 not in s:
        print("FEHLER: Publish-Block nicht gefunden")
        return 1
    s = s.replace(old2, new2, 1)

    # 3. Methode einfuegen
    old3 = '    void publishToShm()'
    if old3 not in s:
        print("FEHLER: publishToShm nicht gefunden")
        return 1
    s = s.replace(old3, METHOD + '\n' + old3, 1)

    # 4. Member
    old4 = '    int _dmabufFd = -1;'
    new4 = ('    int  _dmabufFd = -1;\n'
            '    bool _hybShared = false;\n'
            '    int  _hybSocket = -1;\n'
            '    int  _hybStride = 0;')
    if old4 not in s:
        print("FEHLER: _dmabufFd-Member nicht gefunden")
        return 1
    s = s.replace(old4, new4, 1)

    open(P, 'w', encoding='utf-8', errors='surrogateescape').write(s)
    print("gepatcht: hybris-Puffer als Renderziel")
    print("Aktiv, sobald FGFS_HYB_SOCKET gesetzt ist.")
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""
Fence statt glFinish.

glFinish blockiert den Simulator, bis saemtliche GPU-Arbeit fertig
ist - kein Ueberlappen zwischen Frames mehr. Bei der c172p kostet
das rund sieben Achtel der Bildrate.

Mit EGL_ANDROID_native_fence_sync erzeugt der Simulator stattdessen
ein Fence-Objekt und exportiert dessen Deskriptor. Der wandert ueber
denselben Unix-Socket wie der dmabuf, und der Presenter wartet
darauf - nicht der Simulator. Die Renderpipeline bleibt gefuellt.

Der Fence-Deskriptor wechselt bei jedem Frame, deshalb wird er nicht
einmalig uebergeben wie der dmabuf, sondern bei jeder Anfrage neu.
Der Presenter fragt nur, wenn er tatsaechlich einen neuen Frame
abholt.
"""

import sys

GW = '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5/src/osgViewer/GraphicsWindowEGL.cpp'

# --- glFinish durch Fence ersetzen ---------------------------------
FIN_OLD = '''            if (!g_shm.ready() && !g_shm.open(w, h)) return;
            /* Ohne Synchronisation sieht der Presenter halb
               aufgeloeste Kacheln. glFinish ist grob, aber wirksam;
               feiner ginge es mit EGL_ANDROID_native_fence_sync. */
            glFinish();'''

FIN_NEW = '''            if (!g_shm.ready() && !g_shm.open(w, h)) return;

            /* Statt glFinish - das den Simulator bis zur Fertigstellung
               saemtlicher GPU-Arbeit anhaelt - ein Fence: die Pipeline
               laeuft weiter, und der Presenter wartet selbst darauf,
               bis der Frame vollstaendig ist. */
            if (_useFence) {
                if (!_pCreateSync) {
                    _pCreateSync = (PFN_CreateSyncKHR)
                        eglGetProcAddress("eglCreateSyncKHR");
                    _pDupFence = (PFN_DupNativeFence)
                        eglGetProcAddress("eglDupNativeFenceFDANDROID");
                    _pDestroySync = (PFN_DestroySyncKHR)
                        eglGetProcAddress("eglDestroySyncKHR");
                    if (!_pCreateSync || !_pDupFence || !_pDestroySync) {
                        OSG_WARN << "GraphicsWindowEGL: kein "
                                    "native_fence_sync, nutze glFinish"
                                 << std::endl;
                        _useFence = false;
                    }
                }
            }

            if (_useFence) {
                EGLSyncKHR sync = _pCreateSync(
                    _display, 0x3144 /* EGL_SYNC_NATIVE_FENCE_ANDROID */,
                    nullptr);
                glFlush();                 /* Fence in die Queue schieben */
                if (sync != EGL_NO_SYNC_KHR) {
                    const int ffd = _pDupFence(_display, sync);
                    _pDestroySync(_display, sync);
                    g_fdServer.setFence(ffd);   /* uebernimmt den fd */
                } else {
                    glFinish();               /* Notnagel */
                }
            } else {
                glFinish();
            }'''

# --- FdServer: Fence mitliefern ------------------------------------
SRV_OLD = '''    void sendFd(int conn)
    {
        char dummy = 'F';'''

SRV_NEW = '''    /* Der Fence wechselt pro Frame. Der jeweils juengste wird
       vorgehalten; der vorige wird geschlossen. */
    void setFence(int fd)
    {
        pthread_mutex_lock(&fenceLock);
        if (fenceFd >= 0) ::close(fenceFd);
        fenceFd = fd;
        pthread_mutex_unlock(&fenceLock);
    }

    int takeFence()
    {
        pthread_mutex_lock(&fenceLock);
        const int fd = fenceFd;
        fenceFd = -1;
        pthread_mutex_unlock(&fenceLock);
        return fd;
    }

    void sendFd(int conn)
    {
        char dummy = 'F';'''

# zwei Deskriptoren statt einem senden
SEND_OLD = '''        char cbuf[CMSG_SPACE(sizeof(int))];
        memset(cbuf, 0, sizeof cbuf);

        struct msghdr msg;
        memset(&msg, 0, sizeof msg);
        msg.msg_iov = &iov;
        msg.msg_iovlen = 1;
        msg.msg_control = cbuf;
        msg.msg_controllen = sizeof cbuf;

        struct cmsghdr* cm = CMSG_FIRSTHDR(&msg);
        cm->cmsg_level = SOL_SOCKET;
        cm->cmsg_type = SCM_RIGHTS;
        cm->cmsg_len = CMSG_LEN(sizeof(int));
        memcpy(CMSG_DATA(cm), &payloadFd, sizeof(int));

        if (::sendmsg(conn, &msg, 0) < 0)
            OSG_WARN << "FdServer: sendmsg fehlgeschlagen" << std::endl;
    }'''

SEND_NEW = '''        /* Erste Anfrage bekommt den dmabuf, jede weitere den
           aktuellen Fence. Der Presenter unterscheidet am Byte. */
        int fence = takeFence();
        int toSend = payloadFd;
        if (handedOutBuffer && fence >= 0) {
            toSend = fence;
            dummy = 'S';                /* Sync statt Buffer */
        } else {
            handedOutBuffer = true;
        }

        char cbuf[CMSG_SPACE(sizeof(int))];
        memset(cbuf, 0, sizeof cbuf);

        struct msghdr msg;
        memset(&msg, 0, sizeof msg);
        msg.msg_iov = &iov;
        msg.msg_iovlen = 1;
        msg.msg_control = cbuf;
        msg.msg_controllen = sizeof cbuf;

        struct cmsghdr* cm = CMSG_FIRSTHDR(&msg);
        cm->cmsg_level = SOL_SOCKET;
        cm->cmsg_type = SCM_RIGHTS;
        cm->cmsg_len = CMSG_LEN(sizeof(int));
        memcpy(CMSG_DATA(cm), &toSend, sizeof(int));

        if (::sendmsg(conn, &msg, 0) < 0)
            OSG_WARN << "FdServer: sendmsg fehlgeschlagen" << std::endl;

        if (toSend == fence) ::close(fence);
    }'''

MEMSRV_OLD = '''    int listenFd = -1;
    int payloadFd = -1;'''
MEMSRV_NEW = '''    int listenFd = -1;
    int payloadFd = -1;
    int fenceFd = -1;
    bool handedOutBuffer = false;
    pthread_mutex_t fenceLock = PTHREAD_MUTEX_INITIALIZER;'''

# --- Typen und Member in GraphicsWindowEGL -------------------------
TYPE_OLD = '''    unsigned _texColor = 0;'''
TYPE_NEW = '''    unsigned _texColor = 0;

    typedef EGLSyncKHR (*PFN_CreateSyncKHR)(EGLDisplay, EGLenum, const EGLint*);
    typedef EGLint     (*PFN_DupNativeFence)(EGLDisplay, EGLSyncKHR);
    typedef EGLBoolean (*PFN_DestroySyncKHR)(EGLDisplay, EGLSyncKHR);

    PFN_CreateSyncKHR  _pCreateSync = nullptr;
    PFN_DupNativeFence _pDupFence = nullptr;
    PFN_DestroySyncKHR _pDestroySync = nullptr;
    bool _useFence = true;'''


def main():
    try:
        s = open(GW).read()
    except FileNotFoundError:
        print("nicht gefunden - im Container ausfuehren:", GW)
        return 1

    if '_useFence' in s:
        print("bereits gepatcht")
        return 0

    for old, new, label in (
        (MEMSRV_OLD, MEMSRV_NEW, "FdServer-Member"),
        (SRV_OLD,    SRV_NEW,    "setFence/takeFence"),
        (SEND_OLD,   SEND_NEW,   "sendFd mit Fence"),
        (TYPE_OLD,   TYPE_NEW,   "Fence-Typen"),
        (FIN_OLD,    FIN_NEW,    "Fence statt glFinish"),
    ):
        if old not in s:
            print("FEHLER: Muster nicht gefunden:", label)
            return 1
        s = s.replace(old, new, 1)
        print("gepatcht:", label)

    open(GW, 'w').write(s)
    print("\nfertig - OSG neu bauen")
    print("Abschalten zur Laufzeit ist nicht vorgesehen; bei fehlender")
    print("Extension faellt der Code selbst auf glFinish zurueck.")
    return 0


if __name__ == '__main__':
    sys.exit(main())

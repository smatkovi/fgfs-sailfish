#!/usr/bin/env python3
"""
Probe: laesst sich die FBO-Textur als dmabuf exportieren?

Gestern scheiterte eglExportDMABUFImageMESA an einer frei angelegten
Textur - Zinks swrast-Einstieg setzt drm_fd auf -1 und kann keine
Modifier aushandeln. Ob das fuer eine FBO-Farbtextur genauso gilt,
ist offen: der Weg durch Zink ist ein anderer.

Dieser Patch versucht den Export einmalig beim Realize und schreibt
das Ergebnis ins Log. Er aendert sonst nichts - der Readback laeuft
unveraendert weiter.
"""

import sys

P = '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5/src/osgViewer/GraphicsWindowEGL.cpp'

PROBE = '''
        /* ---- Probe: dmabuf-Export der Farbtextur ---------------- */
        {
            typedef EGLImageKHR (*PFN_CreateImage)(EGLDisplay, EGLContext,
                                                   EGLenum, EGLClientBuffer,
                                                   const EGLint*);
            typedef EGLBoolean (*PFN_Query)(EGLDisplay, EGLImageKHR,
                                            int*, int*, EGLuint64KHR*);
            typedef EGLBoolean (*PFN_Export)(EGLDisplay, EGLImageKHR,
                                             int*, EGLint*, EGLint*);

            PFN_CreateImage CreateImg =
                (PFN_CreateImage)eglGetProcAddress("eglCreateImageKHR");
            PFN_Query Query =
                (PFN_Query)eglGetProcAddress("eglExportDMABUFImageQueryMESA");
            PFN_Export Export =
                (PFN_Export)eglGetProcAddress("eglExportDMABUFImageMESA");

            if (!CreateImg || !Query || !Export) {
                OSG_WARN << "DMABUF-Probe: Einsprungpunkte fehlen "
                         << "(CreateImage=" << (void*)CreateImg
                         << " Query=" << (void*)Query
                         << " Export=" << (void*)Export << ")" << std::endl;
            } else {
                EGLImageKHR img = CreateImg(
                    _display, _context, 0x30B1 /* EGL_GL_TEXTURE_2D_KHR */,
                    (EGLClientBuffer)(uintptr_t)_texColor, nullptr);

                if (img == EGL_NO_IMAGE_KHR) {
                    OSG_WARN << "DMABUF-Probe: eglCreateImageKHR fehlgeschlagen 0x"
                             << std::hex << eglGetError() << std::dec << std::endl;
                } else {
                    int fourcc = 0, planes = 0;
                    EGLuint64KHR mod = 0;
                    if (!Query(_display, img, &fourcc, &planes, &mod)) {
                        OSG_WARN << "DMABUF-Probe: Query fehlgeschlagen 0x"
                                 << std::hex << eglGetError() << std::dec
                                 << std::endl;
                    } else {
                        int fds[4] = { -1, -1, -1, -1 };
                        EGLint strides[4] = {0}, offsets[4] = {0};
                        const EGLBoolean okExp =
                            Export(_display, img, fds, strides, offsets);

                        char cc[5] = {
                            char(fourcc & 0xff), char((fourcc >> 8) & 0xff),
                            char((fourcc >> 16) & 0xff),
                            char((fourcc >> 24) & 0xff), 0 };

                        OSG_WARN << "DMABUF-Probe: export=" << int(okExp)
                                 << " fourcc=" << cc
                                 << " planes=" << planes
                                 << " modifier=0x" << std::hex << (unsigned long long)mod
                                 << std::dec
                                 << " fd=" << fds[0]
                                 << " stride=" << strides[0]
                                 << " offset=" << offsets[0]
                                 << std::endl;

                        /* Ist der FD echt? /proc/self/fd muss ihn kennen. */
                        if (fds[0] >= 0) {
                            char lp[64], tgt[256];
                            snprintf(lp, sizeof lp, "/proc/self/fd/%d", fds[0]);
                            ssize_t k = readlink(lp, tgt, sizeof tgt - 1);
                            if (k > 0) {
                                tgt[k] = 0;
                                OSG_WARN << "DMABUF-Probe: fd " << fds[0]
                                         << " -> " << tgt << "  PID "
                                         << getpid() << std::endl;
                            } else {
                                OSG_WARN << "DMABUF-Probe: fd " << fds[0]
                                         << " ist ungueltig" << std::endl;
                            }
                        }
                    }
                }
            }
        }
        /* ---- Ende Probe ---------------------------------------- */
'''

ANCHOR = '''        glViewport(0, 0, w, h);
        setDefaultFboId(_fbo);'''


def main():
    try:
        s = open(P).read()
    except FileNotFoundError:
        print("nicht gefunden - im Container ausfuehren:", P)
        return 1

    if 'DMABUF-Probe' in s:
        print("bereits gepatcht")
        return 0

    if ANCHOR not in s:
        print("FEHLER: Anker nicht gefunden")
        return 1

    s = s.replace(ANCHOR, PROBE + ANCHOR, 1)
    open(P, 'w').write(s)
    print("Probe eingebaut - OSG neu bauen")
    return 0


if __name__ == '__main__':
    sys.exit(main())

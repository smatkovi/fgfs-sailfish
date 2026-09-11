#!/usr/bin/env python3
"""
Baut den Frame-Readback in GraphicsWindowEGL ein.

Stufe 1 (dieses Skript): jeder N-te Frame wird als PPM nach
/tmp/fgfs-frame.ppm geschrieben. Damit laesst sich pruefen, ob
FlightGear ueberhaupt ein Bild erzeugt.

Steuerung ueber Umgebungsvariablen:
  FGFS_DUMP_EVERY   = 0 aus (default), sonst jeder N-te Frame
  FGFS_DUMP_PATH    = Zielpfad (default /tmp/fgfs-frame.ppm)
"""

import sys

P = '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5/src/osgViewer/GraphicsWindowEGL.cpp'

INCLUDES_OLD = '''#include <cstdlib>
#include <cstring>'''

INCLUDES_NEW = '''#include <cstdlib>
#include <cstring>
#include <cstdio>
#include <vector>

/* GL-Konstanten und -Prototypen ohne GL/gl.h, damit wir nicht gegen
   glvnd-Header linken muessen - die Symbole kommen aus libOpenGL. */
#ifndef GL_RGBA
#define GL_RGBA           0x1908
#define GL_UNSIGNED_BYTE  0x1401
#define GL_PACK_ALIGNMENT 0x0D05
#endif
extern "C" {
    void glReadPixels(int, int, int, int, unsigned, unsigned, void*);
    void glPixelStorei(unsigned, int);
    void glFinish(void);
}'''

SWAP_OLD = '''    void swapBuffersImplementation() override
    {
        /* HIER kommt spaeter der Readback:
         *   glReadPixels in PBO (pingpong) -> memcpy in shm -> eventfd
         * Solange nichts praesentiert wird, ist eglSwapBuffers auf einem
         * Pbuffer ein No-op bzw. schlaegt harmlos fehl.
         */
        if (_surface != EGL_NO_SURFACE) {
            eglSwapBuffers(_display, _surface);
        }
    }'''

SWAP_NEW = '''    void swapBuffersImplementation() override
    {
        if (_surface != EGL_NO_SURFACE) {
            eglSwapBuffers(_display, _surface);
        }
        dumpFrameIfRequested();
    }

    void dumpFrameIfRequested()
    {
        static int every = -1;
        static const char* path = nullptr;
        if (every < 0) {
            const char* e = ::getenv("FGFS_DUMP_EVERY");
            every = (e && *e) ? ::atoi(e) : 0;
            path  = ::getenv("FGFS_DUMP_PATH");
            if (!path || !*path) path = "/tmp/fgfs-frame.ppm";
            if (every > 0) {
                OSG_NOTICE << "GraphicsWindowEGL: Frame-Dump alle " << every
                           << " Frames nach " << path << std::endl;
            }
        }
        if (every <= 0) return;

        if ((++_frameCount % every) != 0) return;

        const int w = _traits.valid() ? _traits->width  : 960;
        const int h = _traits.valid() ? _traits->height : 540;

        if (_pixels.size() != size_t(w) * size_t(h) * 4u) {
            _pixels.resize(size_t(w) * size_t(h) * 4u);
        }

        glFinish();
        glPixelStorei(GL_PACK_ALIGNMENT, 1);
        glReadPixels(0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, _pixels.data());

        /* PPM ist verlustfrei und braucht keine Bibliothek.
           Erst in eine Temp-Datei, dann umbenennen - so sieht ein
           mitlesender Prozess nie ein halbes Bild. */
        std::string tmp = std::string(path) + ".tmp";
        FILE* f = ::fopen(tmp.c_str(), "wb");
        if (!f) return;

        ::fprintf(f, "P6\\n%d %d\\n255\\n", w, h);
        /* GL liefert von unten nach oben, PPM will von oben nach unten */
        for (int y = h - 1; y >= 0; --y) {
            const unsigned char* row = _pixels.data() + size_t(y) * size_t(w) * 4u;
            for (int x = 0; x < w; ++x) {
                ::fputc(row[x * 4 + 0], f);
                ::fputc(row[x * 4 + 1], f);
                ::fputc(row[x * 4 + 2], f);
            }
        }
        ::fclose(f);
        ::rename(tmp.c_str(), path);
    }'''

MEMBERS_OLD = '''    EGLDisplay _display;
    EGLSurface _surface;'''

MEMBERS_NEW = '''    unsigned long _frameCount = 0;
    std::vector<unsigned char> _pixels;

    EGLDisplay _display;
    EGLSurface _surface;'''


def main():
    try:
        s = open(P).read()
    except FileNotFoundError:
        print("Datei nicht gefunden:", P)
        print("Laeuft dieses Skript im Container?")
        return 1

    for old, new, label in (
        (INCLUDES_OLD, INCLUDES_NEW, "Includes"),
        (SWAP_OLD,     SWAP_NEW,     "swapBuffersImplementation"),
        (MEMBERS_OLD,  MEMBERS_NEW,  "Member"),
    ):
        if old not in s:
            print("FEHLER: Muster nicht gefunden:", label)
            return 1
        if new.split('\n')[0] in s and label == "Member":
            print("bereits gepatcht:", label)
            continue
        s = s.replace(old, new, 1)
        print("gepatcht:", label)

    open(P, 'w').write(s)
    print("fertig")
    return 0


if __name__ == '__main__':
    sys.exit(main())

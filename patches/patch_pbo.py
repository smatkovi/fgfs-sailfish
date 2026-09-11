#!/usr/bin/env python3
"""
Asynchroner Readback mit Pixel-Buffer-Objects.

Bisher: glReadPixels schreibt direkt in den Shared Memory und
blockiert, bis die GPU fertig ist. Auf einem Tile-Based Renderer
erzwingt das einen Flush der kompletten Tile-Pipeline.

Neu: zwei PBOs im Wechsel. In Frame N wird der Transfer in PBO A
angestossen (kehrt sofort zurueck), gleichzeitig wird PBO B aus
Frame N-1 gemappt und in den Shared Memory kopiert. Die GPU laeuft
weiter, waehrend die CPU die Daten des Vorframes abholt.

Kostet einen Frame Latenz, was bei einem Flugsimulator auf dem
Telefon nicht ins Gewicht faellt.
"""

import sys

P = '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5/src/osgViewer/GraphicsWindowEGL.cpp'

# --- zusaetzliche GL-Konstanten und Entrypoints ---------------------
DECL_OLD = '''#ifndef GL_FRAMEBUFFER
#define GL_FRAMEBUFFER              0x8D40'''
DECL_NEW = '''#ifndef GL_PIXEL_PACK_BUFFER
#define GL_PIXEL_PACK_BUFFER        0x88EB
#define GL_STREAM_READ              0x88E1
#define GL_READ_ONLY                0x88B8
#endif

#ifndef GL_FRAMEBUFFER
#define GL_FRAMEBUFFER              0x8D40'''

FN_OLD = '''    PFN_v_icp   p_DeleteRenderbuffers = nullptr;'''
FN_NEW = '''    PFN_v_icp   p_DeleteRenderbuffers = nullptr;

    typedef void  (*PFN_v_ip2)(int, unsigned*);
    typedef void  (*PFN_v_uu2)(unsigned, unsigned);
    typedef void  (*PFN_v_uxpu)(unsigned, long, const void*, unsigned);
    typedef void* (*PFN_p_uu)(unsigned, unsigned);
    typedef unsigned char (*PFN_b_u)(unsigned);

    PFN_v_ip2   p_GenBuffers = nullptr;
    PFN_v_uu2   p_BindBuffer = nullptr;
    PFN_v_uxpu  p_BufferData = nullptr;
    PFN_p_uu    p_MapBuffer = nullptr;
    PFN_b_u     p_UnmapBuffer = nullptr;
    PFN_v_icp   p_DeleteBuffers = nullptr;

    bool loadPboEntryPoints()
    {
        if (p_GenBuffers) return true;
        p_GenBuffers    = (PFN_v_ip2) eglGetProcAddress("glGenBuffers");
        p_BindBuffer    = (PFN_v_uu2) eglGetProcAddress("glBindBuffer");
        p_BufferData    = (PFN_v_uxpu)eglGetProcAddress("glBufferData");
        p_MapBuffer     = (PFN_p_uu)  eglGetProcAddress("glMapBuffer");
        p_UnmapBuffer   = (PFN_b_u)   eglGetProcAddress("glUnmapBuffer");
        p_DeleteBuffers = (PFN_v_icp) eglGetProcAddress("glDeleteBuffers");
        return p_GenBuffers && p_BindBuffer && p_BufferData
            && p_MapBuffer && p_UnmapBuffer;
    }'''

# --- publishToShm auf PBO umstellen ---------------------------------
PUB_OLD = '''        const int slot = int(_frameCount & 1u);
        ++_frameCount;

        glPixelStorei(GL_PACK_ALIGNMENT, 1);

        g_shm.beginWrite(slot);
        glReadPixels(0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE,
                     g_shm.slotPtr(slot));
        g_shm.endWrite(slot);
    }'''

PUB_NEW = '''        const size_t bytes = size_t(w) * size_t(h) * 4u;

        /* PBOs beim ersten Aufruf anlegen */
        if (!_pbo[0]) {
            if (!loadPboEntryPoints()) {
                OSG_WARN << "GraphicsWindowEGL: keine PBO-Unterstuetzung, "
                            "falle auf blockierenden Readback zurueck"
                         << std::endl;
                _pboUnavailable = true;
            } else {
                p_GenBuffers(2, _pbo);
                for (int i = 0; i < 2; ++i) {
                    p_BindBuffer(GL_PIXEL_PACK_BUFFER, _pbo[i]);
                    p_BufferData(GL_PIXEL_PACK_BUFFER, long(bytes),
                                 nullptr, GL_STREAM_READ);
                }
                p_BindBuffer(GL_PIXEL_PACK_BUFFER, 0);
                OSG_NOTICE << "GraphicsWindowEGL: PBO-Readback aktiv ("
                           << (2 * bytes / 1024) << " KiB)" << std::endl;
            }
        }

        glPixelStorei(GL_PACK_ALIGNMENT, 1);

        if (_pboUnavailable) {
            const int slot = int(_frameCount & 1u);
            ++_frameCount;
            g_shm.beginWrite(slot);
            glReadPixels(0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE,
                         g_shm.slotPtr(slot));
            g_shm.endWrite(slot);
            return;
        }

        const int cur  = int(_frameCount & 1u);
        const int prev = 1 - cur;

        /* Transfer fuer diesen Frame anstossen - kehrt sofort zurueck,
           weil das Ziel ein Puffer im GPU-Speicher ist. */
        p_BindBuffer(GL_PIXEL_PACK_BUFFER, _pbo[cur]);
        glReadPixels(0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);

        /* Ergebnis des Vorframes abholen. Erst ab dem zweiten Frame,
           vorher enthaelt der andere Puffer nichts. */
        if (_frameCount > 0) {
            p_BindBuffer(GL_PIXEL_PACK_BUFFER, _pbo[prev]);
            void* src = p_MapBuffer(GL_PIXEL_PACK_BUFFER, GL_READ_ONLY);
            if (src) {
                const int slot = int(_frameCount & 1u);
                g_shm.beginWrite(slot);
                memcpy(g_shm.slotPtr(slot), src, bytes);
                g_shm.endWrite(slot);
                p_UnmapBuffer(GL_PIXEL_PACK_BUFFER);
            }
        }

        p_BindBuffer(GL_PIXEL_PACK_BUFFER, 0);
        ++_frameCount;
    }'''

# --- Member ----------------------------------------------------------
MEM_OLD = '''    unsigned _fbo = 0;
    unsigned _rbColor = 0;
    unsigned _rbDepth = 0;'''
MEM_NEW = '''    unsigned _fbo = 0;
    unsigned _rbColor = 0;
    unsigned _rbDepth = 0;
    unsigned _pbo[2] = { 0, 0 };
    bool _pboUnavailable = false;'''

# --- Aufraeumen ------------------------------------------------------
CLOSE_OLD = '''            if (_fbo && p_DeleteFramebuffers) {'''
CLOSE_NEW = '''            if (_pbo[0] && p_DeleteBuffers) {
                eglMakeCurrent(_display, _surface, _surface, _context);
                p_DeleteBuffers(2, _pbo);
                _pbo[0] = _pbo[1] = 0;
            }
            if (_fbo && p_DeleteFramebuffers) {'''


def main():
    try:
        s = open(P).read()
    except FileNotFoundError:
        print("nicht gefunden - im Container ausfuehren:", P)
        return 1

    if '_pboUnavailable' in s:
        print("bereits gepatcht")
        return 0

    for old, new, label in (
        (DECL_OLD,  DECL_NEW,  "GL-Konstanten"),
        (FN_OLD,    FN_NEW,    "PBO-Entrypoints"),
        (MEM_OLD,   MEM_NEW,   "Member"),
        (PUB_OLD,   PUB_NEW,   "publishToShm auf PBO"),
    ):
        if old not in s:
            print("FEHLER: Muster nicht gefunden:", label)
            return 1
        s = s.replace(old, new, 1)
        print("gepatcht:", label)

    open(P, 'w').write(s)
    print("fertig - OSG neu bauen")
    return 0


if __name__ == '__main__':
    sys.exit(main())

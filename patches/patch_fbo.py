#!/usr/bin/env python3
"""
Legt in GraphicsWindowEGL ein FBO an und meldet es OSG als
Default-Framebuffer (GraphicsContext::setDefaultFboId).

Noetig, weil der EGL-Kontext surfaceless ist und damit keinen
Default-Framebuffer 0 besitzt - ohne FBO rendert OSG ins Nichts
und glReadPixels liefert nur Schwarz.
"""

import sys

P = '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5/src/osgViewer/GraphicsWindowEGL.cpp'

GL_DECLS_OLD = '''extern "C" {
    void glReadPixels(int, int, int, int, unsigned, unsigned, void*);
    void glPixelStorei(unsigned, int);
    void glFinish(void);
}'''

GL_DECLS_NEW = '''#ifndef GL_FRAMEBUFFER
#define GL_FRAMEBUFFER          0x8D40
#define GL_RENDERBUFFER         0x8D41
#define GL_COLOR_ATTACHMENT0    0x8CE0
#define GL_DEPTH_ATTACHMENT     0x8D00
#define GL_STENCIL_ATTACHMENT   0x8D20
#define GL_DEPTH24_STENCIL8     0x88F0
#define GL_DEPTH_STENCIL_ATTACHMENT 0x821A
#define GL_RGBA8                0x8058
#define GL_FRAMEBUFFER_COMPLETE 0x8CD5
#endif

extern "C" {
    void glReadPixels(int, int, int, int, unsigned, unsigned, void*);
    void glPixelStorei(unsigned, int);
    void glFinish(void);
    void glViewport(int, int, int, int);
}

/* FBO-Funktionen ueber eglGetProcAddress, damit wir nicht gegen
   eine bestimmte GL-Header-Version binden. */
namespace {
    typedef void (*PFN_GenFramebuffers)(int, unsigned*);
    typedef void (*PFN_BindFramebuffer)(unsigned, unsigned);
    typedef void (*PFN_GenRenderbuffers)(int, unsigned*);
    typedef void (*PFN_BindRenderbuffer)(unsigned, unsigned);
    typedef void (*PFN_RenderbufferStorage)(unsigned, unsigned, int, int);
    typedef void (*PFN_FramebufferRenderbuffer)(unsigned, unsigned, unsigned, unsigned);
    typedef unsigned (*PFN_CheckFramebufferStatus)(unsigned);
    typedef void (*PFN_DeleteFramebuffers)(int, const unsigned*);
    typedef void (*PFN_DeleteRenderbuffers)(int, const unsigned*);

    PFN_GenFramebuffers          p_GenFramebuffers          = nullptr;
    PFN_BindFramebuffer          p_BindFramebuffer          = nullptr;
    PFN_GenRenderbuffers         p_GenRenderbuffers         = nullptr;
    PFN_BindRenderbuffer         p_BindRenderbuffer         = nullptr;
    PFN_RenderbufferStorage      p_RenderbufferStorage      = nullptr;
    PFN_FramebufferRenderbuffer  p_FramebufferRenderbuffer  = nullptr;
    PFN_CheckFramebufferStatus   p_CheckFramebufferStatus   = nullptr;
    PFN_DeleteFramebuffers       p_DeleteFramebuffers       = nullptr;
    PFN_DeleteRenderbuffers      p_DeleteRenderbuffers      = nullptr;

    bool loadFboEntryPoints()
    {
        if (p_GenFramebuffers) return true;
        p_GenFramebuffers = (PFN_GenFramebuffers)
            eglGetProcAddress("glGenFramebuffers");
        p_BindFramebuffer = (PFN_BindFramebuffer)
            eglGetProcAddress("glBindFramebuffer");
        p_GenRenderbuffers = (PFN_GenRenderbuffers)
            eglGetProcAddress("glGenRenderbuffers");
        p_BindRenderbuffer = (PFN_BindRenderbuffer)
            eglGetProcAddress("glBindRenderbuffer");
        p_RenderbufferStorage = (PFN_RenderbufferStorage)
            eglGetProcAddress("glRenderbufferStorage");
        p_FramebufferRenderbuffer = (PFN_FramebufferRenderbuffer)
            eglGetProcAddress("glFramebufferRenderbuffer");
        p_CheckFramebufferStatus = (PFN_CheckFramebufferStatus)
            eglGetProcAddress("glCheckFramebufferStatus");
        p_DeleteFramebuffers = (PFN_DeleteFramebuffers)
            eglGetProcAddress("glDeleteFramebuffers");
        p_DeleteRenderbuffers = (PFN_DeleteRenderbuffers)
            eglGetProcAddress("glDeleteRenderbuffers");
        return p_GenFramebuffers && p_BindFramebuffer &&
               p_GenRenderbuffers && p_BindRenderbuffer &&
               p_RenderbufferStorage && p_FramebufferRenderbuffer &&
               p_CheckFramebufferStatus;
    }
}'''

REALIZE_OLD = '''        (void)pbAttr;
        _surface = EGL_NO_SURFACE;'''

REALIZE_NEW = '''        (void)pbAttr;
        _surface = EGL_NO_SURFACE;

        /* Surfaceless: es gibt keinen Default-Framebuffer 0.
           Wir legen ein eigenes FBO an und melden es OSG. */
        if (!eglMakeCurrent(_display, EGL_NO_SURFACE, EGL_NO_SURFACE, _context)) {
            OSG_WARN << "GraphicsWindowEGL: makeCurrent fuer FBO-Setup fehlgeschlagen 0x"
                     << std::hex << eglGetError() << std::dec << std::endl;
            return false;
        }

        if (!loadFboEntryPoints()) {
            OSG_WARN << "GraphicsWindowEGL: FBO-Einsprungpunkte nicht verfuegbar"
                     << std::endl;
            return false;
        }

        p_GenFramebuffers(1, &_fbo);
        p_BindFramebuffer(GL_FRAMEBUFFER, _fbo);

        p_GenRenderbuffers(1, &_rbColor);
        p_BindRenderbuffer(GL_RENDERBUFFER, _rbColor);
        p_RenderbufferStorage(GL_RENDERBUFFER, GL_RGBA8, w, h);
        p_FramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                                  GL_RENDERBUFFER, _rbColor);

        p_GenRenderbuffers(1, &_rbDepth);
        p_BindRenderbuffer(GL_RENDERBUFFER, _rbDepth);
        p_RenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH24_STENCIL8, w, h);
        p_FramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT,
                                  GL_RENDERBUFFER, _rbDepth);

        unsigned status = p_CheckFramebufferStatus(GL_FRAMEBUFFER);
        if (status != GL_FRAMEBUFFER_COMPLETE) {
            OSG_WARN << "GraphicsWindowEGL: FBO unvollstaendig, status 0x"
                     << std::hex << status << std::dec
                     << " (" << w << "x" << h << ")" << std::endl;
            return false;
        }

        glViewport(0, 0, w, h);
        setDefaultFboId(_fbo);

        OSG_NOTICE << "GraphicsWindowEGL: FBO " << _fbo
                   << " angelegt, " << w << "x" << h << std::endl;'''

MEMBERS_OLD = '''    unsigned long _frameCount = 0;
    std::vector<unsigned char> _pixels;'''

MEMBERS_NEW = '''    unsigned long _frameCount = 0;
    std::vector<unsigned char> _pixels;
    unsigned _fbo = 0;
    unsigned _rbColor = 0;
    unsigned _rbDepth = 0;'''

CLOSE_OLD = '''        if (_display != EGL_NO_DISPLAY) {
            eglMakeCurrent(_display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);'''

CLOSE_NEW = '''        if (_display != EGL_NO_DISPLAY) {
            if (_fbo && p_DeleteFramebuffers) {
                eglMakeCurrent(_display, _surface, _surface, _context);
                p_DeleteFramebuffers(1, &_fbo);
                if (p_DeleteRenderbuffers) {
                    p_DeleteRenderbuffers(1, &_rbColor);
                    p_DeleteRenderbuffers(1, &_rbDepth);
                }
                _fbo = _rbColor = _rbDepth = 0;
            }
            eglMakeCurrent(_display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);'''

MAKECURRENT_OLD = '''        if (!eglMakeCurrent(_display, _surface, _surface, _context)) {
            OSG_WARN << "GraphicsWindowEGL: eglMakeCurrent failed 0x"
                     << std::hex << eglGetError() << std::dec << std::endl;
            return false;
        }
        return true;'''

MAKECURRENT_NEW = '''        if (!eglMakeCurrent(_display, _surface, _surface, _context)) {
            OSG_WARN << "GraphicsWindowEGL: eglMakeCurrent failed 0x"
                     << std::hex << eglGetError() << std::dec << std::endl;
            return false;
        }
        if (_fbo && p_BindFramebuffer) {
            p_BindFramebuffer(GL_FRAMEBUFFER, _fbo);
        }
        return true;'''


def main():
    try:
        s = open(P).read()
    except FileNotFoundError:
        print("Datei nicht gefunden - laeuft das im Container?", P)
        return 1

    steps = (
        (GL_DECLS_OLD,     GL_DECLS_NEW,     "GL-Deklarationen + FBO-Entrypoints"),
        (MEMBERS_OLD,      MEMBERS_NEW,      "Member"),
        (REALIZE_OLD,      REALIZE_NEW,      "realizeImplementation"),
        (MAKECURRENT_OLD,  MAKECURRENT_NEW,  "makeCurrentImplementation"),
        (CLOSE_OLD,        CLOSE_NEW,        "closeImplementation"),
    )

    for old, new, label in steps:
        if old not in s:
            print("FEHLER: Muster nicht gefunden:", label)
            return 1
        s = s.replace(old, new, 1)
        print("gepatcht:", label)

    open(P, 'w').write(s)
    print("fertig")
    return 0


if __name__ == '__main__':
    sys.exit(main())

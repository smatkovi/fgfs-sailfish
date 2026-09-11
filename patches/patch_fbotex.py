#!/usr/bin/env python3
"""
Ersetzt das Farb-Renderbuffer-Attachment des FBO durch eine Textur.

Bei einem Renderbuffer muss der Treiber auf einem Tile-Based Renderer
den kompletten Tile-Speicher aufloesen, bevor glReadPixels beginnen
kann - das PBO macht nur den Transport asynchron, nicht die
Aufloesung. Mit einem Textur-Attachment kann der Treiber das anders
planen.

Zweiter Vorteil: eine Textur laesst sich spaeter ueber
EGL_MESA_image_dma_buf_export als dmabuf exportieren, was den
Readback ganz ueberfluessig machen wuerde. Mit einem Renderbuffer
geht das nicht.
"""

import sys

P = '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5/src/osgViewer/GraphicsWindowEGL.cpp'

DECL_OLD = '''#ifndef GL_PIXEL_PACK_BUFFER'''
DECL_NEW = '''#ifndef GL_TEXTURE_2D
#define GL_TEXTURE_2D               0x0DE1
#define GL_TEXTURE_MIN_FILTER       0x2801
#define GL_TEXTURE_MAG_FILTER       0x2800
#define GL_NEAREST                  0x2600
#define GL_CLAMP_TO_EDGE            0x812F
#define GL_TEXTURE_WRAP_S           0x2802
#define GL_TEXTURE_WRAP_T           0x2803
#endif

#ifndef GL_PIXEL_PACK_BUFFER'''

FN_OLD = '''    bool loadPboEntryPoints()'''
FN_NEW = '''    typedef void (*PFN_tex_img)(unsigned, int, int, int, int, int,
                                unsigned, unsigned, const void*);
    typedef void (*PFN_tex_par)(unsigned, unsigned, int);
    typedef void (*PFN_fb_tex)(unsigned, unsigned, unsigned, unsigned, int);

    PFN_v_ip     p_GenTextures = nullptr;
    PFN_v_uu     p_BindTexture = nullptr;
    PFN_tex_img  p_TexImage2D = nullptr;
    PFN_tex_par  p_TexParameteri = nullptr;
    PFN_fb_tex   p_FramebufferTexture2D = nullptr;
    PFN_v_icp    p_DeleteTextures = nullptr;

    bool loadTexEntryPoints()
    {
        if (p_GenTextures) return true;
        p_GenTextures   = (PFN_v_ip)    eglGetProcAddress("glGenTextures");
        p_BindTexture   = (PFN_v_uu)    eglGetProcAddress("glBindTexture");
        p_TexImage2D    = (PFN_tex_img) eglGetProcAddress("glTexImage2D");
        p_TexParameteri = (PFN_tex_par) eglGetProcAddress("glTexParameteri");
        p_FramebufferTexture2D =
            (PFN_fb_tex) eglGetProcAddress("glFramebufferTexture2D");
        p_DeleteTextures = (PFN_v_icp)  eglGetProcAddress("glDeleteTextures");
        return p_GenTextures && p_BindTexture && p_TexImage2D
            && p_TexParameteri && p_FramebufferTexture2D;
    }

    bool loadPboEntryPoints()'''

# Farb-Renderbuffer durch Textur ersetzen
ATT_OLD = '''        p_GenRenderbuffers(1, &_rbColor);
        p_BindRenderbuffer(GL_RENDERBUFFER, _rbColor);
        p_RenderbufferStorage(GL_RENDERBUFFER, GL_RGBA8, w, h);
        p_FramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                                  GL_RENDERBUFFER, _rbColor);'''

ATT_NEW = '''        /* Farbziel als Textur statt Renderbuffer - siehe Kommentar
           oben zur Tile-Aufloesung. */
        if (!loadTexEntryPoints()) {
            OSG_WARN << "GraphicsWindowEGL: Textur-Entrypoints fehlen"
                     << std::endl;
            return false;
        }
        p_GenTextures(1, &_texColor);
        p_BindTexture(GL_TEXTURE_2D, _texColor);
        p_TexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, w, h, 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
        p_TexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        p_TexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
        p_TexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
        p_TexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
        p_FramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                               GL_TEXTURE_2D, _texColor, 0);'''

MEM_OLD = '''    unsigned _rbColor = 0;'''
MEM_NEW = '''    unsigned _rbColor = 0;
    unsigned _texColor = 0;'''

LOG_OLD = '''        OSG_NOTICE << "GraphicsWindowEGL: FBO " << _fbo << " angelegt, "
                   << w << "x" << h << std::endl;'''
LOG_NEW = '''        OSG_WARN << "GraphicsWindowEGL: FBO " << _fbo
                 << " mit Textur-Attachment " << _texColor
                 << ", " << w << "x" << h << std::endl;'''


def main():
    try:
        s = open(P).read()
    except FileNotFoundError:
        print("nicht gefunden - im Container ausfuehren:", P)
        return 1

    if '_texColor' in s:
        print("bereits gepatcht")
        return 0

    for old, new, label in (
        (DECL_OLD, DECL_NEW, "Textur-Konstanten"),
        (FN_OLD,   FN_NEW,   "Textur-Entrypoints"),
        (MEM_OLD,  MEM_NEW,  "Member"),
        (ATT_OLD,  ATT_NEW,  "Farbattachment als Textur"),
        (LOG_OLD,  LOG_NEW,  "Log auf WARN (NOTICE wird verschluckt)"),
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

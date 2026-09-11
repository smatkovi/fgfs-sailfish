#!/usr/bin/env python3
"""Fourteenth round (FlightGear GLES port): two runtime switches to measure.

FGFS_GL_CONTEXT=3   ask EGL for an ES 3 context instead of ES 2.  The driver
                    hands out 3.2 either way, but asking for it lets the
                    driver pick its ES 3 paths.
FGFS_GLES_LEAN=1    skip the GL modes that do not exist in ES and turn off
                    OSG's per-attribute error check.  GL_VERTEX_PROGRAM_TWO_SIDE
                    alone is toggled about twenty times per frame by
                    FlightGear's effects; each toggle costs a rejected
                    glEnable, a glGetError that synchronises with the driver,
                    and a warning line on stderr.  None of them has any effect
                    under ES, so the picture does not change.

Both default to off, so a build with this patch behaves as before until the
variables are set.
Run after ffp_gles.py .. ffp_gles13.py: python3 ffp_gles14.py [osg-source-root]"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'

def patch(rel, edits):
    p = os.path.join(ROOT, rel); s = open(p).read()
    done = 0
    for old, new in edits:
        if new in s:
            continue
        assert s.count(old) == 1, '%s: Anker fehlt oder mehrdeutig: %r' % (rel, old[:60])
        s = s.replace(old, new); done += 1
    open(p, 'w').write(s)
    print('%s: %d Stellen' % (rel, done))

# ---------------------------------------------------- ES 3 context on request
patch('src/osgViewer/GraphicsWindowEGL.cpp', [
('#if defined(OSG_GLES2_AVAILABLE) || defined(OSG_GLES3_AVAILABLE)\n'
 '#  define FGFS_EGL_API        EGL_OPENGL_ES_API\n'
 '#  define FGFS_EGL_RENDERABLE EGL_OPENGL_ES2_BIT\n'
 '#  define FGFS_EGL_CTX_ATTR   EGL_CONTEXT_CLIENT_VERSION\n'
 '#  define FGFS_EGL_CTX_VER    2\n',
 '#if defined(OSG_GLES2_AVAILABLE) || defined(OSG_GLES3_AVAILABLE)\n'
 '#  define FGFS_EGL_API        EGL_OPENGL_ES_API\n'
 '#  define FGFS_EGL_RENDERABLE EGL_OPENGL_ES2_BIT\n'
 '#  define FGFS_EGL_CTX_ATTR   EGL_CONTEXT_CLIENT_VERSION\n'
 '/* FGFS_GL_CONTEXT=3 asks for an ES 3 context.  The Mali driver reports 3.2\n'
 '   for an ES 2 context as well, but asking lets it choose its ES 3 paths. */\n'
 'static int fgfsEglCtxVer()\n'
 '{\n'
 '    const char* e = ::getenv("FGFS_GL_CONTEXT");\n'
 '    return (e && *e == \'3\') ? 3 : 2;\n'
 '}\n'
 '#  define FGFS_EGL_CTX_VER    fgfsEglCtxVer()\n'),
])

# ---------------------------------------------------- lean mode switch in State
patch('include/osg/State', [
('        inline bool applyMode(StateAttribute::GLMode mode,bool enabled,ModeStack& ms)\n'
 '        {\n'
 '            if (ms.valid && ms.last_applied_value != enabled)\n'
 '            {\n',
 '#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)\n'
 '        /* FlightGear GLES port, FGFS_GLES_LEAN=1: these modes do not exist\n'
 '           under ES.  Setting them raises INVALID_ENUM and changes nothing,\n'
 '           but each attempt costs a driver round trip through the error check. */\n'
 '        static inline bool fgfsDeadMode(StateAttribute::GLMode mode)\n'
 '        {\n'
 '            static const int lean = (::getenv("FGFS_GLES_LEAN") != 0) ? 1 : 0;\n'
 '            if (!lean) return false;\n'
 '            return mode == 0x8643      /* GL_VERTEX_PROGRAM_TWO_SIDE */\n'
 '                || mode == 0x8642      /* GL_VERTEX_PROGRAM_POINT_SIZE */\n'
 '                || mode == 0x0DE1      /* GL_TEXTURE_2D */\n'
 '                || mode == 0x4001;     /* GL_COLOR_LOGIC_OP */\n'
 '        }\n'
 '#endif\n'
 '\n'
 '         inline bool applyMode(StateAttribute::GLMode mode,bool enabled,ModeStack& ms)\n'
 '         {\n'
 '#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)\n'
 '             if (fgfsDeadMode(mode)) { ms.last_applied_value = enabled; return false; }\n'
 '#endif\n'
 '             if (ms.valid && ms.last_applied_value != enabled)\n'
 '             {\n'),
('        inline bool applyModeOnTexUnit(unsigned int unit,StateAttribute::GLMode mode,bool enabled,ModeStack& ms)\n'
 '        {\n'
 '            if (ms.valid && ms.last_applied_value != enabled)\n'
 '            {\n',
 '        inline bool applyModeOnTexUnit(unsigned int unit,StateAttribute::GLMode mode,bool enabled,ModeStack& ms)\n'
 '        {\n'
 '#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)\n'
 '            if (fgfsDeadMode(mode)) { ms.last_applied_value = enabled; return false; }\n'
 '#endif\n'
 '            if (ms.valid && ms.last_applied_value != enabled)\n'
 '            {\n'),
])

# ---------------------------------------------------- error checking off in lean mode
patch('src/osg/State.cpp', [
('    _ffpLastProgram = 0;\n    initFFPUniforms();\n',
 '#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)\n'
 '    /* FlightGear GLES port: with FGFS_GLES_LEAN=1 the per-attribute check is\n'
 '       pure cost - the errors it reports are the desktop-only modes above. */\n'
 '    if (::getenv("FGFS_GLES_LEAN")) _checkGLErrors = NEVER_CHECK_GL_ERRORS;\n'
 '#endif\n'
 '    _ffpLastProgram = 0;\n    initFFPUniforms();\n'),
])
print('fertig')

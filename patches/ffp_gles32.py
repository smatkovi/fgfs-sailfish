#!/usr/bin/env python3
"""OSG: renderbuffers under GLES need a sized internal format.

SimGear's canvas attaches a PACKED_DEPTH_STENCIL_BUFFER with the unsized
GL_DEPTH_STENCIL (0x84F9), which is what desktop GL accepts; under GLES
glRenderbufferStorage rejects it with INVALID_ENUM, the buffer never gets
storage, the FBO is incomplete, and OSG quietly falls back to rendering
the canvas in the window framebuffer - which has no stencil.  ShivaVG
fills and strokes through the stencil buffer, so every path came out as
its painted bounding box (BEFUNDE.md, P40).  Translate the unsized formats
to their sized GLES equivalents where the storage is allocated.

Idempotent.  python3 ffp_gles32.py [osg-source-root]"""
import os, sys
ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/OpenSceneGraph-OpenSceneGraph-3.6.5')
p = os.path.join(ROOT, 'src/osg/FrameBufferObject.cpp')
s = open(p).read()
if 'sized GLES equivalents' in s:
    print('  schon aktuell'); raise SystemExit
old = '''        // bind and configure
        ext->glBindRenderbuffer(GL_RENDERBUFFER_EXT, objectID);
'''
assert s.count(old) == 1, 'bind anchor'
new = '''        // bind and configure
        ext->glBindRenderbuffer(GL_RENDERBUFFER_EXT, objectID);

        // GLES only knows sized renderbuffer formats: the unsized
        // GL_DEPTH_STENCIL that packed depth/stencil attachments are
        // requested with is INVALID_ENUM there, the storage never
        // happens and the FBO ends up incomplete.  Map the unsized
        // formats to their sized GLES equivalents.
        GLenum internalFormat = _internalFormat;
#if defined(OSG_GLES2_AVAILABLE) || defined(OSG_GLES3_AVAILABLE)
        if (internalFormat == GL_DEPTH_STENCIL_EXT)       internalFormat = GL_DEPTH24_STENCIL8_EXT;
        else if (internalFormat == GL_DEPTH_COMPONENT)    internalFormat = GL_DEPTH_COMPONENT16;
        else if (internalFormat == 0x1901 /* GL_STENCIL_INDEX */) internalFormat = GL_STENCIL_INDEX8_EXT;
#endif
'''
s = s.replace(old, new, 1)
# the three storage calls in this function use the translated format
seg_start = s.index(new)
seg_end = s.index('        dirty = 0;\n    }\n\n    return objectID;', seg_start)
seg = s[seg_start:seg_end]
n = seg.count('_internalFormat, _width, _height')
assert n == 3, 'expected three storage calls, found %d' % n
seg = seg.replace('_internalFormat, _width, _height', 'internalFormat, _width, _height')
s = s[:seg_start] + seg + s[seg_end:]
open(p, 'w').write(s)
print('geaendert src/osg/FrameBufferObject.cpp')

#!/usr/bin/env python3
"""GraphicsWindowEGL: release the context at the end of realize().

realizeImplementation() binds the context on the calling thread to set up
the FBO and leaves it bound.  In OSG's threaded modes the draw thread then
tries to bind the same context and EGL refuses with EGL_BAD_ACCESS (0x3002),
because a context can be current on one thread only.  The GL function table
is then built without a context - GL_VERSION reads NULL - and the first call
through it crashes in PerContextProgram.  OSG expects realize() to hand the
context back; the viewer binds it again on whichever thread renders.

  python3 egl_release_after_realize.py [osg-source-root]
"""
import os
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'
p = os.path.join(ROOT, 'src/osgViewer/GraphicsWindowEGL.cpp')
s = open(p).read()

old = '''        OSG_WARN << "GraphicsWindowEGL: realize fertig" << std::endl;
        _realized = true;
        return true;
    }
'''
new = '''        /* Hand the context back.  A context can be current on one thread
           only, and in OSG's threaded modes it is the draw thread, not this
           one, that renders: leaving it bound here made the draw thread's
           eglMakeCurrent fail with EGL_BAD_ACCESS and the GL function table
           come up empty.  The viewer binds it again where it is needed. */
        eglMakeCurrent(_display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);

        OSG_WARN << "GraphicsWindowEGL: realize fertig" << std::endl;
        _realized = true;
        return true;
    }
'''
if new in s:
    print('  schon aktuell')
else:
    assert s.count(old) == 1, 'Anker fehlt oder mehrdeutig'
    s = s.replace(old, new)
    open(p, 'w').write(s)
    print('geaendert src/osgViewer/GraphicsWindowEGL.cpp')
print('fertig')

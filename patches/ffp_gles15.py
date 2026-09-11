#!/usr/bin/env python3
"""Fifteenth round (FlightGear GLES port): glHint under ES, and phase timings.

FGFS_GLES_LEAN=1 now also skips glHint for every target ES does not have.
Hint accounts for about 7000 of the 10800 error messages per run - more than
all the GL modes together - and ES only knows GL_GENERATE_MIPMAP_HINT (plus
GL_FRAGMENT_SHADER_DERIVATIVE_HINT where the extension is present).  Every
other target is rejected, so nothing changes on screen.

FGFS_GLES_TIMING=1 logs how long cull and draw take, averaged over 100 frames.
OSG has these numbers already but only publishes them through the on-screen
overlay, which is no use when rendering headless.  This finally answers
whether the time goes into the scene graph traversal on the CPU or into
issuing and executing the draw calls.

Run after ffp_gles.py .. ffp_gles14.py: python3 ffp_gles15.py [osg-source-root]"""
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

# ------------------------------------------------------------------- glHint
patch('src/osg/Hint.cpp', [
('void Hint::apply(State& /*state*/) const\n'
 '{\n'
 '    if (_target==GL_NONE || _mode==GL_NONE) return;\n'
 '\n'
 '    glHint(_target, _mode);\n'
 '}\n',
 'void Hint::apply(State& /*state*/) const\n'
 '{\n'
 '    if (_target==GL_NONE || _mode==GL_NONE) return;\n'
 '\n'
 '#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)\n'
 '    /* FlightGear GLES port, FGFS_GLES_LEAN=1: ES has GL_GENERATE_MIPMAP_HINT\n'
 '       and, with the extension, GL_FRAGMENT_SHADER_DERIVATIVE_HINT.  Every\n'
 '       other target raises INVALID_ENUM and does nothing, and each attempt\n'
 '       costs a driver round trip through the error check. */\n'
 '    {\n'
 '        static const int lean = (::getenv("FGFS_GLES_LEAN") != 0) ? 1 : 0;\n'
 '        if (lean && _target != 0x8192      /* GL_GENERATE_MIPMAP_HINT */\n'
 '                 && _target != 0x8B8B)     /* GL_FRAGMENT_SHADER_DERIVATIVE_HINT */\n'
 '            return;\n'
 '    }\n'
 '#endif\n'
 '    glHint(_target, _mode);\n'
 '}\n'),
])

# ------------------------------------------------------------ phase timings
patch('src/osgViewer/Renderer.cpp', [
('    osg::Timer_t afterDrawTick = osg::Timer::instance()->tick();\n\n    if (stats && stats->collectStats("rendering"))\n',
 '    osg::Timer_t afterDrawTick = osg::Timer::instance()->tick();\n'
 '\n'
 '#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)\n'
 '    /* FlightGear GLES port, FGFS_GLES_TIMING=1: OSG collects these numbers\n'
 '       only for the on-screen overlay, which we cannot see when rendering\n'
 '       headless.  Average over 100 frames and log them. */\n'
 '    {\n'
 '        static int enabled = -1;\n'
 '        if (enabled < 0) enabled = (::getenv("FGFS_GLES_TIMING") != 0) ? 1 : 0;\n'
 '        if (enabled)\n'
 '        {\n'
 '            static unsigned long n = 0;\n'
 '            static double cullSum = 0.0, drawSum = 0.0, frameSum = 0.0;\n'
 '            static osg::Timer_t lastFrame = 0;\n'
 '            cullSum += osg::Timer::instance()->delta_m(beforeCullTick, afterCullTick);\n'
 '            drawSum += osg::Timer::instance()->delta_m(beforeDrawTick, afterDrawTick);\n'
 '            if (lastFrame) frameSum += osg::Timer::instance()->delta_m(lastFrame, afterDrawTick);\n'
 '            lastFrame = afterDrawTick;\n'
 '            if (++n % 100 == 0)\n'
 '            {\n'
 '                OSG_WARN << "FGFS timing over 100 frames: cull " << (cullSum / 100.0)\n'
 '                         << " ms, draw " << (drawSum / 100.0)\n'
 '                         << " ms, frame " << (frameSum / 100.0)\n'
 '                         << " ms (rest " << ((frameSum - cullSum - drawSum) / 100.0)\n'
 '                         << " ms outside cull and draw)" << std::endl;\n'
 '                cullSum = drawSum = frameSum = 0.0;\n'
 '            }\n'
 '        }\n'
 '    }\n'
 '#endif\n'
 '\n    if (stats && stats->collectStats("rendering"))\n'),
])
print('fertig')

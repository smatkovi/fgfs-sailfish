#!/usr/bin/env python3
"""Seventeenth round (FlightGear GLES port): PBO readback under ES 3, and
timings for the draw-thread mode.

The PBO path in GraphicsWindowEGL was complete but switched off for GLES
with "GLES2 has no pixel buffer objects".  ES 3 has them; the one thing it
lacks is a readable glMapBuffer, so the ES path maps with glMapBufferRange
and GL_MAP_READ_BIT instead.  With a PBO the readback no longer stalls the
thread that issues it - which matters in DrawThreadPerContext, where that
thread is the one meant to overlap with the next frame's update.

The FGFS_GLES_TIMING output was only in Renderer::cull_draw(); the
DrawThreadPerContext mode goes through Renderer::draw(), which now reports
the same way (draw only - cull runs on the other thread there).

Run after ffp_gles.py .. ffp_gles16.py: python3 ffp_gles17.py [osg-source-root]"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'

def patch(rel, edits):
    p = os.path.join(ROOT, rel); s = open(p).read()
    done = 0
    for old, new in edits:
        if new in s:
            continue
        assert s.count(old) == 1, '%s: Anker fehlt oder mehrdeutig: %r' % (rel, old[:70])
        s = s.replace(old, new); done += 1
    open(p, 'w').write(s)
    print('%s: %d Stellen' % (rel, done))

patch('src/osgViewer/GraphicsWindowEGL.cpp', [
# a pointer type for glMapBufferRange
('    typedef void* (*PFN_p_uu)(unsigned, unsigned);\n',
 '    typedef void* (*PFN_p_uu)(unsigned, unsigned);\n'
 '    typedef void* (*PFN_p_ullu)(unsigned, long, long, unsigned);   /* glMapBufferRange */\n'),
('    PFN_p_uu    p_MapBuffer = nullptr;\n',
 '    PFN_p_uu    p_MapBuffer = nullptr;\n'
 '    PFN_p_ullu  p_MapBufferRange = nullptr;   /* ES 3: the readable mapping */\n'),
# ES 3 loads glMapBufferRange in place of glMapBuffer
('        p_MapBuffer     = (PFN_p_uu)  eglGetProcAddress("glMapBuffer");\n'
 '        p_UnmapBuffer   = (PFN_b_u)   eglGetProcAddress("glUnmapBuffer");\n'
 '        p_DeleteBuffers = (PFN_v_icp) eglGetProcAddress("glDeleteBuffers");\n'
 '        return p_GenBuffers && p_BindBuffer && p_BufferData\n'
 '            && p_MapBuffer && p_UnmapBuffer;\n',
 '        p_MapBuffer     = (PFN_p_uu)  eglGetProcAddress("glMapBuffer");\n'
 '        p_MapBufferRange= (PFN_p_ullu)eglGetProcAddress("glMapBufferRange");\n'
 '        p_UnmapBuffer   = (PFN_b_u)   eglGetProcAddress("glUnmapBuffer");\n'
 '        p_DeleteBuffers = (PFN_v_icp) eglGetProcAddress("glDeleteBuffers");\n'
 '        /* ES 3 has no readable glMapBuffer; glMapBufferRange does the job. */\n'
 '        return p_GenBuffers && p_BindBuffer && p_BufferData\n'
 '            && (p_MapBuffer || p_MapBufferRange) && p_UnmapBuffer;\n'),
# no longer refuse PBOs on GLES
('#if defined(OSG_GLES2_AVAILABLE) || defined(OSG_GLES3_AVAILABLE)\n'
 '            if (true) {   /* GLES2 hat keine Pixel-Buffer-Objects */\n'
 '#else\n'
 '            if (!loadPboEntryPoints()) {\n'
 '#endif\n',
 '            /* ES 3 has pixel buffer objects (ES 2 has not); the entry\n'
 '               points decide, not the profile.  FGFS_NO_PBO=1 forces the\n'
 '               blocking path for comparison. */\n'
 '            if (::getenv("FGFS_NO_PBO") || !loadPboEntryPoints()) {\n'),
# map with glMapBufferRange when that is what we have
('            void* src = p_MapBuffer(GL_PIXEL_PACK_BUFFER, GL_READ_ONLY);\n',
 '            void* src = p_MapBufferRange\n'
 '                ? p_MapBufferRange(GL_PIXEL_PACK_BUFFER, 0, long(bytes),\n'
 '                                   0x0001 /* GL_MAP_READ_BIT */)\n'
 '                : p_MapBuffer(GL_PIXEL_PACK_BUFFER, GL_READ_ONLY);\n'),
])

# timings on the draw-thread path as well
patch('src/osgViewer/Renderer.cpp', [
('        osg::Timer_t afterDrawTick = osg::Timer::instance()->tick();\n'
 '\n'
 '//        OSG_NOTICE<<"Time wait for draw = "',
 '        osg::Timer_t afterDrawTick = osg::Timer::instance()->tick();\n'
 '\n'
 '#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)\n'
 '        /* FlightGear GLES port, FGFS_GLES_TIMING=1 - the DrawThreadPerContext\n'
 '           path; cull runs on the other thread and is not seen here. */\n'
 '        {\n'
 '            static int enabled = -1;\n'
 '            if (enabled < 0) enabled = (::getenv("FGFS_GLES_TIMING") != 0) ? 1 : 0;\n'
 '            if (enabled)\n'
 '            {\n'
 '                static unsigned long n = 0;\n'
 '                static double drawSum = 0.0, frameSum = 0.0;\n'
 '                static osg::Timer_t lastFrame = 0;\n'
 '                drawSum += osg::Timer::instance()->delta_m(beforeDrawTick, afterDrawTick);\n'
 '                if (lastFrame) frameSum += osg::Timer::instance()->delta_m(lastFrame, afterDrawTick);\n'
 '                lastFrame = afterDrawTick;\n'
 '                if (++n % 100 == 0)\n'
 '                {\n'
 '                    OSG_WARN << "FGFS timing over 100 frames (draw thread): draw " << (drawSum / 100.0)\n'
 '                             << " ms, frame " << (frameSum / 100.0)\n'
 '                             << " ms (rest " << ((frameSum - drawSum) / 100.0)\n'
 '                             << " ms outside draw)" << std::endl;\n'
 '                    drawSum = frameSum = 0.0;\n'
 '                }\n'
 '            }\n'
 '        }\n'
 '#endif\n'
 '\n'
 '//        OSG_NOTICE<<"Time wait for draw = "'),
])
print('fertig')

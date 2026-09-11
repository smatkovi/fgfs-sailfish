#!/usr/bin/env python3
"""Sixteenth round (FlightGear GLES port): make the lean path the normal one,
and break the draw phase down further.

Measured on the device, over four hundred frames each: skipping the GL modes
and glHint targets that ES does not have takes the frame from 48.4 ms to
36.8 ms - cull 4.4 -> 3.1, draw 26.0 -> 18.8, rest 18.0 -> 14.8 - and removes
all ten thousand error messages per run.  Nothing changes on screen, because
every call it skips was rejected by the driver anyway.  So it stops being a
switch and becomes what the GLES build does.  FGFS_GLES_FAT=1 brings the old
behaviour back for comparison.

FGFS_GLES_TIMING=1 additionally counts, per hundred frames, how many state
attributes and modes are applied and how many drawables are dispatched, so
the remaining 19 ms of draw can be attributed.

Run after ffp_gles.py .. ffp_gles15.py: python3 ffp_gles16.py [osg-source-root]"""
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

# ---- lean is now the default; FGFS_GLES_FAT=1 restores the old behaviour
patch('include/osg/State', [
('            static const int lean = (::getenv("FGFS_GLES_LEAN") != 0) ? 1 : 0;\n'
 '            if (!lean) return false;\n',
 '            static const int fat = (::getenv("FGFS_GLES_FAT") != 0) ? 1 : 0;\n'
 '            if (fat) return false;\n'),
])
patch('src/osg/Hint.cpp', [
('        static const int lean = (::getenv("FGFS_GLES_LEAN") != 0) ? 1 : 0;\n'
 '        if (lean && _target != 0x8192      /* GL_GENERATE_MIPMAP_HINT */\n'
 '                 && _target != 0x8B8B)     /* GL_FRAGMENT_SHADER_DERIVATIVE_HINT */\n'
 '            return;\n',
 '        static const int fat = (::getenv("FGFS_GLES_FAT") != 0) ? 1 : 0;\n'
 '        if (!fat && _target != 0x8192      /* GL_GENERATE_MIPMAP_HINT */\n'
 '                 && _target != 0x8B8B)     /* GL_FRAGMENT_SHADER_DERIVATIVE_HINT */\n'
 '            return;\n'),
])
patch('src/osg/State.cpp', [
('    if (::getenv("FGFS_GLES_LEAN")) _checkGLErrors = NEVER_CHECK_GL_ERRORS;\n',
 '    if (!::getenv("FGFS_GLES_FAT")) _checkGLErrors = NEVER_CHECK_GL_ERRORS;\n'),
])

# ---- count what the draw phase actually does
patch('include/osg/State', [
('        void applyModelViewAndProjectionUniformsIfRequired();\n',
 '        void applyModelViewAndProjectionUniformsIfRequired();\n'
 '\n'
 '        /* FlightGear GLES port: counters for FGFS_GLES_TIMING=1.  Public and\n'
 '           unconditional so the header stays the same in both profiles. */\n'
 '        mutable unsigned long _fgfsNumAttribs, _fgfsNumModes, _fgfsNumDrawables;\n'),
])
patch('src/osg/State.cpp', [
('    resetVertexAttributeAlias();\n',
 '    _fgfsNumAttribs = _fgfsNumModes = _fgfsNumDrawables = 0;\n\n'
 '    resetVertexAttributeAlias();\n'),
])
patch('include/osg/State', [
('             if (fgfsDeadMode(mode)) { ms.last_applied_value = enabled; return false; }\n'
 '#endif\n'
 '             if (ms.valid && ms.last_applied_value != enabled)\n'
 '             {\n'
 '                ms.last_applied_value = enabled;\n',
 '             if (fgfsDeadMode(mode)) { ms.last_applied_value = enabled; return false; }\n'
 '#endif\n'
 '             if (ms.valid && ms.last_applied_value != enabled)\n'
 '             {\n'
 '                ++_fgfsNumModes;\n'
 '                ms.last_applied_value = enabled;\n'),
])

# ---- count applied attributes and dispatched drawables
patch('include/osg/State', [
("""            if (as.last_applied_attribute != attribute)
            {
                if (!as.global_default_attribute.valid()) as.global_default_attribute = attribute->cloneType()->asStateAttribute();

                as.last_applied_attribute = attribute;
""",
 """            if (as.last_applied_attribute != attribute)
            {
                if (!as.global_default_attribute.valid()) as.global_default_attribute = attribute->cloneType()->asStateAttribute();

                ++_fgfsNumAttribs;
                as.last_applied_attribute = attribute;
"""),
])

patch('src/osg/Geometry.cpp', [
("""void Geometry::drawVertexArraysImplementation(RenderInfo& renderInfo) const
{
    State& state = *renderInfo.getState();
    VertexArrayState* vas = state.getCurrentVertexArrayState();
""",
 """void Geometry::drawVertexArraysImplementation(RenderInfo& renderInfo) const
{
    State& state = *renderInfo.getState();
    VertexArrayState* vas = state.getCurrentVertexArrayState();
    ++state._fgfsNumDrawables;
"""),
])

# ---- report them alongside the timings
patch('src/osgViewer/Renderer.cpp', [
('                OSG_WARN << "FGFS timing over 100 frames: cull " << (cullSum / 100.0)\n'
 '                         << " ms, draw " << (drawSum / 100.0)\n'
 '                         << " ms, frame " << (frameSum / 100.0)\n'
 '                         << " ms (rest " << ((frameSum - cullSum - drawSum) / 100.0)\n'
 '                         << " ms outside cull and draw)" << std::endl;\n',
 '                OSG_WARN << "FGFS timing over 100 frames: cull " << (cullSum / 100.0)\n'
 '                         << " ms, draw " << (drawSum / 100.0)\n'
 '                         << " ms, frame " << (frameSum / 100.0)\n'
 '                         << " ms (rest " << ((frameSum - cullSum - drawSum) / 100.0)\n'
 '                         << " ms outside cull and draw)" << std::endl;\n'
 '                OSG_WARN << "FGFS per frame: modes " << (state->_fgfsNumModes / 100)\n'
 '                         << ", attributes " << (state->_fgfsNumAttribs / 100)\n'
 '                         << ", drawables " << (state->_fgfsNumDrawables / 100) << std::endl;\n'
 '                state->_fgfsNumModes = state->_fgfsNumAttribs = state->_fgfsNumDrawables = 0;\n'),
])
print('fertig')

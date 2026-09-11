#!/usr/bin/env python3
"""Ninth round (FlightGear GLES port): time-gated diagnostics.  OSG_GLES_DEBUG_AFTER=<seconds>
starts logging only after that many seconds of process time, so the scene is
covered instead of the splash.  Logs: every setArray call for slot 3
(osg_MultiTexCoord0) including the "array unchanged, nothing dispatched" case,
and the GL state after the pointer call.
Run after ffp_gles.py .. ffp_gles8.py: python3 ffp_gles9.py [osg-source-root]"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'

p = os.path.join(ROOT, 'src/osg/VertexArrayState.cpp'); s = open(p).read()

# ---- replace the counter-limited probe with a time-gated one
start = s.index('#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)\n        /* FlightGear GLES port: what does GL hold for slot 3')
end = s.index('#endif\n', start) + len('#endif\n')
s = s[:start] + (
    '#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)\n'
    '        /* FlightGear GLES port: what does GL hold for slot 3 (osg_MultiTexCoord0)? */\n'
    '        if (unit == 3 && ext->glGetVertexAttribiv && osg_gles_debug_now())\n'
    '        {\n'
    '            static int logged = 0;\n'
    '            if (logged < 16)\n'
    '            {\n'
    '                ++logged;\n'
    '                GLint enabled = -1, divisor = -1, size = -1, buffer = -1, type = -1;\n'
    '                ext->glGetVertexAttribiv(3, 0x8622 /* ENABLED */, &enabled);\n'
    '                ext->glGetVertexAttribiv(3, 0x88FE /* DIVISOR */, &divisor);\n'
    '                ext->glGetVertexAttribiv(3, 0x8623 /* SIZE */, &size);\n'
    '                ext->glGetVertexAttribiv(3, 0x8625 /* TYPE */, &type);\n'
    '                ext->glGetVertexAttribiv(3, 0x889F /* BUFFER_BINDING */, &buffer);\n'
    '                const float* f = (new_array->getDataType() == GL_FLOAT && new_array->getDataPointer()) ? static_cast<const float*>(new_array->getDataPointer()) : 0;\n'
    '                OSG_WARN << "attrib3 after pointer: enabled=" << enabled << " divisor=" << divisor << " size=" << size\n'
    '                         << " type=0x" << std::hex << type << std::dec << " buffer=" << buffer << " ptr=" << ptr\n'
    '                         << " n=" << new_array->getNumElements() << " first=" << (f ? f[0] : 0.0f) << "," << (f ? f[1] : 0.0f)\n'
    '                         << " glGetError=0x" << std::hex << glGetError() << std::dec << std::endl;\n'
    '            }\n'
    '        }\n'
    '#endif\n') + s[end:]

# ---- the time gate itself
old = 'struct VertexAttribArrayDispatch : public VertexArrayState::ArrayDispatch\n'
assert s.count(old) == 1, 'dispatch struct'
s = s.replace(old,
    '/* FlightGear GLES port: OSG_GLES_DEBUG_AFTER=<seconds> - only log once the\n'
    '   scene is up, so the probes are not used up by the splash screen. */\n'
    'static bool osg_gles_debug_now()\n'
    '{\n'
    '    static double after = -1.0;\n'
    '    static osg::Timer_t start = osg::Timer::instance()->tick();\n'
    '    if (after < 0.0)\n'
    '    {\n'
    '        const char* e = getenv("OSG_GLES_DEBUG_AFTER");\n'
    '        after = (e && *e) ? atof(e) : 0.0;\n'
    '    }\n'
    '    return osg::Timer::instance()->delta_s(start, osg::Timer::instance()->tick()) >= after;\n'
    '}\n'
    '\n' + old)

# ---- log setArray for slot 3, including the "nothing dispatched" path
old = ('void VertexArrayState::setArray(ArrayDispatch* vad, osg::State& state, const osg::Array* new_array)\n'
       '{\n'
       '    if (new_array)\n'
       '    {\n')
assert s.count(old) == 1, 'setArray'
s = s.replace(old,
    'void VertexArrayState::setArray(ArrayDispatch* vad, osg::State& state, const osg::Array* new_array)\n'
    '{\n'
    '#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)\n'
    '    /* FlightGear GLES port: does slot 3 get an array at all for scene geometry? */\n'
    '    if (vad && vad->isVertexAttribDispatch() && vad == _vertexAttribArrays[3].get() && osg_gles_debug_now())\n'
    '    {\n'
    '        static int logged = 0;\n'
    '        if (logged < 20)\n'
    '        {\n'
    '            ++logged;\n'
    '            const bool same = new_array && vad->array == new_array && new_array->getModifiedCount() == vad->modifiedCount;\n'
    '            OSG_WARN << "setArray slot3 new=" << (const void*)new_array\n'
    '                     << " n=" << (new_array ? new_array->getNumElements() : 0)\n'
    '                     << " prev=" << (const void*)vad->array\n'
    '                     << (new_array ? (same ? " -> unchanged, no dispatch" : " -> dispatch") : " -> disable") << std::endl;\n'
    '        }\n'
    '    }\n'
    '#endif\n'
    '    if (new_array)\n'
    '    {\n')

if '#include <osg/Timer>' not in s:
    s = s.replace('#include <osg/State>\n', '#include <osg/State>\n#include <osg/Timer>\n', 1)
open(p, 'w').write(s); print('geaendert src/osg/VertexArrayState.cpp')
print('fertig')

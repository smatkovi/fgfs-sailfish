#!/usr/bin/env python3
"""Eighth round (FlightGear GLES port): diagnostics on attribute slot 3
(osg_MultiTexCoord0 in OSG's compact alias layout) - GL state right after the
array is set (enabled, divisor, size, buffer) - plus every VertexAttribDivisor
applied, and the full light line.
Run after ffp_gles.py .. ffp_gles7.py: python3 ffp_gles8.py [osg-source-root]"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'

def patch(rel, edits):
    p = os.path.join(ROOT, rel); s = open(p).read()
    for old, new in edits:
        assert s.count(old) == 1, '%s: anchor not found or ambiguous: %r' % (rel, old[:60])
        s = s.replace(old, new)
    open(p, 'w').write(s); print('geaendert', rel)

# ---- slot 3 instead of 8, and query the GL side after the pointer call
p = os.path.join(ROOT, 'src/osg/VertexArrayState.cpp'); s = open(p).read()
start = s.index('#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)\n        /* FlightGear GLES port: what reaches attribute 8')
end = s.index('#endif\n', start) + len('#endif\n')
s = s[:start] + s[end:]
old = ('        }\n'
       '    }\n'
       '\n'
       '    virtual void enable_and_dispatch(osg::State& state, const osg::Array* new_array)\n'
       '    {\n'
       '        GLExtensions* ext = state.get<GLExtensions>();\n'
       '\n'
       '        ext->glEnableVertexAttribArray( unit );\n'
       '        callVertexAttribPointer(ext, new_array, new_array->getDataPointer());\n')
assert s.count(old) == 1, 'callVertexAttribPointer tail'
s = s.replace(old,
       '        }\n'
       '#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)\n'
       '        /* FlightGear GLES port: what does GL hold for slot 3 (osg_MultiTexCoord0) now? */\n'
       '        if (unit == 3 && ext->glGetVertexAttribiv)\n'
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
       '#endif\n'
       '    }\n'
       '\n'
       '    virtual void enable_and_dispatch(osg::State& state, const osg::Array* new_array)\n'
       '    {\n'
       '        GLExtensions* ext = state.get<GLExtensions>();\n'
       '\n'
       '        ext->glEnableVertexAttribArray( unit );\n'
       '        callVertexAttribPointer(ext, new_array, new_array->getDataPointer());\n')
open(p, 'w').write(s); print('geaendert src/osg/VertexArrayState.cpp')

# ---- every divisor applied through OSG
patch('src/osg/VertexAttribDivisor.cpp', [
('        extensions->glVertexAttribDivisor( _index, _divisor );\n',
 '        extensions->glVertexAttribDivisor( _index, _divisor );\n'
 '        {\n'
 '            static int logged = 0;   /* FlightGear GLES port */\n'
 '            if (logged < 24) { ++logged; OSG_WARN << "VertexAttribDivisor::apply index=" << _index << " divisor=" << _divisor << std::endl; }\n'
 '        }\n'),
])
p = os.path.join(ROOT, 'src/osg/VertexAttribDivisor.cpp'); s = open(p).read()
if '#include <osg/Notify>' not in s:
    s = s.replace('#include <osg/VertexAttribDivisor>\n', '#include <osg/VertexAttribDivisor>\n#include <osg/Notify>\n', 1); open(p, 'w').write(s); print('include src/osg/VertexAttribDivisor.cpp')
print('fertig')

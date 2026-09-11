#!/usr/bin/env python3
"""Seventh round (FlightGear GLES port): diagnostics only - active attribute
locations per linked program, every array dispatch to attribute 8
(osg_MultiTexCoord0), and light values logged on change.
Run after ffp_gles.py .. ffp_gles6.py: python3 ffp_gles7.py [osg-source-root]"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'

def patch(rel, edits):
    p = os.path.join(ROOT, rel); s = open(p).read()
    for old, new in edits:
        assert s.count(old) == 1, '%s: anchor not found or ambiguous: %r' % (rel, old[:60])
        s = s.replace(old, new)
    open(p, 'w').write(s); print('geaendert', rel)

# ---- active attributes after link
p = os.path.join(ROOT, 'src/osg/Program.cpp'); src = open(p).read()
if '#include <sstream>' not in src:
    src = src.replace('#include <osg/Program>\n', '#include <osg/Program>\n#include <sstream>\n', 1); open(p, 'w').write(src); print('include src/osg/Program.cpp')
patch('src/osg/Program.cpp', [
('                _attribInfoMap[reinterpret_cast<char*>(name)] = ActiveVarInfo(loc,type,size);\n'
 '\n'
 '                OSG_INFO << "\\tAttrib \\"" << name << "\\""\n'
 '                         << " loc=" << loc\n'
 '                         << " size=" << size\n'
 '                         << std::endl;\n'
 '            }\n'
 '        }\n',
 '                _attribInfoMap[reinterpret_cast<char*>(name)] = ActiveVarInfo(loc,type,size);\n'
 '\n'
 '                OSG_INFO << "\\tAttrib \\"" << name << "\\""\n'
 '                         << " loc=" << loc\n'
 '                         << " size=" << size\n'
 '                         << std::endl;\n'
 '            }\n'
 '        }\n'
 '#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)\n'
 '        /* FlightGear GLES port: where did the attributes end up? */\n'
 '        {\n'
 '            static int logged = 0;\n'
 '            if (logged < 10)\n'
 '            {\n'
 '                ++logged;\n'
 '                std::ostringstream os;\n'
 '                for (ActiveVarInfoMap::const_iterator it = _attribInfoMap.begin(); it != _attribInfoMap.end(); ++it)\n'
 '                    os << " " << it->first << "=" << it->second._location;\n'
 '                OSG_WARN << "Program attribs [" << _program->getName() << "]:" << os.str() << std::endl;\n'
 '            }\n'
 '        }\n'
 '#endif\n'),
])

# ---- every dispatch to attribute 8 (osg_MultiTexCoord0 alias)
patch('src/osg/VertexArrayState.cpp', [
('    inline void callVertexAttribPointer(GLExtensions* ext, const osg::Array* new_array, const GLvoid * ptr)\n'
 '    {\n',
 '    inline void callVertexAttribPointer(GLExtensions* ext, const osg::Array* new_array, const GLvoid * ptr)\n'
 '    {\n'
 '#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)\n'
 '        /* FlightGear GLES port: what reaches attribute 8 (osg_MultiTexCoord0)? */\n'
 '        if (unit == 8)\n'
 '        {\n'
 '            static int logged = 0;\n'
 '            if (logged < 16)\n'
 '            {\n'
 '                ++logged;\n'
 '                const float* f = (new_array->getDataType() == GL_FLOAT && new_array->getDataPointer()) ? static_cast<const float*>(new_array->getDataPointer()) : 0;\n'
 '                OSG_WARN << "attrib8 dispatch type=0x" << std::hex << new_array->getDataType() << std::dec\n'
 '                         << " size=" << new_array->getDataSize() << " n=" << new_array->getNumElements()\n'
 '                         << " normalize=" << new_array->getNormalize() << " preserve=" << new_array->getPreserveDataType()\n'
 '                         << " ptr=" << ptr << " vbo=" << (new_array->getBufferObject() ? 1 : 0)\n'
 '                         << " first=" << (f ? f[0] : 0.0f) << "," << (f ? f[1] : 0.0f)\n'
 '                         << " glGetError(before)=0x" << std::hex << glGetError() << std::dec << std::endl;\n'
 '            }\n'
 '        }\n'
 '#endif\n'),
])

# ---- light: log on change instead of the first eight calls
patch('src/osg/Light.cpp', [
('    {\n'
 '        static int logged = 0;   /* first frames only */\n'
 '        if (logged < 8) { ++logged; OSG_WARN << "Light::apply light" << _lightnum << " position=" << _position\n'
 '                                            << " eye=" << eyePosition << " ambient=" << _ambient << " diffuse=" << _diffuse << std::endl; }\n'
 '    }\n',
 '    {\n'
 '        static int logged = 0;\n'
 '        static Vec4 lastPos, lastDiffuse, lastAmbient;\n'
 '        if (logged < 40 && (_position != lastPos || _diffuse != lastDiffuse || _ambient != lastAmbient))\n'
 '        {\n'
 '            ++logged; lastPos = _position; lastDiffuse = _diffuse; lastAmbient = _ambient;\n'
 '            OSG_WARN << "Light::apply light" << _lightnum << " position=" << _position\n'
 '                     << " eye=" << eyePosition << " ambient=" << _ambient << " diffuse=" << _diffuse << std::endl;\n'
 '        }\n'
 '    }\n'),
])
print('fertig')

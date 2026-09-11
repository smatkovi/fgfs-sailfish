#!/usr/bin/env python3
"""Tenth round (FlightGear GLES port): where do large drawables put their texture
coordinates?  Logs, for geometry above OSG_GLES_DEBUG_MINVERTS vertices (default
500) and after OSG_GLES_DEBUG_AFTER seconds, which texcoord units and which
vertex-attrib indices carry arrays.
Run after ffp_gles.py .. ffp_gles9.py: python3 ffp_gles10.py [osg-source-root]"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'

p = os.path.join(ROOT, 'src/osg/Geometry.cpp'); s = open(p).read()

old = ('void Geometry::drawVertexArraysImplementation(RenderInfo& renderInfo) const\n'
       '{\n'
       '    State& state = *renderInfo.getState();\n'
       '    VertexArrayState* vas = state.getCurrentVertexArrayState();\n')
assert s.count(old) == 1, 'drawVertexArraysImplementation'
s = s.replace(old,
    'void Geometry::drawVertexArraysImplementation(RenderInfo& renderInfo) const\n'
    '{\n'
    '    State& state = *renderInfo.getState();\n'
    '    VertexArrayState* vas = state.getCurrentVertexArrayState();\n'
    '\n'
    '#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)\n'
    '    /* FlightGear GLES port: terrain tiles are large; where do their texture\n'
    '       coordinates go?  Gated by OSG_GLES_DEBUG_AFTER / OSG_GLES_DEBUG_MINVERTS. */\n'
    '    {\n'
    '        static double after = -1.0;\n'
    '        static unsigned int minVerts = 0;\n'
    '        static osg::Timer_t startTick = osg::Timer::instance()->tick();\n'
    '        static int logged = 0;\n'
    '        if (after < 0.0)\n'
    '        {\n'
    '            const char* a = getenv("OSG_GLES_DEBUG_AFTER");\n'
    '            const char* m = getenv("OSG_GLES_DEBUG_MINVERTS");\n'
    '            after = (a && *a) ? atof(a) : 0.0;\n'
    '            minVerts = (m && *m) ? atoi(m) : 500;\n'
    '        }\n'
    '        const unsigned int numVerts = _vertexArray.valid() ? _vertexArray->getNumElements() : 0;\n'
    '        if (logged < 12 && numVerts >= minVerts &&\n'
    '            osg::Timer::instance()->delta_s(startTick, osg::Timer::instance()->tick()) >= after)\n'
    '        {\n'
    '            ++logged;\n'
    '            std::ostringstream os;\n'
    '            os << "bigGeom verts=" << numVerts << " name=[" << getName() << "]";\n'
    '            os << " texUnits=" << _texCoordList.size();\n'
    '            for (unsigned int unit = 0; unit < _texCoordList.size(); ++unit)\n'
    '            {\n'
    '                const Array* a = _texCoordList[unit].get();\n'
    '                os << " tex" << unit << "=" << (a ? a->getNumElements() : 0);\n'
    '                if (a) os << "(size=" << a->getDataSize() << ",bind=" << a->getBinding() << ")";\n'
    '            }\n'
    '            os << " attribs=" << _vertexAttribList.size();\n'
    '            for (unsigned int i = 0; i < _vertexAttribList.size(); ++i)\n'
    '            {\n'
    '                const Array* a = _vertexAttribList[i].get();\n'
    '                if (a) os << " attr" << i << "=" << a->getNumElements() << "(size=" << a->getDataSize() << ",bind=" << a->getBinding() << ")";\n'
    '            }\n'
    '            os << " normals=" << (_normalArray.valid() ? _normalArray->getNumElements() : 0)\n'
    '               << " colors=" << (_colorArray.valid() ? _colorArray->getNumElements() : 0);\n'
    '            OSG_WARN << os.str() << std::endl;\n'
    '        }\n'
    '    }\n'
    '#endif\n')

for inc in ('#include <osg/Timer>', '#include <sstream>'):
    if inc not in s:
        s = s.replace('#include <osg/Geometry>\n', '#include <osg/Geometry>\n' + inc + '\n', 1)
open(p, 'w').write(s); print('geaendert src/osg/Geometry.cpp')
print('fertig')

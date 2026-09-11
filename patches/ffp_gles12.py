#!/usr/bin/env python3
"""Twelfth round (FlightGear GLES port): fix the crash in setArray.

VertexArrayState::setTexCoordArray()/setVertexAttribArray() index their
dispatcher vectors without a bounds check, and Geometry iterates over the
drawable's own unit count, which can exceed the dispatchers held by the
current VertexArrayState - scene geometry with several texture units and
vertex attributes does exactly that, and the out-of-range read hands a
garbage pointer to setArray().

Two changes: the assign*Dispatcher() calls only ever grow the vectors (so
calling them again is harmless), and Geometry grows them to what the
drawable needs before dispatching.
Run after ffp_gles.py .. ffp_gles11.py: python3 ffp_gles12.py [osg-source-root]"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'

def patch(rel, edits):
    p = os.path.join(ROOT, rel); s = open(p).read()
    for old, new in edits:
        assert s.count(old) == 1, '%s: anchor not found or ambiguous: %r' % (rel, old[:70])
        s = s.replace(old, new)
    open(p, 'w').write(s); print('geaendert', rel)

# ---- grow-only dispatcher vectors
patch('src/osg/VertexArrayState.cpp', [
('void VertexArrayState::assignTexCoordArrayDispatcher(unsigned int numUnits)\n'
 '{\n'
 '    _texCoordArrays.resize(numUnits);\n',
 'void VertexArrayState::assignTexCoordArrayDispatcher(unsigned int numUnits)\n'
 '{\n'
 '    /* FlightGear GLES port: only ever grow.  Shrinking would leave the\n'
 '       drawable\'s higher units without a dispatcher, and setTexCoordArray()\n'
 '       indexes this vector unchecked. */\n'
 '    if (numUnits > _texCoordArrays.size()) _texCoordArrays.resize(numUnits);\n'),
('void VertexArrayState::assignVertexAttribArrayDispatcher(unsigned int numUnits)\n'
 '{\n'
 '    _vertexAttribArrays.resize(numUnits);\n',
 'void VertexArrayState::assignVertexAttribArrayDispatcher(unsigned int numUnits)\n'
 '{\n'
 '    /* FlightGear GLES port: grow only, see assignTexCoordArrayDispatcher(). */\n'
 '    if (numUnits > _vertexAttribArrays.size()) _vertexAttribArrays.resize(numUnits);\n'),
])

# ---- make sure the current VertexArrayState can serve this drawable
patch('src/osg/Geometry.cpp', [
('    for(unsigned int unit=0;unit<_texCoordList.size();++unit)\n'
 '    {\n'
 '        const Array* array = _texCoordList[unit].get();\n'
 '        if (array)\n'
 '        {\n'
 '            vas->setTexCoordArray(state, unit,array);\n'
 '        }\n'
 '    }\n',
 '    /* FlightGear GLES port: the current VertexArrayState may be the global\n'
 '       one, with fewer dispatchers than this drawable has units; setTexCoordArray()\n'
 '       and setVertexAttribArray() would then index out of range. */\n'
 '    if (!_texCoordList.empty()) vas->assignTexCoordArrayDispatcher(_texCoordList.size());\n'
 '    if (handleVertexAttributes && !_vertexAttribList.empty())\n'
 '        vas->assignVertexAttribArrayDispatcher(_vertexAttribList.size());\n'
 '\n'
 '    for(unsigned int unit=0;unit<_texCoordList.size();++unit)\n'
 '    {\n'
 '        const Array* array = _texCoordList[unit].get();\n'
 '        if (array)\n'
 '        {\n'
 '            vas->setTexCoordArray(state, unit,array);\n'
 '        }\n'
 '    }\n'),
])
print('fertig')

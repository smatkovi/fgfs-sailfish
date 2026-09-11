#!/usr/bin/env python3
"""Twenty-first round (FlightGear GLES port): a probe for attribute locations.

The instrument faces of the c172p read texture coordinate (0,0) although the
array is dispatched to attribute slot 3 with data.  Under GLES the shader
finds osg_MultiTexCoord0 wherever the link put it - and effects bind their
own attributes by index, so a collision moves it.  With
OSG_GLES_DEBUG_ATTRIBS=1 every linked program logs its name and each active
attribute with its location, so a collision shows up as
osg_MultiTexCoord0 != 3.

Run after ffp_gles.py .. ffp_gles20.py: python3 ffp_gles21.py [osg-source-root]"""
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

patch('src/osg/Program.cpp', [
('                _attribInfoMap[reinterpret_cast<char*>(name)] = ActiveVarInfo(loc,type,size);\n'
 '\n'
 '                OSG_INFO << "\\tAttrib \\"" << name << "\\""\n',
 '                _attribInfoMap[reinterpret_cast<char*>(name)] = ActiveVarInfo(loc,type,size);\n'
 '\n'
 '#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)\n'
 '                /* FlightGear GLES port, OSG_GLES_DEBUG_ATTRIBS=1 */\n'
 '                {\n'
 '                    static const int probe = (::getenv("OSG_GLES_DEBUG_ATTRIBS") != 0) ? 1 : 0;\n'
 '                    if (probe)\n'
 '                        OSG_WARN << "ATTRIBS program=[" << _program->getName() << "] handle=" << _glProgramHandle\n'
 '                                 << " " << name << " loc=" << loc << " size=" << size\n'
 '                                 << " bound=" << _program->getAttribBindingList().size() << std::endl;\n'
 '                }\n'
 '#endif\n'
 '                OSG_INFO << "\\tAttrib \\"" << name << "\\""\n'),
])
print('fertig')

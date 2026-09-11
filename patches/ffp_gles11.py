#!/usr/bin/env python3
"""Eleventh round (FlightGear GLES port): remove the setArray slot-3 probe.

It indexed _vertexAttribArrays[3] directly, which crashes for geometry whose
dispatcher list is shorter than that - scene geometry with vertex attributes,
unlike the splash screen.  The probe has served its purpose; the attrib3
logging inside callVertexAttribPointer stays.
Run after ffp_gles.py .. ffp_gles10.py: python3 ffp_gles11.py [osg-source-root]"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'

p = os.path.join(ROOT, 'src/osg/VertexArrayState.cpp'); s = open(p).read()
marker = '#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)\n    /* FlightGear GLES port: does slot 3 get an array at all for scene geometry? */'
if marker in s:
    start = s.index(marker)
    end = s.index('#endif\n', start) + len('#endif\n')
    s = s[:start] + s[end:]
    open(p, 'w').write(s)
    print('Sonde entfernt aus src/osg/VertexArrayState.cpp')
else:
    print('Sonde war nicht vorhanden - nichts zu tun')
print('fertig')

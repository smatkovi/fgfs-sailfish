#!/usr/bin/env python3
"""Twenty-ninth round: the fallback program used a uniform nobody sets.

The fallback program from round 18 - the one that draws geometry with no
shader of its own - passed its texture coordinates through
osg_TextureMatrix0.  That uniform is filled by the fixed-function emulation
for converted shaders; for this built-in program nothing sets it, and an
unset uniform is zero, so every fragment sampled the same texel.  That is
what left the c172p's instrument faces blank while their geometry, texture,
attribute slot and coordinates were all correct.

The texture matrix has no business here anyway: the fallback stands in for
geometry that has no effect, and such geometry has no TexMat either.  Pass
the attribute straight through.

Run after ffp_gles.py .. ffp_gles28.py: python3 ffp_gles29.py [osg-source-root]"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'

p = os.path.join(ROOT, 'src/osg/State.cpp')
s = open(p).read()

old = '''            "uniform mat4 osg_TextureMatrix0;\\n"'''
if old not in s:
    print('  schon aktuell')
    raise SystemExit

s = s.replace(old, '')
old2 = '''            "  fgfs_tc = (osg_TextureMatrix0 * osg_MultiTexCoord0).st;\\n"'''
assert s.count(old2) == 1, 'Anker Koordinatenzeile'
s = s.replace(old2, '''            /* No texture matrix: this program stands in for geometry that
               has no effect, so there is no TexMat either - and an unset
               uniform is a zero matrix, which put every fragment on the
               same texel. */
            "  fgfs_tc = osg_MultiTexCoord0.st;\\n"''')
open(p, 'w').write(s)
print('geaendert src/osg/State.cpp')
print('fertig')

#!/usr/bin/env python3
"""Twentieth round (FlightGear GLES port): textures whose size is not a power
of two.

ES 2 has no mipmaps and no repeat for such textures - sampling them returns
black.  Four of the c172p's panel textures are affected (the breaker
switches, the fuel selector and two light maps), and those instruments
stayed black.  applyTexParameters now clamps a non-power-of-two texture to
the edge and drops it to LINEAR under GLES, which is what ES allows and what
a panel texture wants anyway.

Run after ffp_gles.py .. ffp_gles19.py: python3 ffp_gles20.py [osg-source-root]"""
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

patch('src/osg/Texture.cpp', [
('    WrapMode ws = _wrap_s, wt = _wrap_t, wr = _wrap_r;\n'
 '\n'
 '    // GL_IBM_texture_mirrored_repeat, fall-back REPEAT\n',
 '    WrapMode ws = _wrap_s, wt = _wrap_t, wr = _wrap_r;\n'
 '\n'
 '#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)\n'
 '    /* FlightGear GLES port: ES 2 has neither mipmaps nor repeat for a\n'
 '       texture whose size is not a power of two - sampling one returns\n'
 '       black, which is how four of the c172p panel textures ended up.\n'
 '       Clamp to the edge and sample linearly instead; for panel artwork\n'
 '       that is what is wanted anyway. */\n'
 '    {\n'
 '        const osg::Image* img = getImage(0);\n'
 '        if (img)\n'
 '        {\n'
 '            const int w = img->s(), h = img->t();\n'
 '            const bool pot = w > 0 && h > 0 && (w & (w - 1)) == 0 && (h & (h - 1)) == 0;\n'
 '            if (!pot)\n'
 '            {\n'
 '                ws = CLAMP_TO_EDGE;\n'
 '                wt = CLAMP_TO_EDGE;\n'
 '                wr = CLAMP_TO_EDGE;\n'
 '                if (_min_filter != NEAREST) const_cast<Texture*>(this)->_min_filter = LINEAR;\n'
 '            }\n'
 '        }\n'
 '    }\n'
 '#endif\n'
 '\n'
 '    // GL_IBM_texture_mirrored_repeat, fall-back REPEAT\n'),
])
print('fertig')

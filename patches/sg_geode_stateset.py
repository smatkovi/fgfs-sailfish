#!/usr/bin/env python3
"""SimGear: build the effect from the drawable's state set when the geode has
none.

MakeEffectVisitor::apply(Geode&) returns early when the geode carries no
state set.  No state set means no parameters, so texture[0] stays empty and
the technique binds SimGear's white placeholder - which is exactly what the
c172p instrument faces got (2295 such geodes in one run, every one of them
with a single drawable).  Multiplied by the dark lightmap that comes out
black, while the needles, which are separate geometry, stayed visible.  On
the desktop it goes unnoticed because the fixed-function technique takes the
texture straight off the drawable.

The AC3D loader puts the material on the Geometry, not on the Geode, so the
state set is one level down.  When the geode has none and holds exactly one
drawable, use that drawable's.  With more than one drawable the choice would
be arbitrary - the effect is per geode, not per drawable - so that case is
logged rather than guessed at.

  python3 sg_geode_stateset.py [simgear-source-root]
"""
import os
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/simgear-2020.3.19')
p = os.path.join(ROOT, 'simgear/scene/model/model.cxx')
s = open(p).read()

if 'state set one level down' in s:
    print('  schon aktuell')
    raise SystemExit

old = '''    osg::StateSet* ss = geode.getStateSet();
'''
new = '''    osg::StateSet* ss = geode.getStateSet();
    if (!ss) {
        /* The AC3D loader puts the material on the Geometry, so look for the
           state set one level down.  Only with a single drawable: the effect
           belongs to the geode, so with several the choice would be
           arbitrary. */
        const unsigned int nd = geode.getNumDrawables();
        if (nd == 1) {
            ss = geode.getDrawable(0)->getStateSet();
        } else if (nd > 1) {
            unsigned int withState = 0;
            for (unsigned int i = 0; i < nd; ++i)
                if (geode.getDrawable(i)->getStateSet()) ++withState;
            if (withState)
                SG_LOG(SG_INPUT, SG_WARN, "makeEffect: geode [" << geode.getName()
                       << "] has no state set but " << withState << " of its "
                       << nd << " drawables do; effects are per geode, so none is used");
        }
    }
'''
assert s.count(old) == 1, 'Anker fehlt oder mehrdeutig'
s = s.replace(old, new)
open(p, 'w').write(s)
print('geaendert simgear/scene/model/model.cxx')

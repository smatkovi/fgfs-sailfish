#!/usr/bin/env python3
"""SimGear probe: which technique is which, and which one the geode gets.

The pass probe (P31) numbers an effect's techniques 0..6 and finds that the
one chosen for the Katana canopy carries neither a program nor a blend
state - but no technique in model-default, model-combined or
model-combined-deferred looks like that, and nothing in SimGear inserts a
technique.  So the index alone does not say what technique 0 is.  This
logs, with SG_TEXPARAM_PROBE=1, the property index n and path of every
technique as it is built, keyed by the effect's address, and puts the same
address on the PASSPROBE and TECHPROBE lines so the three can be joined:
build order -> pass state -> the index chosen at cull time.

Insert-only after unique anchors; the TECHPROBE line gets a cap so a
minute of culling does not fill the disk.  Idempotent.
  python3 sg_tniqbuild_probe.py [simgear-source-root]"""
import sys, os

ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/simgear-2020.3.19'
eff = os.path.join(ROOT, 'simgear/scene/material/Effect.cxx')
mdl = os.path.join(ROOT, 'simgear/scene/model/model.cxx')

s = open(eff).read()
if 'TNIQBUILD' not in s:
    anchor = '''    Technique* tniq = new Technique;
    effect->techniques.push_back(tniq);
'''
    assert s.count(anchor) == 1, 'buildTechnique anchor'
    block = '''    {
        static const int probe = (::getenv("SG_TEXPARAM_PROBE") != 0) ? 1 : 0;
        if (probe)
            SG_LOG(SG_INPUT, SG_ALERT, "TNIQBUILD effect=" << (const void*)effect
                   << " idx=" << (effect->techniques.size() - 1)
                   << " n=" << prop->getIndex()
                   << " path=[" << prop->getPath() << "]"
                   << " predicate=" << (prop->getChild("predicate") ? 1 : 0)
                   << " scheme=[" << prop->getStringValue("scheme") << "]"
                   << " passes=" << prop->getChildren("pass").size());
    }
'''
    s = s.replace(anchor, anchor + block, 1)
    old = 'SG_LOG(SG_GL, SG_ALERT, "TECHPROBE effect=[" << getName() << "] technique "'
    assert s.count(old) == 1, 'TECHPROBE anchor'
    s = s.replace(old, 'SG_LOG(SG_GL, SG_ALERT, "TECHPROBE effect=" << (const void*)this << " technique "', 1)
    old2 = '        if (probe)\n            SG_LOG(SG_GL, SG_ALERT, "TECHPROBE effect="'
    assert s.count(old2) == 1, 'TECHPROBE if anchor'
    s = s.replace(old2, '        static int logged = 0;\n        if (probe && logged++ < 400000)\n            SG_LOG(SG_GL, SG_ALERT, "TECHPROBE effect="', 1)
    open(eff, 'w').write(s); print('Effect.cxx: TNIQBUILD eingefuegt, TECHPROBE mit Adresse')
else:
    print('Effect.cxx schon aktuell')

m = open(mdl).read()
old = '"PASSPROBE alpha=" << alpha'
if old in m:
    m = m.replace(old, '"PASSPROBE effect=" << (const void*)effect << " alpha=" << alpha', 1)
    open(mdl, 'w').write(m); print('model.cxx: PASSPROBE mit Adresse')
else:
    print('model.cxx schon aktuell' if 'PASSPROBE effect=' in m else 'PASSPROBE-Anker fehlt!')

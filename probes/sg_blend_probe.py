#!/usr/bin/env python3
"""Report what SG derives for blend/active per geode, next to the existing
SG_TEXPARAM_PROBE output.

Why: cockpit glass renders opaque under FlightGear while the very same model
blends correctly in plain OSG (BEFUNDE.md, P24/P25).  Geometry, texture
coordinates and texel are all confirmed right; what is missing is the
blending.  SimGear turns a model's state set into effect parameters and sets
blend/active only when it finds a BlendFunc (Effect.cxx:1465-1475); the
AC3D loader attaches one for translucent materials (ac3d.cpp:251-259).  One
of those two statements does not hold at run time, and this says which.

Idempotent.  Run: python3 sg_blend_probe.py [simgear-source-root]"""
import sys, os

ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/simgear-2020.3.19'

p = os.path.join(ROOT, 'simgear/scene/model/model.cxx')
s = open(p).read()

old = '''    SGPropertyNode_ptr ssRoot = new SGPropertyNode;
    makeParametersFromStateSet(ssRoot, ss);'''

new = '''    SGPropertyNode_ptr ssRoot = new SGPropertyNode;
    makeParametersFromStateSet(ssRoot, ss);
    {
        /* What did the state set actually yield?  blend/active decides
           whether the shaderless fallback technique switches blending on,
           and with it whether transparent materials stay transparent. */
        static const int probe = (::getenv("SG_TEXPARAM_PROBE") != 0) ? 1 : 0;
        if (probe) {
            const SGPropertyNode* b = ssRoot->getNode("blend");
            const SGPropertyNode* a = b ? b->getNode("active") : 0;
            const SGPropertyNode* rh = ssRoot->getNode("rendering-hint");
            SG_LOG(SG_INPUT, SG_ALERT, "BLENDPROBE geode=[" << geode.getName()
                   << "] blend/active=" << (a ? (a->getBoolValue() ? "true" : "false")
                                              : "absent")
                   << " rendering-hint=" << (rh ? rh->getStringValue() : "absent")
                   << " blendfunc=" << (ss->getAttribute(osg::StateAttribute::BLENDFUNC) ? "yes" : "no")
                   << " modeBLEND=" << (int)ss->getMode(GL_BLEND)
                   << " material=" << (ss->getAttribute(osg::StateAttribute::MATERIAL) ? "yes" : "no"));
        }
    }'''

if new in s:
    print('  schon aktuell')
    raise SystemExit
if old not in s:
    raise SystemExit('Anker nicht gefunden - Quelle abweichend?')

s = s.replace(old, new, 1)

# getStateAttribute lebt in Effect.hxx; BlendFunc/Material brauchen ihre Header.
need = [('#include <osg/BlendFunc>', '#include <osg/BlendFunc>\n'),
        ('#include <osg/Material>', '#include <osg/Material>\n')]
for token, line in need:
    if token not in s:
        idx = s.index('#include <osg/')
        s = s[:idx] + line + s[idx:]

open(p, 'w').write(s)
print('geaendert simgear/scene/model/model.cxx')
print('fertig')

#!/usr/bin/env python3
"""SimGear probe: which path the cull visitor takes for translucent geodes.

The draw probe (P34) shows the Katana canopy reaching the GPU through the
shaderless fallback with GL_BLEND inherited off, while the lamp glass of
the same model goes through the ubershader with blending - and neither the
technique probe nor the pass probe ever saw the canopy's effect at cull
time.  EffectCullVisitor::apply(Geode&) has four exits: not an EffectGeode,
no effect, no valid technique, or a technique.  This logs which one, for
geodes whose first geometry carries an overall colour with alpha < 0.99,
with the effect address, the technique index and the geode's parent chain.
SG_TEXPARAM_PROBE=1, capped.  Insert-only, idempotent."""
import os, sys
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/simgear-2020.3.19'
p = os.path.join(ROOT, 'simgear/scene/material/EffectCullVisitor.cxx')
s = open(p).read()
if 'CULLPROBE' in s:
    print('schon drin'); raise SystemExit
old = '''    EffectGeode *eg = dynamic_cast<EffectGeode*>(&node);
    if (!eg) {
        CullVisitor::apply(node);
        return;
    }
    Effect* effect = eg->getEffect();
    Technique* technique = 0;
    if (!effect) {
        CullVisitor::apply(node);
        return;
    } else if (!(technique = effect->chooseTechnique(&getRenderInfo(), _effScheme))) {
        return;
    }
'''
assert s.count(old) == 1, 'Anker'
new = '''    EffectGeode *eg = dynamic_cast<EffectGeode*>(&node);
    /* probe: translucent geode? (overall colour alpha < 0.99, as the AC3D
       loader leaves it) */
    static const int cullProbe = (::getenv("SG_TEXPARAM_PROBE") != 0) ? 1 : 0;
    static int cullLogged = 0;
    bool probeThis = false;
    std::string probeColor;
    if (cullProbe && cullLogged < 2000) {
        /* any translucent drawable, or a name with "vitre" anywhere up the
           chain (the P35 filter on drawable 0 alone never fired) */
        for (unsigned int i = 0; i < node.getNumDrawables(); ++i) {
            const osg::Geometry* g = node.getDrawable(i)->asGeometry();
            const osg::Vec4Array* ca = g ? dynamic_cast<const osg::Vec4Array*>(g->getColorArray()) : 0;
            std::ostringstream c;
            c << " d" << i << "=" << (g ? "geom" : node.getDrawable(i)->className())
              << "/" << (g && g->getColorArray() ? g->getColorArray()->className() : "nocolor")
              << "/" << (ca ? (int)ca->size() : -1) << "/" << (ca && ca->size() ? (*ca)[0].a() : -1.0f);
            probeColor += c.str();
            if (ca && ca->size() == 1 && (*ca)[0].a() < 0.99f) probeThis = true;
        }
        const osg::Node* n = &node;
        for (int d = 0; n && d < 6; ++d) {
            if (n->getName().find("vitre") != std::string::npos) probeThis = true;
            n = n->getNumParents() ? n->getParent(0) : 0;
        }
    }
    if (probeThis) {
        ++cullLogged;
        std::ostringstream pos;
        pos << "CULLPROBE geode=" << (const void*)&node << " eg=" << (eg ? 1 : 0)
           << " effect=" << (eg ? (const void*)eg->getEffect() : 0)
           << " scheme=[" << _effScheme << "] mask=0x" << std::hex << node.getNodeMask() << std::dec
           << " ss=" << (node.getStateSet() ? 1 : 0)
           << " dss=" << (node.getNumDrawables() && node.getDrawable(0)->getStateSet() ? 1 : 0)
           << " nd=" << node.getNumDrawables() << probeColor;
        if (eg && eg->getEffect()) {
            Technique* t = eg->getEffect()->chooseTechnique(&getRenderInfo(), _effScheme);
            int idx = -1;
            for (size_t i = 0; i < eg->getEffect()->techniques.size(); ++i)
                if (eg->getEffect()->techniques[i].get() == t) idx = (int)i;
            pos << " technique=" << idx;
        }
        const osg::Node* n = node.getNumParents() ? node.getParent(0) : 0;
        for (int d = 0; n && d < 5; ++d) {
            pos << " <" << n->className() << ":" << n->getName().substr(0, 20);
            n = n->getNumParents() ? n->getParent(0) : 0;
        }
        SG_LOG(SG_GL, SG_ALERT, pos.str());
    }
    if (!eg) {
        CullVisitor::apply(node);
        return;
    }
    Effect* effect = eg->getEffect();
    Technique* technique = 0;
    if (!effect) {
        CullVisitor::apply(node);
        return;
    } else if (!(technique = effect->chooseTechnique(&getRenderInfo(), _effScheme))) {
        return;
    }
'''
s = s.replace(old, new, 1)
for inc in ('#include <osg/Geometry>', '#include <sstream>'):
    if inc not in s:
        i = s.index('#include <'); s = s[:i] + inc + '\n' + s[i:]
open(p, 'w').write(s); print('Cull-Sonde eingefuegt')

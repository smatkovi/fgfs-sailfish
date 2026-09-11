#!/usr/bin/env python3
"""SimGear probe: who leaves the canopy's EffectGeode without an effect.

P36 (cull probe): the Katana canopy geodes vitres/intvitres are
EffectGeodes with effect == 0 at cull time, so they fall to the plain
CullVisitor path - shaderless fallback, GL_BLEND inherited off - while
the frame around them carries an effect.  Either makeEffect returned
null for them (silently: failures go through reportFailure, not SG_LOG)
or something cleared the effect afterwards.  Log both: every
EffectGeode::setEffect(0) with the geode address, and every makeEffect
result in MakeEffectVisitor for translucent geodes, with the geode
address, so the cull probe's addresses can be joined.  SG_TEXPARAM_PROBE=1.
Insert-only, idempotent."""
import os, sys
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/simgear-2020.3.19'
eg = os.path.join(ROOT, 'simgear/scene/material/EffectGeode.cxx')
s = open(eg).read()
if 'SETEFFECT' not in s:
    old = '''void EffectGeode::setEffect(Effect* effect)
{
    _effect = effect;
'''
    assert s.count(old) == 1, 'setEffect anchor'
    new = '''void EffectGeode::setEffect(Effect* effect)
{
    {
        static const int probe = (::getenv("SG_TEXPARAM_PROBE") != 0) ? 1 : 0;
        static int logged = 0;
        if (probe && !effect && logged++ < 500)
            SG_LOG(SG_INPUT, SG_ALERT, "SETEFFECT null geode=" << (const void*)this
                   << " had=" << (const void*)_effect.get()
                   << " parent=[" << (getNumParents() ? getParent(0)->getName().substr(0, 24) : std::string("-")) << "]");
    }
    _effect = effect;
'''
    s = s.replace(old, new, 1)
    if '#include <simgear/debug/logstream.hxx>' not in s:
        i = s.index('#include <'); s = s[:i] + '#include <simgear/debug/logstream.hxx>\n' + s[i:]
    open(eg, 'w').write(s); print('EffectGeode.cxx: SETEFFECT eingefuegt')
else:
    print('EffectGeode.cxx schon aktuell')

mdl = os.path.join(ROOT, 'simgear/scene/model/model.cxx')
m = open(mdl).read()
if 'MAKEEFFECT' not in m:
    anchor = '    Effect* effect = makeEffect(effectRoot, true, _options.get(), _modelPath);\n'
    assert m.count(anchor) == 1, 'makeEffect anchor'
    block = '''    {
        static const int probe = (::getenv("SG_TEXPARAM_PROBE") != 0) ? 1 : 0;
        const osg::Material* pm = dynamic_cast<const osg::Material*>(ss->getAttribute(osg::StateAttribute::MATERIAL));
        const float palpha = pm ? pm->getDiffuse(osg::Material::FRONT_AND_BACK).a() : -1.0f;
        if (probe && (!effect || (palpha >= 0.0f && palpha < 0.99f)))
            SG_LOG(SG_INPUT, SG_ALERT, "MAKEEFFECT geode=" << (const void*)&geode
                   << " alpha=" << palpha << " effect=" << (const void*)effect
                   << " inherits=[" << effectRoot->getStringValue("inherits-from", "-") << "]"
                   << " parent=[" << (geode.getNumParents() ? geode.getParent(0)->getName().substr(0, 24) : std::string("-")) << "]"
                   << " isEG=" << (dynamic_cast<EffectGeode*>(&geode) ? 1 : 0));
    }
'''
    m = m.replace(anchor, anchor + block, 1)
    open(mdl, 'w').write(m); print('model.cxx: MAKEEFFECT eingefuegt')
else:
    print('model.cxx schon aktuell')

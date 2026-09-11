#!/usr/bin/env python3
"""SimGear: an aircraft effect must not vanish because one shader is missing.

With compositor support SimGear rewrites every shader path "Shaders/x" to
"Compositor/Shaders/x" and gives up if that file does not exist.  Aircraft
effects were written against the classic tree: the Katana's canopy effect
(glassrain.eff) asks for Shaders/glass-ALS.vert, which is in fgdata/Shaders
but not in fgdata/Compositor/Shaders.  The technique build throws, makeEffect
returns null, and the geode is left as an EffectGeode without an effect and
without its state set - so it is drawn through the plain cull path: no
blending, no transparent bin, an opaque canopy (BEFUNDE.md, P36/P37).  The
failure is only reported through reportFailure, which ends in a GUI dialog
this port never shows.

Two changes, both in Effect.cxx:
  1. If the Compositor/ path is not found, look for the shader under its
     original name before giving up - the classic location the effect was
     written for.
  2. A technique that cannot be built is dropped, with the reason logged,
     and the remaining techniques are kept.  Only when none is left does the
     effect fail as before.  For the canopy that leaves technique n=9, the
     fixed-function one, which carries the blend state.

Idempotent.  python3 sg_shader_fallback.py [simgear-source-root]"""
import os, sys
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/simgear-2020.3.19'
p = os.path.join(ROOT, 'simgear/scene/material/Effect.cxx')
s = open(p).read()
changed = False

old1 = '''        string fileName = SGModelLib::findDataFile(shaderName, options);
        if (fileName.empty())
        {
            simgear::reportFailure(simgear::LoadFailure::NotFound, simgear::ErrorCode::LoadEffectsShaders,
                                   "Couldn't locate shader:" + shaderName, sg_location{shaderName});
'''
new1 = '''        string fileName = SGModelLib::findDataFile(shaderName, options);
        /* The Compositor/ tree only holds the shaders FGData itself ships;
           aircraft effects name shaders in the classic tree, so look there
           before declaring the shader missing. */
        if (fileName.empty() && shaderName != shaderKey.first)
        {
            fileName = SGModelLib::findDataFile(shaderKey.first, options);
            if (!fileName.empty())
                SG_LOG(SG_INPUT, SG_INFO, "Shader " << shaderName
                       << " not found, using classic " << shaderKey.first);
        }
        if (fileName.empty())
        {
            simgear::reportFailure(simgear::LoadFailure::NotFound, simgear::ErrorCode::LoadEffectsShaders,
                                   "Couldn't locate shader:" + shaderName, sg_location{shaderName});
'''
if new1 not in s:
    assert s.count(old1) == 1, 'shader lookup anchor'
    s = s.replace(old1, new1, 1); changed = True

old2 = '''    PropertyList tniqList = root->getChildren("technique");
    for (const auto& tniq : tniqList) {
        buildTechnique(this, tniq, options);
    }
'''
new2 = '''    PropertyList tniqList = root->getChildren("technique");
    for (const auto& tniq : tniqList) {
        /* One technique that cannot be built (a shader this data tree does
           not have, say) used to take the whole effect down with it, and
           with the effect the geode's state set: the geometry then drew
           with no blending and no texture at all.  Keep what can be built;
           the fixed-function technique needs no shader and is always among
           them in the stock effects. */
        const size_t before = techniques.size();
        try {
            buildTechnique(this, tniq, options);
        } catch (BuilderException& e) {
            techniques.resize(before);
            SG_LOG(SG_INPUT, SG_WARN, "Effect " << getName() << ": dropping technique "
                   << tniq->getIndex() << ": " << e.getFormattedMessage());
        }
    }
    if (techniques.empty() && !tniqList.empty())
        throw BuilderException("no technique of this effect could be built");
'''
if new2 not in s:
    assert s.count(old2) == 1, 'realizeTechniques anchor'
    s = s.replace(old2, new2, 1); changed = True

if changed:
    open(p, 'w').write(s); print('geaendert simgear/scene/material/Effect.cxx')
else:
    print('  schon aktuell')

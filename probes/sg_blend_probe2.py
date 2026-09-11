# Insert-only after makeParametersFromStateSet(): log what it produced, at
# the CORRECT path (parameters/blend/...), plus the material's diffuse alpha
# so the transparent geodes are identifiable without names.
import os
p='/home/mersdk/simgear-2020.3.19/simgear/scene/model/model.cxx'
s=open(p).read()
anchor='''    SGPropertyNode_ptr ssRoot = new SGPropertyNode;
    makeParametersFromStateSet(ssRoot, ss);
'''
assert s.count(anchor)==1, 'Anker'
block='''    if (::getenv("SG_TEXPARAM_PROBE")) {
        const SGPropertyNode* pa = ssRoot->getNode("parameters/blend/active");
        const SGPropertyNode* pm = ssRoot->getNode("parameters/blend/mode");
        const SGPropertyNode* rh = ssRoot->getNode("parameters/rendering-hint");
        const osg::Material* mat = dynamic_cast<const osg::Material*>(
            ss->getAttribute(osg::StateAttribute::MATERIAL));
        const float alpha = mat ? mat->getDiffuse(osg::Material::FRONT_AND_BACK).a() : -1.0f;
        SG_LOG(SG_INPUT, SG_ALERT, "BLENDPROBE2 alpha=" << alpha
               << " blendfunc=" << (ss->getAttribute(osg::StateAttribute::BLENDFUNC) ? 1 : 0)
               << " modeBLEND=" << (int)ss->getMode(GL_BLEND)
               << " p.active=" << (pa ? (pa->getBoolValue() ? "true" : "false") : "absent")
               << " p.mode=" << (pm ? (pm->getBoolValue() ? "true" : "false") : "absent")
               << " p.hint=" << (rh ? rh->getStringValue() : "absent")
               << " drawables=" << geode.getNumDrawables());
    }
'''
if 'BLENDPROBE2' not in s:
    for inc in ('#include <osg/BlendFunc>','#include <osg/Material>'):
        if inc not in s:
            i=s.index('#include <osg/'); s=s[:i]+inc+'\n'+s[i:]
    open(p,'w').write(s.replace(anchor, anchor+block, 1)); print('Sonde eingefuegt')
else: print('schon drin')

# Insert-only after makeEffect(): what does the built effect's first
# technique/pass carry for GL_BLEND? Only for transparent geodes.
import os
p='/home/mersdk/simgear-2020.3.19/simgear/scene/model/model.cxx'
s=open(p).read()
anchor='    Effect* effect = makeEffect(effectRoot, true, _options.get(), _modelPath);\n'
assert s.count(anchor)==1, 'Anker'
block='''    if (::getenv("SG_TEXPARAM_PROBE") && effect) {
        const osg::Material* mat = dynamic_cast<const osg::Material*>(
            ss->getAttribute(osg::StateAttribute::MATERIAL));
        const float alpha = mat ? mat->getDiffuse(osg::Material::FRONT_AND_BACK).a() : -1.0f;
        if (alpha >= 0.0f && alpha < 0.99f) {
            for (size_t ti = 0; ti < effect->techniques.size(); ++ti) {
                Technique* t = effect->techniques[ti].get();
                for (int pi = 0; pi < t->passes.size(); ++pi) {
                    const osg::StateSet* ps = t->passes[pi].get();
                    SG_LOG(SG_INPUT, SG_ALERT, "PASSPROBE alpha=" << alpha
                           << " technique=" << ti << " pass=" << pi
                           << " modeBLEND=" << (ps ? (int)ps->getMode(GL_BLEND) : -1)
                           << " blendfunc=" << (ps && ps->getAttribute(osg::StateAttribute::BLENDFUNC) ? 1 : 0)
                           << " hint=" << (ps ? ps->getRenderingHint() : -1)
                           << " program=" << (ps && ps->getAttribute(osg::StateAttribute::PROGRAM) ? 1 : 0));
                }
            }
        }
    }
'''
if 'PASSPROBE' not in s:
    open(p,'w').write(s.replace(anchor, anchor+block, 1)); print('Pass-Sonde eingefuegt')
else: print('schon drin')

# Insert-only at the proven anchor: dump the state-set stack for GL_BLEND.
import os
p='/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5/src/osg/State.cpp'
s=open(p).read()
anchor='    const bool textured = getLastAppliedTextureAttribute(0, StateAttribute::TEXTURE) != 0;\n'
assert s.count(anchor)==1, 'Anker'
block='''    if (::getenv("FGFS_GLASS_PROBE"))
    {
        static int logged = 0;
        if (logged < 4000)
        {
            ++logged;
            unsigned int tid = 0;
            const StateAttribute* sa = getLastAppliedTextureAttribute(0, StateAttribute::TEXTURE);
            const Texture* tx = dynamic_cast<const Texture*>(sa);
            const Texture::TextureObject* to = tx ? tx->getTextureObject(getContextID()) : 0;
            if (to) tid = to->id();
            GLboolean be = GL_FALSE; glGetBooleanv(GL_BLEND, &be);
            std::ostringstream os;
            os << "STACKPROBE texid=" << tid << " gl=" << (be ? 1 : 0)
               << " state=" << (getLastAppliedMode(GL_BLEND) ? 1 : 0)
               << " depth=" << _stateStateStack.size() << " stack=";
            for (StateSetStack::const_iterator it = _stateStateStack.begin(); it != _stateStateStack.end(); ++it)
            {
                const StateSet* ss = *it;
                os << "[m" << (int)ss->getMode(GL_BLEND)
                   << (ss->getAttribute(StateAttribute::BLENDFUNC) ? "b" : "-")
                   << (ss->getAttribute(StateAttribute::PROGRAM) ? "P" : "-")
                   << "h" << ss->getRenderingHint() << "]";
            }
            OSG_WARN << os.str() << std::endl;
        }
    }
'''
if 'STACKPROBE' not in s:
    open(p,'w').write(s.replace(anchor, anchor+block, 1)); print('Stapel-Sonde eingefuegt')
else: print('schon drin')

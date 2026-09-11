# Insert-only: name every state set on the stack by its parent node, plus
# the viewport, at the fallback binding.
import os
p='/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5/src/osg/State.cpp'
s=open(p).read()
anchor='    const bool textured = getLastAppliedTextureAttribute(0, StateAttribute::TEXTURE) != 0;\n'
assert s.count(anchor)==1, 'Anker'
block='''    if (::getenv("FGFS_GLASS_PROBE"))
    {
        static int logged = 0;
        if (logged < 3000)
        {
            ++logged;
            unsigned int tid = 0;
            const StateAttribute* sa = getLastAppliedTextureAttribute(0, StateAttribute::TEXTURE);
            const Texture* tx = dynamic_cast<const Texture*>(sa);
            const Texture::TextureObject* to = tx ? tx->getTextureObject(getContextID()) : 0;
            if (to) tid = to->id();
            std::ostringstream os;
            os << "OWNERPROBE texid=" << tid;
            if (getCurrentViewport())
                os << " vp=" << (int)getCurrentViewport()->width() << "x" << (int)getCurrentViewport()->height();
            os << " |";
            for (StateSetStack::const_iterator it = _stateStateStack.begin(); it != _stateStateStack.end(); ++it)
            {
                const StateSet* ss = *it;
                os << " [m" << (int)ss->getMode(GL_BLEND)
                   << (ss->getAttribute(StateAttribute::PROGRAM) ? "P" : "-");
                const StateSet::ParentList& pl = ss->getParents();
                if (!pl.empty() && pl[0])
                {
                    os << " " << pl[0]->className();
                    const std::string& n = pl[0]->getName();
                    if (!n.empty()) os << ":" << n.substr(0, 28);
                }
                const std::string& sn = ss->getName();
                if (!sn.empty()) os << " ss:" << sn.substr(0, 20);
                os << "]";
            }
            OSG_WARN << os.str() << std::endl;
        }
    }
'''
if 'OWNERPROBE' not in s:
    open(p,'w').write(s.replace(anchor, anchor+block, 1)); print('Besitzer-Sonde eingefuegt')
else: print('schon drin')

# Insert-only, after the proven unique anchor. Logs what State believes about
# GL_BLEND next to what GL reports, keyed by texture object id.
import os
p='/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5/src/osg/State.cpp'
s=open(p).read()
anchor='    const bool textured = getLastAppliedTextureAttribute(0, StateAttribute::TEXTURE) != 0;\n'
assert s.count(anchor)==1, 'Anker'
block='''    if (::getenv("FGFS_GLASS_PROBE"))
    {
        static int logged = 0;
        if (logged < 6000)
        {
            ++logged;
            unsigned int tid = 0;
            const StateAttribute* sa =
                getLastAppliedTextureAttribute(0, StateAttribute::TEXTURE);
            const Texture* tx = dynamic_cast<const Texture*>(sa);
            const Texture::TextureObject* to = tx ? tx->getTextureObject(getContextID()) : 0;
            if (to) tid = to->id();
            GLboolean be = GL_FALSE;
            glGetBooleanv(GL_BLEND, &be);
            /* what State thinks it last applied, versus what GL says */
            const bool cached = getLastAppliedMode(GL_BLEND);
            OSG_WARN << "CACHEPROBE texid=" << tid << " gl=" << (be ? 1 : 0)
                     << " state=" << (cached ? 1 : 0) << std::endl;
        }
    }
'''
if 'CACHEPROBE' not in s:
    open(p,'w').write(s.replace(anchor, anchor+block, 1)); print('Sonde C eingefuegt')
else: print('schon drin')

# Insert-only: at every fallback binding, log the bound texture's GL object
# id and the blend state.  Keyed by object id, not image file name - the
# aircraft textures have their image freed after upload, so the name is gone
# by draw time (P27).  Removal = restore State.cpp.beforeprobe.
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
            OSG_WARN << "GLASSPROBE texid=" << tid << " blend=" << (be ? 1 : 0) << std::endl;
        }
    }
'''
if 'GLASSPROBE' not in s:
    open(p,'w').write(s.replace(anchor, anchor+block, 1)); print('Sonde B eingefuegt')
else: print('schon drin')

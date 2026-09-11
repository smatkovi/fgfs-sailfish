# Insert-only: at first upload, while the image still exists, log the GL
# texture object id next to the file name.  Joined offline with GLASSPROBE.
import os
p='/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5/src/osg/Texture2D.cpp'
s=open(p).read()
anchor='''            applyTexImage2D_load(state,GL_TEXTURE_2D,image.get(),
                                 _textureWidth, _textureHeight, _numMipmapLevels);

            textureObject->setAllocated(true);
'''
assert s.count(anchor)==1, 'Anker'
block='''            if (::getenv("FGFS_GLASS_PROBE"))
                OSG_WARN << "TEXID id=" << textureObject->id() << " file=["
                         << image->getFileName() << "]" << std::endl;
'''
if 'TEXID id=' not in s:
    open(p,'w').write(s.replace(anchor, anchor+block, 1)); print('Sonde A eingefuegt')
else: print('schon drin')

import sys, os
ROOT='/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'
p=os.path.join(ROOT,'src/osg/State.cpp')
s=open(p).read()
old_start='        static const int bprobe = (::getenv("FGFS_BLEND_PROBE") != 0) ? 1 : 0;'
i=s.find(old_start)
assert i>=0, 'alte Sonde nicht gefunden'
j=s.find('    }', s.find('std::endl;', i))+6
new='''        static const int bprobe = (::getenv("FGFS_BLEND_PROBE") != 0) ? 1 : 0;
        static int blogged = 0;
        if (bprobe && blogged < 600)
        {
            ++blogged;
            /* Which surface is this?  The first two dozen fallback bindings
               of a frame are the sky dome and the panel, not the canopy -
               without the texture name the sample says nothing about the
               drawable one is actually asking about. */
            std::string texName;
            const StateAttribute* sa = getLastAppliedTextureAttribute(0, StateAttribute::TEXTURE);
            const Texture* t = dynamic_cast<const Texture*>(sa);
            const Image* img = t ? t->getImage(0) : 0;
            if (img) texName = img->getFileName();
            std::string::size_type sl = texName.find_last_of('/');
            if (sl != std::string::npos) texName = texName.substr(sl + 1);

            GLboolean be = GL_FALSE;
            glGetBooleanv(GL_BLEND, &be);
            OSG_WARN << "BLENDSTATE tex=[" << texName << "] textured="
                     << (textured ? 1 : 0) << " GL_BLEND=" << (be ? 1 : 0)
                     << std::endl;
        }
    }'''
s = s[:i] + new + s[j:]
open(p,'w').write(s)
print('Sonde erweitert')

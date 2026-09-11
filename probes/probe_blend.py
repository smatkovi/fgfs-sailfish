import sys, os
ROOT='/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'
p=os.path.join(ROOT,'src/osg/State.cpp')
s=open(p).read()
anchor='''    const bool textured = getLastAppliedTextureAttribute(0, StateAttribute::TEXTURE) != 0;'''
probe='''    const bool textured = getLastAppliedTextureAttribute(0, StateAttribute::TEXTURE) != 0;
    {
        /* BLENDSTATE: ask GL itself whether blending is on at the moment the
           fallback is bound.  Everything else about the transparent surfaces
           checked out, so this is the one thing left that can be measured
           rather than inferred. */
        static const int bprobe = (::getenv("FGFS_BLEND_PROBE") != 0) ? 1 : 0;
        static int blogged = 0;
        if (bprobe && blogged < 24)
        {
            ++blogged;
            GLboolean be = GL_FALSE;
            glGetBooleanv(GL_BLEND, &be);
            GLint sf = 0, df = 0;
            glGetIntegerv(GL_BLEND_SRC_ALPHA, &sf);
            glGetIntegerv(GL_BLEND_DST_ALPHA, &df);
            OSG_WARN << "BLENDSTATE textured=" << (textured ? 1 : 0)
                     << " GL_BLEND=" << (be ? 1 : 0)
                     << " src=0x" << std::hex << sf << " dst=0x" << df << std::dec
                     << std::endl;
        }
    }'''
mode=sys.argv[1]
n=0
if mode=='on':
    if probe not in s and anchor in s:
        s=s.replace(anchor,probe,1); n+=1
else:
    if probe in s:
        s=s.replace(probe,anchor,1); n+=1
open(p,'w').write(s)
print('Blend-Sonde',mode,'->',n)

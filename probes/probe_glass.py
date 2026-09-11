#!/usr/bin/env python3
"""Insert-only probe: which surface is bound to the fallback, and is
blending on for it?

Pure insertion after a unique anchor - no cutting.  The previous attempt
removed text "up to the next closing brace" and took part of the
surrounding function with it.  Removal happens by restoring
State.cpp.beforeprobe, not by reversing this.
"""
import os
ROOT = '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'
p = os.path.join(ROOT, 'src/osg/State.cpp')
s = open(p).read()

anchor = '    const bool textured = getLastAppliedTextureAttribute(0, StateAttribute::TEXTURE) != 0;\n'
assert s.count(anchor) == 1, 'Anker fehlt oder mehrdeutig'

block = '''    if (::getenv("FGFS_GLASS_PROBE"))
    {
        static int logged = 0;
        if (logged < 4000)
        {
            ++logged;
            std::string tn;
            const StateAttribute* sa =
                getLastAppliedTextureAttribute(0, StateAttribute::TEXTURE);
            const Texture* tx = dynamic_cast<const Texture*>(sa);
            const Image* im = tx ? tx->getImage(0) : 0;
            if (im) tn = im->getFileName();
            std::string::size_type sl = tn.find_last_of('/');
            if (sl != std::string::npos) tn = tn.substr(sl + 1);
            GLboolean be = GL_FALSE;
            glGetBooleanv(GL_BLEND, &be);
            OSG_WARN << "GLASSPROBE tex=[" << tn << "] textured="
                     << (textured ? 1 : 0) << " blend=" << (be ? 1 : 0)
                     << std::endl;
        }
    }
'''

if 'GLASSPROBE' in s:
    print('  schon vorhanden')
else:
    s = s.replace(anchor, anchor + block, 1)
    open(p, 'w').write(s)
    print('Sonde eingefuegt')

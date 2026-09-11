#!/usr/bin/env python3
"""Twenty-fifth round: the setArray probe, filtered by the bound texture.

Round 24 showed the normal pattern - one enable per frame, then pointer-only
updates - but only for the first drawables of a frame, never the instrument
faces.  setArray has the State at hand, so it can name the texture bound on
unit 0 and be limited to it:

  OSG_GLES_DEBUG_SETARRAY=1 OSG_GLES_DEBUG_TEXNAME=asi.png

Run after ffp_gles.py .. ffp_gles24.py: python3 ffp_gles25.py [osg-source-root]"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'

p = os.path.join(ROOT, 'src/osg/VertexArrayState.cpp')
s = open(p).read()

if 'SETARRAY tex0 [' in s:
    print('  schon aktuell')
    raise SystemExit

# Texture und Image sind in dieser Uebersetzungseinheit nur vorwaerts deklariert
inc_old = '#include <osg/VertexArrayState>\n'
inc_new = '#include <osg/VertexArrayState>\n#include <osg/Texture>\n#include <osg/Image>\n'
if inc_new not in s and inc_old in s:
    s = s.replace(inc_old, inc_new, 1)
    print('Includes ergaenzt')

old = '''        static const int probe = (::getenv("OSG_GLES_DEBUG_SETARRAY") != 0) ? 1 : 0;
        static int logged = 0;
        if (probe && logged < 60 && vad && !_texCoordArrays.empty()
            && vad == _texCoordArrays[0].get())
        {
            ++logged;
'''
new = '''        static const int probe = (::getenv("OSG_GLES_DEBUG_SETARRAY") != 0) ? 1 : 0;
        static const char* wantTex = ::getenv("OSG_GLES_DEBUG_TEXNAME");
        static int logged = 0;
        if (probe && logged < 60 && vad && !_texCoordArrays.empty()
            && vad == _texCoordArrays[0].get())
        {
            /* Which texture is bound while this array is dispatched? */
            std::string texName;
            {
                const osg::StateAttribute* sa =
                    state.getLastAppliedTextureAttribute(0, osg::StateAttribute::TEXTURE);
                const osg::Texture* t = dynamic_cast<const osg::Texture*>(sa);
                const osg::Image* img = t ? t->getImage(0) : 0;
                if (img) texName = img->getFileName();
                std::string::size_type sl = texName.find_last_of('/');
                if (sl != std::string::npos) texName = texName.substr(sl + 1);
            }
            if (wantTex && *wantTex && texName.find(wantTex) == std::string::npos) return;
            ++logged;
'''
assert s.count(old) == 1, 'Anker Sondenkopf'
s = s.replace(old, new)

old2 = '''            OSG_WARN << "SETARRAY tex0 " << path
'''
new2 = '''            OSG_WARN << "SETARRAY tex0 [" << texName << "] " << path
'''
assert s.count(old2) == 1, 'Anker Ausgabe'
s = s.replace(old2, new2)
open(p, 'w').write(s)
print('geaendert src/osg/VertexArrayState.cpp')
print('fertig')

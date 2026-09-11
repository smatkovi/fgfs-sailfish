#!/usr/bin/env python3
"""Nineteenth round (FlightGear GLES port): 1D textures, and two shader
constructs GLSL ES rejects.

crop.frag and forest.frag - fields and forests - look their colour up in a
1D texture ("ColorsTex").  GLSL ES has no sampler1D, and OSG's
Texture1D::apply() is a no-op under GLES, so those effects failed to compile
and the ground stayed black.  Now:

  * the converter turns sampler1D into sampler2D and texture1D(s, x) into
    texture2D(s, vec2(x, 0.5));
  * Texture1D::apply() under GLES uploads the image as a 2D texture of
    height 1 and binds that, so the lookup finds it;
  * "const float X = SOME_INT;" (urban.frag) becomes "const float X =
    float(SOME_INT);", a constant expression ES accepts.

Run after ffp_gles.py .. ffp_gles18.py: python3 ffp_gles19.py [osg-source-root]"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'

def patch(rel, edits):
    p = os.path.join(ROOT, rel); s = open(p).read()
    done = 0
    for old, new in edits:
        if new in s:
            continue
        assert s.count(old) == 1, '%s: Anker fehlt oder mehrdeutig: %r' % (rel, old[:70])
        s = s.replace(old, new); done += 1
    open(p, 'w').write(s)
    print('%s: %d Stellen' % (rel, done))

# ---- converter: sampler1D / texture1D / const float from int
patch('src/osg/State.cpp', [
('        if (es3)\n'
 '        {\n'
 '            /* GLSL ES 3.00 reserves some names FlightGear uses as identifiers\n',
 '        /* No 1D textures in GLSL ES.  sampler1D becomes sampler2D, and\n'
 '           texture1D(s, x) becomes texture2D(s, vec2(x, 0.5)); Texture1D::apply\n'
 '           uploads the image as a 2D texture of height 1 to match. */\n'
 '        {\n'
 '            static const std::regex s1d("\\\\bsampler1D\\\\b");\n'
 '            src = std::regex_replace(src, s1d, "sampler2D");\n'
 '            std::string::size_type pos = 0;\n'
 '            while ((pos = src.find("texture1D", pos)) != std::string::npos)\n'
 '            {\n'
 '                std::string::size_type open = src.find(\'(\', pos);\n'
 '                if (open == std::string::npos) break;\n'
 '                int depth = 0; std::string::size_type comma = std::string::npos, close = std::string::npos;\n'
 '                for (std::string::size_type i = open; i < src.size(); ++i)\n'
 '                {\n'
 '                    if (src[i] == \'(\') ++depth;\n'
 '                    else if (src[i] == \')\') { if (--depth == 0) { close = i; break; } }\n'
 '                    else if (src[i] == \',\' && depth == 1 && comma == std::string::npos) comma = i;\n'
 '                }\n'
 '                if (close == std::string::npos || comma == std::string::npos) { pos += 9; continue; }\n'
 '                std::string sampler = src.substr(open + 1, comma - open - 1);\n'
 '                std::string coord   = src.substr(comma + 1, close - comma - 1);\n'
 '                std::string repl = "texture2D(" + sampler + ", vec2(" + coord + ", 0.5))";\n'
 '                src.replace(pos, close - pos + 1, repl);\n'
 '                pos += repl.size();\n'
 '            }\n'
 '            /* "const float X = SOME_INT_MACRO;" is not a constant expression of\n'
 '               type float in GLSL ES; a float() constructor around it is. */\n'
 '            static const std::regex constFloat("(\\\\bconst\\\\s+float\\\\s+[A-Za-z_][A-Za-z0-9_]*\\\\s*=\\\\s*)([A-Za-z_][A-Za-z0-9_]*)\\\\s*;");\n'
 '            src = std::regex_replace(src, constFloat, "$1float($2);");\n'
 '        }\n'
 '\n'
 '        if (es3)\n'
 '        {\n'
 '            /* GLSL ES 3.00 reserves some names FlightGear uses as identifiers\n'),
])

# ---- Texture1D under GLES: a 2D texture of height 1
patch('src/osg/Texture1D.cpp', [
('#include <osg/GLExtensions>\n#include <osg/Texture1D>\n',
 '#include <osg/GLExtensions>\n#include <osg/Texture1D>\n#include <osg/Texture2D>\n#include <OpenThreads/Mutex>\n#include <OpenThreads/ScopedLock>\n#include <map>\n'),
('#else\n'
 '    OSG_NOTICE<<"Warning: Texture1D::apply(State& state) not supported."<<std::endl;\n'
 '#endif\n'
 '}\n',
 '#else\n'
 '    /* FlightGear GLES port: GLES has no 1D textures.  Upload the image as a\n'
 '       2D texture of height 1 and bind that; the shader converter turns the\n'
 '       texture1D() lookups into texture2D(s, vec2(x, 0.5)) to match.  Kept in\n'
 '       a side table so the class layout does not change. */\n'
 '    {\n'
 '        static OpenThreads::Mutex mutex;\n'
 '        static std::map<const Texture1D*, osg::ref_ptr<osg::Texture2D> > side;\n'
 '        osg::ref_ptr<osg::Texture2D> t2;\n'
 '        {\n'
 '            OpenThreads::ScopedLock<OpenThreads::Mutex> lock(mutex);\n'
 '            osg::ref_ptr<osg::Texture2D>& slot = side[this];\n'
 '            if (!slot)\n'
 '            {\n'
 '                slot = new osg::Texture2D;\n'
 '                slot->setImage(_image.get());\n'
 '                slot->setFilter(MIN_FILTER, getFilter(MIN_FILTER));\n'
 '                slot->setFilter(MAG_FILTER, getFilter(MAG_FILTER));\n'
 '                slot->setWrap(WRAP_S, getWrap(WRAP_S));\n'
 '                slot->setWrap(WRAP_T, CLAMP_TO_EDGE);\n'
 '                slot->setResizeNonPowerOfTwoHint(false);\n'
 '            }\n'
 '            else if (slot->getImage() != _image.get()) slot->setImage(_image.get());\n'
 '            t2 = slot;\n'
 '        }\n'
 '        t2->apply(state);\n'
 '    }\n'
 '#endif\n'
 '}\n'),
])

# ---- GL_TEXTURE_1D is a dead mode under ES too
patch('include/osg/State', [
('                || mode == 0x0DE1      /* GL_TEXTURE_2D */\n',
 '                || mode == 0x0DE0      /* GL_TEXTURE_1D */\n'
 '                || mode == 0x0DE1      /* GL_TEXTURE_2D */\n'),
])
print('fertig')

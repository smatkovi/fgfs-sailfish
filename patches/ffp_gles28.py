#!/usr/bin/env python3
"""Twenty-eighth round: does this program have the attribute where we dispatch it?

For the black instrument faces GL reports slot 3 enabled with two-component
data, the geometry carries proper texture coordinates, and the model's UVs are
fine - yet the vertex shader reads osg_MultiTexCoord0 as zero.  That is only
possible if the program bound at that moment has the attribute somewhere else
than the slot the dispatcher writes to.  So ask the currently bound program,
at draw time, where its osg_MultiTexCoord0 sits, and compare.

  OSG_GLES_DEBUG_ATTRLOC=1 [OSG_GLES_DEBUG_TEXNAME=asi.png]

Run after ffp_gles.py .. ffp_gles27.py: python3 ffp_gles28.py [osg-source-root]"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'

p = os.path.join(ROOT, 'src/osg/Geometry.cpp')
s = open(p).read()

if 'ATTRLOC' in s:
    print('  schon aktuell')
    raise SystemExit

old = '''    bool handleVertexAttributes = !_vertexAttribList.empty();
'''
new = '''#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)
    /* FlightGear GLES port, OSG_GLES_DEBUG_ATTRLOC=1: where does the program
       that is bound right now keep osg_MultiTexCoord0, and where do we send
       the texture coordinates? */
    {
        static const int probe = (::getenv("OSG_GLES_DEBUG_ATTRLOC") != 0) ? 1 : 0;
        static const char* wantTex = ::getenv("OSG_GLES_DEBUG_TEXNAME");
        static int logged = 0;
        if (probe && logged < 40 && !_texCoordList.empty() && _texCoordList[0].valid())
        {
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
            if (!(wantTex && *wantTex && texName.find(wantTex) == std::string::npos))
            {
                ++logged;
                const Program::PerContextProgram* pcp = state.getLastAppliedProgramObject();
                const int inProgram = pcp ? (int)pcp->getAttribLocation("osg_MultiTexCoord0") : -2;
                const int dispatchTo = state.getTexCoordAliasList().empty()
                                       ? -1 : (int)state.getTexCoordAliasList()[0]._location;
                OSG_WARN << "ATTRLOC [" << texName << "] program="
                         << (pcp ? pcp->getProgram()->getName() : std::string("none"))
                         << " osg_MultiTexCoord0 at " << inProgram
                         << ", dispatched to " << dispatchTo
                         << (inProgram >= 0 && inProgram != dispatchTo ? "  MISMATCH" : "")
                         << std::endl;
            }
        }
    }
#endif

    bool handleVertexAttributes = !_vertexAttribList.empty();
'''
assert s.count(old) == 1, 'Anker'
s = s.replace(old, new)
open(p, 'w').write(s)
print('geaendert src/osg/Geometry.cpp')
print('fertig')

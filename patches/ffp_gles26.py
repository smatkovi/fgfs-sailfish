#!/usr/bin/env python3
"""Twenty-sixth round: ask GL whether the attribute is on.

Everything reachable by reading the code checks out - geometry, texture,
effect, technique, aliasing, dispatch - yet the instrument faces sample
texture coordinate (0,0), and which ones do depends on the drawing order.
A disabled vertex attribute is exactly what reads as a constant, so ask GL
itself, right before the draw call, whether slot 3 is enabled and what
pointer it holds.

  OSG_GLES_DEBUG_ATTRSTATE=1 [OSG_GLES_DEBUG_TEXNAME=asi.png]

Run after ffp_gles.py .. ffp_gles25.py: python3 ffp_gles26.py [osg-source-root]"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'

p = os.path.join(ROOT, 'src/osg/Geometry.cpp')
s = open(p).read()

if 'ATTRSTATE' in s:
    print('  schon aktuell')
    raise SystemExit

# direkt vor dem Zeichnen der Primitive
old = '''    bool handleVertexAttributes = !_vertexAttribList.empty();
'''
new = '''#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)
    /* FlightGear GLES port, OSG_GLES_DEBUG_ATTRSTATE=1: what does GL say
       about the texture coordinate attribute for this drawable? */
    {
        static const int probe = (::getenv("OSG_GLES_DEBUG_ATTRSTATE") != 0) ? 1 : 0;
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
                const int slot = state.getTexCoordAliasList().empty()
                                 ? -1 : (int)state.getTexCoordAliasList()[0]._location;
                GLint enabled = -1, size = -1, stride = -1, bufBinding = -1;
                if (slot >= 0)
                {
                    glGetVertexAttribiv(slot, GL_VERTEX_ATTRIB_ARRAY_ENABLED, &enabled);
                    glGetVertexAttribiv(slot, GL_VERTEX_ATTRIB_ARRAY_SIZE, &size);
                    glGetVertexAttribiv(slot, GL_VERTEX_ATTRIB_ARRAY_STRIDE, &stride);
                    glGetVertexAttribiv(slot, GL_VERTEX_ATTRIB_ARRAY_BUFFER_BINDING, &bufBinding);
                }
                OSG_WARN << "ATTRSTATE [" << texName << "] verts="
                         << (_vertexArray.valid() ? _vertexArray->getNumElements() : 0)
                         << " slot=" << slot << " enabled=" << enabled
                         << " size=" << size << " stride=" << stride
                         << " buffer=" << bufBinding << std::endl;
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

#!/usr/bin/env python3
"""OSG probe: what actually reaches the GPU when a translucent AC3D geometry
is drawn.

Every earlier glass probe sat inside the shaderless fallback (P24-P32), so
a draw that went through a real program was invisible to it.  The
technique probe (P33) says the canopy's effect chooses the ubershader
technique, with a program and GL_BLEND on - so the fallback probes were
looking at other geometry.  This one hooks Geometry::drawImplementation
itself, after the arrays are dispatched and before the primitives, for
geometries whose overall colour has alpha < 0.99 (the AC3D loader puts the
material diffuse there): bound program, GL_BLEND, blend factors, the current
value of the colour attribute, texture unit 0, the material diffuse uniform
if the program has one, and the parent chain.  FGFS_DRAWPROBE=1, first 3000, the splash screen's bar excluded.

Insert-only after a unique anchor; idempotent."""
import os
p = os.path.expanduser('~/OpenSceneGraph-OpenSceneGraph-3.6.5/src/osg/Geometry.cpp')
s = open(p).read()
if 'DRAWPROBE' in s:
    print('schon drin'); raise SystemExit
anchor = '''    drawVertexArraysImplementation(renderInfo);

    if (checkForGLErrors) state.checkGLErrors("Geometry::drawImplementation() after vertex arrays setup.");
'''
assert s.count(anchor) == 1, 'Anker nicht eindeutig'
block = '''    if (::getenv("FGFS_DRAWPROBE"))
    {
        static int logged = 0;
        const Vec4Array* ca = dynamic_cast<const Vec4Array*>(_colorArray.get());
        if (ca && ca->getBinding() == Array::BIND_OVERALL && ca->size() == 1 && (*ca)[0].a() < 0.99f && logged < 3000
            && !(getNumParents() && getParent(0)->getNumParents() && getParent(0)->getParent(0)->getNumParents()
                 && getParent(0)->getParent(0)->getParent(0)->getName() == "splashGroup"))
        {
            ++logged;
            GLint prog = 0, tex = 0, src = 0, dst = 0;
            glGetIntegerv(GL_CURRENT_PROGRAM, &prog);
            glGetIntegerv(GL_TEXTURE_BINDING_2D, &tex);
            glGetIntegerv(GL_BLEND_SRC_ALPHA, &src);
            glGetIntegerv(GL_BLEND_DST_ALPHA, &dst);
            GLfloat cur[4] = { -1, -1, -1, -1 };
            const int loc = state.getColorAlias()._location;
            if (loc >= 0) glGetVertexAttribfv(loc, GL_CURRENT_VERTEX_ATTRIB, cur);
            GLint enabled = 0;
            if (loc >= 0) glGetVertexAttribiv(loc, GL_VERTEX_ATTRIB_ARRAY_ENABLED, &enabled);
            GLfloat mat[4] = { -1, -1, -1, -1 };
            GLint mloc = -1;
            if (prog) mloc = glGetUniformLocation(prog, "osg_FrontMaterial.diffuse");
            if (mloc >= 0) glGetUniformfv(prog, mloc, mat);
            std::ostringstream os;
            os << "DRAWPROBE alpha=" << (*ca)[0].a()
               << " prog=" << prog << " blend=" << (int)glIsEnabled(GL_BLEND)
               << " src=0x" << std::hex << src << " dst=0x" << dst << std::dec
               << " tex=" << tex
               << " colorLoc=" << loc << " arrayEnabled=" << enabled
               << " curColor=" << cur[0] << "," << cur[1] << "," << cur[2] << "," << cur[3]
               << " matDiffuseUniform=" << (mloc >= 0 ? "yes" : "no") << " a=" << mat[3]
               << " geom=[" << getName().substr(0, 24) << "]";
            {
                const Program* pr = 0;
                if (state.getLastAppliedProgramObject()) pr = state.getLastAppliedProgramObject()->getProgram();
                os << " progName=[" << (pr ? pr->getName().substr(0, 40) : std::string("-")) << "]";
                /* the state set stack: which node owns each level, and
                   whether an effect pass is among them */
                os << " stack=";
                const State::StateSetStack& st = state.getStateSetStack();
                for (State::StateSetStack::const_iterator it = st.begin(); it != st.end(); ++it)
                {
                    const StateSet* ss = *it;
                    os << "[" << ss->className() << " m" << (int)ss->getMode(GL_BLEND)
                       << (ss->getAttribute(StateAttribute::PROGRAM) ? "P" : "-");
                    const StateSet::ParentList& pl = ss->getParents();
                    if (!pl.empty() && pl[0]) os << " " << pl[0]->className() << ":" << pl[0]->getName().substr(0, 16);
                    os << "]";
                }
            }
            const Node* n = getNumParents() ? getParent(0) : 0;
            for (int d = 0; n && d < 5; ++d)
            {
                os << " <" << n->className() << ":" << n->getName().substr(0, 24);
                n = n->getNumParents() ? n->getParent(0) : 0;
            }
            OSG_WARN << os.str() << std::endl;
        }
    }
'''
s = s.replace(anchor, anchor + block, 1)
open(p, 'w').write(s); print('Draw-Sonde eingefuegt')

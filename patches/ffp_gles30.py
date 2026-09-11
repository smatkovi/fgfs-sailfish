#!/usr/bin/env python3
"""Thirtieth round: the AC3D loader emitted primitive modes GLES does not have.

This is the black instrument faces, and it was never a texture problem.

GL_QUADS and GL_POLYGON exist in desktop GL only.  Under GLES a draw call
with either mode rasterises nothing whatsoever - and, since the mode is
validated on the desktop path only, reports no GL error while doing so.
Every earlier probe therefore passed: the geometry, the UV values, the
attribute slot, the bound texture and the linked program were all correct.
They describe the *preparation* of a draw call, and preparation was never
the problem.  The call itself drew nothing.

That is why the fault looked like it followed "fixed versus moving".  A dial
face is a single four-cornered SURF, so it becomes one GL_QUADS element and
vanishes completely.  The needles and the curved moving parts - compass
rose, horizon ball - carry triangles too, so they survive, which made the
split look like it was about animation.  It was about quads versus
triangles all along.

Measured with the minimal test case on asi.ac: the face (one quad, 0.08 x
0.08, should cover ~91000 pixels) drew nothing, while the needle's three
triangles drew 240 pixels - the predicted area for those triangles alone.
A hand-built quad with the same coordinates as a TRIANGLE_FAN drew a full
gradient through the same shader and the same context.

Both replacements keep the vertex order, so winding and thus face
orientation are unchanged:
  - a quad (v0,v1,v2,v3) becomes triangles (v0,v1,v2) and (v0,v2,v3),
    which is exactly how GL_QUADS is specified to be decomposed;
  - GL_POLYGON becomes GL_TRIANGLE_FAN, which for a convex polygon is the
    same primitive under a different name.  Concave surfaces never reach
    this path - the loader routes them through _toTessellatePolygons and
    osgUtil::Tessellator, which already outputs triangles.

Run after ffp_gles.py .. ffp_gles29.py: python3 ffp_gles30.py [osg-source-root]"""
import sys, os

ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'

p = os.path.join(ROOT, 'src/osgPlugins/ac/ac3d.cpp')
s = open(p).read()
orig = s

# ---------------------------------------------------------------- quads
old_quads = '''        // handle quads
        if (!_quads.empty())
        {
            osg::ref_ptr<osg::DrawElementsUInt> drawElements = new osg::DrawElementsUInt(osg::PrimitiveSet::QUADS);
            for (unsigned i = 0; i < _quads.size(); ++i)
            {
                for (unsigned j = 0; j < 4; ++j)
                {
                    unsigned index = pushVertex(_quads[i].index[j], vertexArray, normalArray, texcoordArray);
                    drawElements->addElement(index);
                }
            }
            geometry->addPrimitiveSet(createOptimalDrawElements(drawElements.get()));
        }'''

new_quads = '''        // handle quads
        if (!_quads.empty())
        {
            /* GLES has no GL_QUADS.  A draw call carrying that mode
               rasterises nothing and raises no error, so the surface simply
               disappears - this is what blanked the instrument faces.  Split
               each quad the way GL_QUADS is specified to decompose, which
               keeps the vertex order and therefore the winding. */
            osg::ref_ptr<osg::DrawElementsUInt> drawElements = new osg::DrawElementsUInt(osg::PrimitiveSet::TRIANGLES);
            for (unsigned i = 0; i < _quads.size(); ++i)
            {
                unsigned q[4];
                for (unsigned j = 0; j < 4; ++j)
                {
                    q[j] = pushVertex(_quads[i].index[j], vertexArray, normalArray, texcoordArray);
                }
                drawElements->addElement(q[0]);
                drawElements->addElement(q[1]);
                drawElements->addElement(q[2]);
                drawElements->addElement(q[0]);
                drawElements->addElement(q[2]);
                drawElements->addElement(q[3]);
            }
            geometry->addPrimitiveSet(createOptimalDrawElements(drawElements.get()));
        }'''

# ------------------------------------------------------------- polygons
old_poly = '''        // handle polygons
        if (!_polygons.empty())
        {
            for (unsigned i = 0; i < _polygons.size(); ++i)
            {
                osg::ref_ptr<osg::DrawElementsUInt> drawElements = new osg::DrawElementsUInt(osg::PrimitiveSet::POLYGON);'''

new_poly = '''        // handle polygons
        if (!_polygons.empty())
        {
            for (unsigned i = 0; i < _polygons.size(); ++i)
            {
                /* GLES has no GL_POLYGON either.  These surfaces are convex
                   - concave ones are routed through _toTessellatePolygons
                   and come back as triangles - and for a convex polygon a
                   triangle fan is the same primitive under a name GLES
                   knows. */
                osg::ref_ptr<osg::DrawElementsUInt> drawElements = new osg::DrawElementsUInt(osg::PrimitiveSet::TRIANGLE_FAN);'''

changed = []

if old_quads in s:
    s = s.replace(old_quads, new_quads)
    changed.append('quads -> triangles')
elif new_quads in s:
    pass
else:
    raise SystemExit('Anker Vierecke nicht gefunden - Quelle abweichend?')

if old_poly in s:
    s = s.replace(old_poly, new_poly)
    changed.append('polygon -> triangle fan')
elif new_poly in s:
    pass
else:
    raise SystemExit('Anker Polygone nicht gefunden - Quelle abweichend?')

if s == orig:
    print('  schon aktuell')
    raise SystemExit

open(p, 'w').write(s)
print('geaendert src/osgPlugins/ac/ac3d.cpp: ' + ', '.join(changed))
print('fertig')

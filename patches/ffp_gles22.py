#!/usr/bin/env python3
"""Twenty-second round (FlightGear GLES port): the last shrinking dispatcher
list.

Round 12 made assignTexCoordArrayDispatcher() and
assignVertexAttribArrayDispatcher() grow-only, because shrinking leaves a
drawable's higher units without a dispatcher.  getOrCreateVertexAttributeDispatch()
was missed: it still calls list.resize(slot + 1), which shrinks the list when
a drawable needs a lower slot than the previous one did.

Without fixed function osg_MultiTexCoord0 lives on attribute slot 8, so its
dispatcher sits high in the list and is exactly what a shrink throws away.
The next drawable that wants texture coordinates gets a fresh, unbound
dispatcher and reads (0,0) - which is how the c172p's instrument faces ended
up sampling one white texel and rendering black, while their needles, which
carry no texture coordinates, stayed visible.  Which instruments are hit
depends on the drawing order, so some looked fine.

Run after ffp_gles.py .. ffp_gles21.py: python3 ffp_gles22.py [osg-source-root]"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'

p = os.path.join(ROOT, 'src/osg/VertexArrayState.cpp')
s = open(p).read()

old = '''    VertexArrayState::ArrayDispatch* getOrCreateVertexAttributeDispatch(VertexArrayState::ArrayDispatchList& list, int slot)
    {
        list.resize(slot + 1);
'''
new = '''    VertexArrayState::ArrayDispatch* getOrCreateVertexAttributeDispatch(VertexArrayState::ArrayDispatchList& list, int slot)
    {
#if defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)
        list.resize(slot + 1);
#else
        /* FlightGear GLES port: grow only, as in assignTexCoordArrayDispatcher().
           resize() also shrinks, and a drawable that needs a lower slot than the
           previous one would drop the dispatchers above it - including slot 8,
           where osg_MultiTexCoord0 lives without fixed function.  The next
           drawable with texture coordinates then read (0,0). */
        if (static_cast<unsigned int>(slot) + 1 > list.size()) list.resize(slot + 1);
#endif
'''
if new in s:
    print('  schon aktuell')
else:
    assert s.count(old) == 1, 'Anker fehlt oder mehrdeutig'
    s = s.replace(old, new)
    open(p, 'w').write(s)
    print('geaendert src/osg/VertexArrayState.cpp')
print('fertig')

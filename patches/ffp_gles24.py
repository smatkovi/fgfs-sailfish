#!/usr/bin/env python3
"""Twenty-fourth round (FlightGear GLES port): watch the texture coordinate
dispatch itself.

Everything static about the black instrument faces checks out - the drawables
carry texture coordinates just like the ones that render, the texture is
bound, the shader runs, and osg_MultiTexCoord0 links to the same slot the
alias list dispatches to.  Which instruments go black depends on the drawing
order, so the fault is in the state kept between drawables.

VertexArrayState::setArray takes one of three paths: enable and dispatch (a
fresh dispatcher), dispatch only (the array changed), or nothing at all (same
array as last time).  Only the first enables the attribute in GL.  With
OSG_GLES_DEBUG_SETARRAY=1 each call on a texture coordinate dispatcher logs
which path it took and what it holds, so a "dispatch only" or a skip on an
attribute that GL has since disabled shows up directly.

Run after ffp_gles.py .. ffp_gles23.py: python3 ffp_gles24.py [osg-source-root]"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'

p = os.path.join(ROOT, 'src/osg/VertexArrayState.cpp')
s = open(p).read()

if 'SETARRAY' in s:
    print('  schon aktuell')
    raise SystemExit

old = '''void VertexArrayState::setArray(ArrayDispatch* vad, osg::State& state, const osg::Array* new_array)
{
    if (new_array)
    {
'''
new = '''void VertexArrayState::setArray(ArrayDispatch* vad, osg::State& state, const osg::Array* new_array)
{
#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)
    /* FlightGear GLES port, OSG_GLES_DEBUG_SETARRAY=1: which path does a
       texture coordinate array take?  Only the first enables the attribute. */
    {
        static const int probe = (::getenv("OSG_GLES_DEBUG_SETARRAY") != 0) ? 1 : 0;
        static int logged = 0;
        if (probe && logged < 60 && vad && !_texCoordArrays.empty()
            && vad == _texCoordArrays[0].get())
        {
            ++logged;
            const char* path = !new_array ? "disable"
                             : (vad->array == 0 ? "ENABLE+dispatch"
                             : ((new_array != vad->array
                                 || new_array->getModifiedCount() != vad->modifiedCount)
                                ? "dispatch only" : "skipped (same array)"));
            OSG_WARN << "SETARRAY tex0 " << path
                     << " n=" << (new_array ? new_array->getNumElements() : 0)
                     << " active=" << (vad->active ? 1 : 0)
                     << " had=" << (vad->array ? 1 : 0)
                     << " class=" << vad->className() << std::endl;
        }
    }
#endif
    if (new_array)
    {
'''
assert s.count(old) == 1, 'Anker setArray'
s = s.replace(old, new)
open(p, 'w').write(s)
print('geaendert src/osg/VertexArrayState.cpp')
print('fertig')

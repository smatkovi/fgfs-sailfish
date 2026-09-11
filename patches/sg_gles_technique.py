#!/usr/bin/env python3
"""SimGear: let the effect techniques choose a shader path under GLES.

FlightGear's effects pick a technique by predicate.  The interior effect the
c172p's instruments inherit from asks for GLSL >= 2.0 or the four ARB shader
extensions - none of which exist under ES, where that functionality is core
and the extension strings were never defined.  So no shader technique
matched, the effect fell through to the fixed-function one, and under GLES
that draws nothing: the instrument faces were black while the needles, which
come from a different effect, were visible.

Under GLES:
  * extension-supported answers true for the four ARB shader extensions,
    because ES has had that functionality in core since 2.0;
  * shader-language reports 1.20 rather than the ES language version, so
    the version comparisons in the effect files work out.  The shaders are
    rewritten to GLSL ES on load anyway (State::convertShaderSourceForGLES).

  python3 sg_gles_technique.py [simgear-source-root]
"""
import os
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/simgear-2020.3.19')
p = os.path.join(ROOT, 'simgear/scene/material/Technique.cxx')
s = open(p).read()

old_ext = '''    void eval(bool&value, const expression::Binding* b) const
    {
        int contextId = getOperand(0)->getValue(b);
        value = isGLExtensionSupported((unsigned)contextId, _extString.c_str());
    }
'''
new_ext = '''    void eval(bool&value, const expression::Binding* b) const
    {
        int contextId = getOperand(0)->getValue(b);
#if defined(SG_GLES2)
        /* FlightGear GLES port: these four describe functionality ES has had
           in core since 2.0, so the extension strings were never defined.
           Answering false here left every shader technique unmatched and the
           effects fell through to fixed function, which draws nothing under
           ES - the instrument faces stayed black. */
        if (_extString == "GL_ARB_shader_objects"
            || _extString == "GL_ARB_shading_language_100"
            || _extString == "GL_ARB_vertex_shader"
            || _extString == "GL_ARB_fragment_shader")
        {
            value = true;
            return;
        }
#endif
        value = isGLExtensionSupported((unsigned)contextId, _extString.c_str());
    }
'''
assert s.count(old_ext) == 1 or new_ext in s, 'Anker extension-supported'
if new_ext not in s:
    s = s.replace(old_ext, new_ext)
    print('extension-supported: die vier ARB-Namen gelten unter GLES als vorhanden')
else:
    print('  schon aktuell: extension-supported')

# shader-language: report 1.20 under GLES.  Matched by line rather than by a
# block anchor, because the indentation of that #endif differs between trees.
if 'value = 1.20f' in s:
    print('  schon aktuell: shader-language')
else:
    lines = s.split('\n')
    k = next(i for i, l in enumerate(lines) if 'glslLanguageVersion' in l)
    e = next(i for i, l in enumerate(lines) if i > k and l.strip() == '#endif')
    lines[e+1:e+1] = [
        '#if defined(SG_GLES2)',
        '        /* The effect files compare against desktop GLSL versions (2.0 and',
        '           1.2).  Report 1.20 so those comparisons work out; the shaders are',
        '           rewritten to GLSL ES on load either way. */',
        '        if (value > 0.0f) value = 1.20f;',
        '#endif',
    ]
    s = '\n'.join(lines)
    print('shader-language: meldet 1.20 unter GLES')

open(p, 'w').write(s)
print('fertig')

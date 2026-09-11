#!/usr/bin/env python3
"""Eighteenth round (FlightGear GLES port): a fallback program for geometry
that has none.

Under GLES nothing draws without a shader - there is no fixed-function
pipeline to fall back to.  FlightGear's sky dome, the HUD and the 2D panel
come without an Effect, so they stayed black.  When a state set leaves no
program bound, State now binds a built-in one: position through
osg_ModelViewProjectionMatrix, the vertex colour, and the texture on unit 0
if one is bound.  That is what the fixed-function pipeline does for such
geometry with lighting off.

Two variants (with and without texture) are compiled on first use and kept
in the State.  FGFS_GLES_NO_FALLBACK=1 turns it off for comparison.

Run after ffp_gles.py .. ffp_gles17.py: python3 ffp_gles18.py [osg-source-root]"""
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

# ---- members
patch('include/osg/State', [
('        Uniform* ffpUniform(const std::string& name, Uniform::Type type);\n',
 '        Uniform* ffpUniform(const std::string& name, Uniform::Type type);\n'
 '        /* fallback program for geometry without one (FlightGear GLES port) */\n'
 '        ref_ptr<Program>            _fallbackProgram[2];   /* [0] plain, [1] textured */\n'
 '        ref_ptr<Uniform>            _fallbackSampler;\n'
 '        void applyFallbackProgramIfNeeded();\n'),
])

# ---- the hook, at the end of both apply() variants
patch('src/osg/State.cpp', [
('        if (dstate->getUniformList().empty())\n'
 '        {\n'
 '            if (_currentShaderCompositionUniformList.empty()) applyUniformMap(_uniformMap);\n',
 '#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)\n'
 '        applyFallbackProgramIfNeeded();   /* FlightGear GLES port */\n'
 '#endif\n'
 '        if (dstate->getUniformList().empty())\n'
 '        {\n'
 '            if (_currentShaderCompositionUniformList.empty()) applyUniformMap(_uniformMap);\n'),
('    if (_shaderCompositionEnabled)\n'
 '    {\n'
 '        applyShaderComposition();\n'
 '    }\n'
 '\n'
 '    if (_currentShaderCompositionUniformList.empty()) applyUniformMap(_uniformMap);\n',
 '    if (_shaderCompositionEnabled)\n'
 '    {\n'
 '        applyShaderComposition();\n'
 '    }\n'
 '\n'
 '#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)\n'
 '    applyFallbackProgramIfNeeded();   /* FlightGear GLES port */\n'
 '#endif\n'
 '    if (_currentShaderCompositionUniformList.empty()) applyUniformMap(_uniformMap);\n'),
# ---- the implementation, next to the other FFP code
('bool State::convertVertexShaderSourceToOsgBuiltIns(std::string& source) const\n',
 '#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)\n'
 '/* FlightGear GLES port: nothing draws without a program under GLES, and\n'
 '   FlightGear\'s sky dome, HUD and 2D panel have none.  Bind a built-in one\n'
 '   when the state set left none bound - vertex colour, times the texture on\n'
 '   unit 0 if there is one.  That is what the fixed-function pipeline does\n'
 '   for such geometry with lighting off. */\n'
 'void State::applyFallbackProgramIfNeeded()\n'
 '{\n'
 '    if (_lastAppliedProgramObject) return;\n'
 '    static const int off = (::getenv("FGFS_GLES_NO_FALLBACK") != 0) ? 1 : 0;\n'
 '    if (off) return;\n'
 '\n'
 '    const bool textured = getLastAppliedTextureAttribute(0, StateAttribute::TEXTURE) != 0;\n'
 '    ref_ptr<Program>& prog = _fallbackProgram[textured ? 1 : 0];\n'
 '    if (!prog)\n'
 '    {\n'
 '        /* GLSL ES 1.00, which the converter leaves alone; State supplies\n'
 '           osg_ModelViewProjectionMatrix, the attribute aliases and\n'
 '           osg_TextureMatrix0. */\n'
 '        const char* vs =\n'
 '            "attribute vec4 osg_Vertex;\\n"\n'
 '            "attribute vec4 osg_Color;\\n"\n'
 '            "attribute vec4 osg_MultiTexCoord0;\\n"\n'
 '            "uniform mat4 osg_ModelViewProjectionMatrix;\\n"\n'
 '            "uniform mat4 osg_TextureMatrix0;\\n"\n'
 '            "varying vec4 fgfs_color;\\n"\n'
 '            "varying vec2 fgfs_tc;\\n"\n'
 '            "void main() {\\n"\n'
 '            "  gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;\\n"\n'
 '            "  fgfs_color = osg_Color;\\n"\n'
 '            "  fgfs_tc = (osg_TextureMatrix0 * osg_MultiTexCoord0).st;\\n"\n'
 '            "}\\n";\n'
 '        const char* fsPlain =\n'
 '            "precision mediump float;\\n"\n'
 '            "varying vec4 fgfs_color;\\n"\n'
 '            "varying vec2 fgfs_tc;\\n"\n'
 '            "void main() { gl_FragColor = fgfs_color; }\\n";\n'
 '        const char* fsTex =\n'
 '            "precision mediump float;\\n"\n'
 '            "uniform sampler2D fgfs_tex;\\n"\n'
 '            "varying vec4 fgfs_color;\\n"\n'
 '            "varying vec2 fgfs_tc;\\n"\n'
 '            "void main() { gl_FragColor = fgfs_color * texture2D(fgfs_tex, fgfs_tc); }\\n";\n'
 '        prog = new Program;\n'
 '        prog->setName(textured ? "fgfs_fallback_textured" : "fgfs_fallback_plain");\n'
 '        prog->addShader(new Shader(Shader::VERTEX, vs));\n'
 '        prog->addShader(new Shader(Shader::FRAGMENT, textured ? fsTex : fsPlain));\n'
 '        if (!_fallbackSampler) _fallbackSampler = new Uniform("fgfs_tex", 0);\n'
 '        OSG_WARN << "State: fallback program (" << prog->getName()\n'
 '                 << ") for geometry without a shader" << std::endl;\n'
 '    }\n'
 '    prog->apply(*this);\n'
 '    if (textured && _lastAppliedProgramObject) _lastAppliedProgramObject->apply(*_fallbackSampler);\n'
 '    /* the fixed-function uniforms (texture matrix etc.) need a fresh upload\n'
 '       for this program */\n'
 '    _ffpDirty = true;\n'
 '}\n'
 '#endif\n'
 '\n'
 'bool State::convertVertexShaderSourceToOsgBuiltIns(std::string& source) const\n'),
])
print('fertig')

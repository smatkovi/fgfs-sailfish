#!/usr/bin/env python3
"""Fixed-function emulation for GLES builds of OSG 3.6.5 (FlightGear port).
Run inside the SDK container: python3 ffp_gles.py [osg-source-root]"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'

def patch(rel, edits):
    p = os.path.join(ROOT, rel); s = open(p).read()
    for old, new in edits:
        assert s.count(old) == 1, '%s: anchor not found or ambiguous: %r' % (rel, old[:60])
        s = s.replace(old, new)
    open(p, 'w').write(s); print('geaendert', rel)

def add_include(rel, after, inc):
    p = os.path.join(ROOT, rel); s = open(p).read()
    if inc in s: return
    assert s.count(after) == 1, rel
    open(p, 'w').write(s.replace(after, after + inc)); print('include', rel)

CORE = 'namespace osg_gles\n{\n    struct Alias\n    {\n        std::string glName, osgName, declaration;   /* e.g. gl_Vertex, osg_Vertex, "vec4 " */\n    };\n\n    /* Same semantics as osg::State_Utils::replace: the match must not be\n       followed by an identifier character. */\n    inline bool replaceWord(std::string& str, const std::string& original, const std::string& replacement)\n    {\n        if (original.empty()) return false;\n        bool replaced = false;\n        std::string::size_type pos = 0;\n        while ((pos = str.find(original, pos)) != std::string::npos)\n        {\n            std::string::size_type end = pos + original.size();\n            if (end < str.size())\n            {\n                char c = str[end];\n                if ((c >= \'0\' && c <= \'9\') || (c >= \'a\' && c <= \'z\') || (c >= \'A\' && c <= \'Z\') || c == \'_\')\n                {\n                    pos = end;\n                    continue;\n                }\n            }\n            str.replace(pos, original.size(), replacement);\n            pos += replacement.size();\n            replaced = true;\n        }\n        return replaced;\n    }\n\n    inline bool contains(const std::string& str, const std::string& what)\n    {\n        return str.find(what) != std::string::npos;\n    }\n\n    inline void addDecl(std::vector<std::string>& decls, const std::string& decl)\n    {\n        for (std::vector<std::string>::const_iterator it = decls.begin(); it != decls.end(); ++it)\n            if (*it == decl) return;\n        decls.push_back(decl);\n    }\n\n    /* ES 1.00 only allows constant expressions as global initialisers.\n       Split "type name = expr;" at brace depth 0 into a plain declaration\n       and remember the assignment for main(). */\n    inline std::string hoistGlobalInitialisers(const std::string& src, std::vector<std::string>& hoisted)\n    {\n        static const std::regex decl("^(\\\\s*)(float|int|bool|vec[234]|ivec[234]|mat[234])\\\\s+([A-Za-z_][A-Za-z0-9_]*)\\\\s*=\\\\s*([^;]+);(.*)$");\n        static const std::regex literal("^[\\\\s\\\\d.,()eE+*/-]*$");\n        std::ostringstream out;\n        std::istringstream in(src);\n        std::string line;\n        int depth = 0;\n        bool first = true;\n        while (std::getline(in, line))\n        {\n            if (!first) out << \'\\n\';\n            first = false;\n            std::string code = line.substr(0, line.find("//"));\n            std::smatch m;\n            if (depth == 0 && std::regex_match(line, m, decl) && !std::regex_match(m[4].str(), literal)\n                && !contains(code, "const"))\n            {\n                out << m[1].str() << m[2].str() << \' \' << m[3].str() << \';\' << m[5].str();\n                std::string rhs = m[4].str();\n                std::string::size_type a = rhs.find_first_not_of(" \\t"), b = rhs.find_last_not_of(" \\t");\n                hoisted.push_back(m[3].str() + " = " + rhs.substr(a, b - a + 1) + ";");\n                continue;\n            }\n            for (std::string::size_type i = 0; i < code.size(); ++i)\n            {\n                if (code[i] == \'{\') ++depth;\n                else if (code[i] == \'}\') --depth;\n            }\n            out << line;\n        }\n        return out.str();\n    }\n\n    /* Comment out #version / #extension lines in place so that line\n       numbers in compiler messages stay meaningful. */\n    inline std::string neutraliseDirectives(const std::string& src)\n    {\n        static const std::regex directive("^[ \\\\t]*#(version|extension)\\\\b");\n        std::ostringstream out;\n        std::istringstream in(src);\n        std::string line;\n        bool first = true;\n        while (std::getline(in, line))\n        {\n            if (!first) out << \'\\n\';\n            first = false;\n            if (std::regex_search(line, directive)) out << "// ";\n            out << line;\n        }\n        return out.str();\n    }\n\n    inline std::string convert(const std::string& input, bool vertexStage, const std::vector<Alias>& aliases)\n    {\n        std::string src = input;\n        std::string::size_type p;\n        while ((p = src.find("\\r\\n")) != std::string::npos) src.replace(p, 2, "\\n");\n        while ((p = src.find(\'\\r\')) != std::string::npos) src[p] = \'\\n\';\n\n        std::vector<std::string> decls, ext, tail;\n\n        src = neutraliseDirectives(src);\n\n        /* --- what OSG\'s own conversion does: matrices, attributes --- */\n        replaceWord(src, "ftransform()", "(gl_ModelViewProjectionMatrix * gl_Vertex)");\n        static const char* matrices[][3] = {\n            { "gl_ModelViewMatrixInverse",   "osg_ModelViewMatrixInverse",   "mat4" },\n            { "gl_ModelViewMatrixTranspose", "osg_ModelViewMatrixTranspose", "mat4" },\n            { "gl_ModelViewProjectionMatrix", "osg_ModelViewProjectionMatrix", "mat4" },\n            { "gl_ModelViewMatrix",          "osg_ModelViewMatrix",          "mat4" },\n            { "gl_ProjectionMatrix",         "osg_ProjectionMatrix",         "mat4" },\n            { "gl_NormalMatrix",             "osg_NormalMatrix",             "mat3" } };\n        for (unsigned i = 0; i < sizeof(matrices) / sizeof(matrices[0]); ++i)\n            if (replaceWord(src, matrices[i][0], matrices[i][1]))\n                addDecl(decls, std::string("uniform ") + matrices[i][2] + " " + matrices[i][1] + ";");\n\n        bool wroteBack = false;\n        if (vertexStage)\n        {\n            replaceWord(src, "gl_FrontColor", "osg_FrontColor");\n            wroteBack = replaceWord(src, "gl_BackColor", "osg_BackColor");\n            replaceWord(src, "gl_FrontSecondaryColor", "osg_FrontSecondaryColor");\n            replaceWord(src, "gl_BackSecondaryColor", "osg_BackSecondaryColor");\n            addDecl(decls, "varying vec4 osg_FrontColor;");\n            addDecl(decls, "varying vec4 osg_BackColor;");\n            if (contains(src, "osg_FrontSecondaryColor")) addDecl(decls, "varying vec4 osg_FrontSecondaryColor;");\n            if (contains(src, "osg_BackSecondaryColor")) addDecl(decls, "varying vec4 osg_BackSecondaryColor;");\n            if (replaceWord(src, "gl_FogFragCoord", "osg_FogFragCoord")) addDecl(decls, "varying float osg_FogFragCoord;");\n            if (replaceWord(src, "gl_ClipVertex", "osg_ClipVertexDummy")) addDecl(decls, "vec4 osg_ClipVertexDummy;");\n            for (std::vector<Alias>::const_iterator a = aliases.begin(); a != aliases.end(); ++a)\n                if (replaceWord(src, a->glName, a->osgName))\n                    addDecl(decls, "attribute " + a->declaration + a->osgName + ";");\n        }\n        else\n        {\n            if (replaceWord(src, "gl_Color", "(gl_FrontFacing ? osg_FrontColor : osg_BackColor)"))\n            {\n                addDecl(decls, "varying vec4 osg_FrontColor;");\n                addDecl(decls, "varying vec4 osg_BackColor;");\n            }\n            if (replaceWord(src, "gl_SecondaryColor", "osg_FrontSecondaryColor")) addDecl(decls, "varying vec4 osg_FrontSecondaryColor;");\n            if (replaceWord(src, "gl_FogFragCoord", "osg_FogFragCoord")) addDecl(decls, "varying float osg_FogFragCoord;");\n            replaceWord(src, "gl_FragData[0]", "gl_FragColor");\n            if (replaceWord(src, "gl_FragDepth", "osg_FragDepthDummy")) addDecl(decls, "float osg_FragDepthDummy;");\n        }\n\n        /* --- gl_TexCoord[n]: varying array sized by the largest index --- */\n        {\n            static const std::regex texCoord("gl_TexCoord\\\\[(\\\\d+)\\\\]");\n            int maxIndex = -1;\n            for (std::sregex_iterator it(src.begin(), src.end(), texCoord), end; it != end; ++it)\n            {\n                int idx = atoi((*it)[1].str().c_str());\n                if (idx > maxIndex) maxIndex = idx;\n            }\n            if (maxIndex >= 0)\n            {\n                while ((p = src.find("gl_TexCoord[")) != std::string::npos) src.replace(p, 12, "osg_TexCoord[");\n                std::ostringstream d; d << "varying vec4 osg_TexCoord[" << (maxIndex + 1) << "];";\n                addDecl(decls, d.str());\n            }\n        }\n\n        /* --- fixed-function state structs -> flat uniforms --- */\n        static const char* lightMembers[][2] = {\n            { "ambient", "vec4" }, { "diffuse", "vec4" }, { "specular", "vec4" }, { "position", "vec4" },\n            { "halfVector", "vec4" }, { "spotDirection", "vec3" }, { "spotExponent", "float" },\n            { "spotCutoff", "float" }, { "spotCosCutoff", "float" }, { "constantAttenuation", "float" },\n            { "linearAttenuation", "float" }, { "quadraticAttenuation", "float" } };\n        for (int n = 0; n < 8; ++n)\n        {\n            std::ostringstream num; num << n;\n            for (unsigned i = 0; i < sizeof(lightMembers) / sizeof(lightMembers[0]); ++i)\n            {\n                std::string osgName = "osg_LightSource" + num.str() + "_" + lightMembers[i][0];\n                if (replaceWord(src, "gl_LightSource[" + num.str() + "]." + lightMembers[i][0], osgName))\n                    addDecl(decls, std::string("uniform ") + lightMembers[i][1] + " " + osgName + ";");\n            }\n        }\n        static const char* materialMembers[][2] = {\n            { "emission", "vec4" }, { "ambient", "vec4" }, { "diffuse", "vec4" }, { "specular", "vec4" }, { "shininess", "float" } };\n        static const char* materialPrefixes[] = { "gl_FrontMaterial", "gl_BackMaterial" };\n        for (unsigned pfx = 0; pfx < 2; ++pfx)\n            for (unsigned i = 0; i < sizeof(materialMembers) / sizeof(materialMembers[0]); ++i)\n            {\n                std::string osgName = std::string("osg_FrontMaterial_") + materialMembers[i][0];\n                if (replaceWord(src, std::string(materialPrefixes[pfx]) + "." + materialMembers[i][0], osgName))\n                    addDecl(decls, std::string("uniform ") + materialMembers[i][1] + " " + osgName + ";");\n            }\n        if (replaceWord(src, "gl_LightModel.ambient", "osg_LightModel_ambient")) addDecl(decls, "uniform vec4 osg_LightModel_ambient;");\n        if (replaceWord(src, "gl_FrontLightModelProduct.sceneColor", "osg_FrontLightModelProduct_sceneColor"))\n            addDecl(decls, "uniform vec4 osg_FrontLightModelProduct_sceneColor;");\n        static const char* fogMembers[][2] = { { "color", "vec4" }, { "density", "float" }, { "start", "float" }, { "end", "float" }, { "scale", "float" } };\n        for (unsigned i = 0; i < sizeof(fogMembers) / sizeof(fogMembers[0]); ++i)\n        {\n            std::string osgName = std::string("osg_Fog_") + fogMembers[i][0];\n            if (replaceWord(src, std::string("gl_Fog.") + fogMembers[i][0], osgName))\n                addDecl(decls, std::string("uniform ") + fogMembers[i][1] + " " + osgName + ";");\n        }\n        for (int n = 0; n < 8; ++n)\n        {\n            std::ostringstream num; num << n;\n            if (replaceWord(src, "gl_TextureMatrix[" + num.str() + "]", "osg_TextureMatrix" + num.str()))\n                addDecl(decls, "uniform mat4 osg_TextureMatrix" + num.str() + ";");\n        }\n\n        /* --- spellings ES 1.00 lacks --- */\n        replaceWord(src, "mat2x2", "mat2");\n        replaceWord(src, "mat3x3", "mat3");\n        replaceWord(src, "mat4x4", "mat4");\n\n        /* --- integer literals where ES 1.00 wants floats --- */\n        {\n            static const std::regex floatDeclInit("\\\\bfloat\\\\s+([A-Za-z_][A-Za-z0-9_]*)\\\\s*=\\\\s*(\\\\d+)\\\\s*;");\n            src = std::regex_replace(src, floatDeclInit, "float $1 = $2.0;");\n            static const std::regex swizzleCompare("(\\\\.[rgbaxyzwst]{1,4})\\\\s*(>=|<=|==|!=|>|<)\\\\s*(\\\\d+)\\\\b(?![.\\\\w])");\n            src = std::regex_replace(src, swizzleCompare, "$1 $2 $3.0");\n            static const std::regex floatDecls("\\\\bfloat\\\\s+([A-Za-z_][A-Za-z0-9_]*(?:\\\\s*,\\\\s*[A-Za-z_][A-Za-z0-9_]*)*)");\n            std::set<std::string> names;\n            for (std::sregex_iterator it(src.begin(), src.end(), floatDecls), end; it != end; ++it)\n            {\n                std::string list = (*it)[1].str();\n                std::string::size_type start = 0;\n                while (start <= list.size())\n                {\n                    std::string::size_type comma = list.find(\',\', start);\n                    std::string name = list.substr(start, comma == std::string::npos ? std::string::npos : comma - start);\n                    std::string::size_type a = name.find_first_not_of(" \\t"), b = name.find_last_not_of(" \\t");\n                    if (a != std::string::npos) names.insert(name.substr(a, b - a + 1));\n                    if (comma == std::string::npos) break;\n                    start = comma + 1;\n                }\n            }\n            for (std::set<std::string>::const_iterator n = names.begin(); n != names.end(); ++n)\n            {\n                std::regex cmp("\\\\b(" + *n + ")\\\\s*(>=|<=|==|!=|>|<)\\\\s*(\\\\d+)\\\\b(?![.\\\\w])");\n                src = std::regex_replace(src, cmp, "$1 $2 $3.0");\n                std::regex assign("\\\\b(" + *n + ")\\\\s*=\\\\s*(\\\\d+)\\\\s*;");\n                src = std::regex_replace(src, assign, "$1 = $2.0;");\n            }\n        }\n\n        /* --- extensions ES has to be told about --- */\n        if (contains(src, "sampler3D"))\n        {\n            ext.push_back("#extension GL_OES_texture_3D : enable");\n            decls.insert(decls.begin(), "precision mediump sampler3D;");\n        }\n        if (!vertexStage)\n        {\n            static const std::regex lod("\\\\btexture2D(Proj)?Lod\\\\b");\n            if (std::regex_search(src, lod))\n            {\n                src = std::regex_replace(src, lod, "texture2D$1LodEXT");\n                ext.push_back("#extension GL_EXT_shader_texture_lod : enable");\n            }\n        }\n\n        /* --- main() wrapper: colour defaults and hoisted initialisers --- */\n        std::vector<std::string> hoisted;\n        src = hoistGlobalInitialisers(src, hoisted);\n        if (vertexStage || !hoisted.empty())\n        {\n            static const std::regex mainDecl("\\\\bvoid\\\\s+main\\\\s*\\\\(\\\\s*(void)?\\\\s*\\\\)");\n            if (std::regex_search(src, mainDecl))\n            {\n                src = std::regex_replace(src, mainDecl, "void osg_ffp_main()");\n                std::ostringstream w;\n                w << "void main() {\\n";\n                if (vertexStage) w << "    osg_FrontColor = vec4(1.0);\\n    osg_BackColor = vec4(1.0);\\n";\n                for (std::vector<std::string>::const_iterator h = hoisted.begin(); h != hoisted.end(); ++h) w << "    " << *h << \'\\n\';\n                w << "    osg_ffp_main();\\n";\n                if (vertexStage && !wroteBack) w << "    osg_BackColor = osg_FrontColor;\\n";\n                w << "}";\n                tail.push_back(w.str());\n            }\n        }\n\n        /* --- assemble --- */\n        std::ostringstream out;\n        out << "#version 100\\n";\n        for (std::vector<std::string>::const_iterator e = ext.begin(); e != ext.end(); ++e) out << *e << \'\\n\';\n        if (vertexStage) out << "precision highp float;\\n";\n        else out << "#ifdef GL_FRAGMENT_PRECISION_HIGH\\nprecision highp float;\\n#else\\nprecision mediump float;\\n#endif\\n";\n        out << "precision highp int;\\n";\n        for (std::vector<std::string>::const_iterator d = decls.begin(); d != decls.end(); ++d) out << *d << \'\\n\';\n        out << src;\n        for (std::vector<std::string>::const_iterator t = tail.begin(); t != tail.end(); ++t) out << \'\\n\' << *t << \'\\n\';\n        return out.str();\n    }\n}\n'

# ---------------------------------------------------------------- header
patch('include/osg/State', [
('        void applyModelViewAndProjectionUniformsIfRequired();\n',
 '        void applyModelViewAndProjectionUniformsIfRequired();\n'
 '\n'
 '        /* --- fixed-function emulation for GLES builds (FlightGear port) ---\n'
 '           Desktop GLSL 1.20 shaders are rewritten to ES 1.00, and the values\n'
 '           of Light/Material/LightModel/Fog/TexMat are uploaded as osg_*\n'
 '           uniforms to the current program. */\n'
 '        bool convertShaderSourceForGLES(Shader::Type type, std::string& source) const;\n'
 '        void setFFPLight(unsigned int num, const Vec4& ambient, const Vec4& diffuse, const Vec4& specular,\n'
 '                         const Vec4& eyePosition, const Vec3& eyeSpotDirection, float spotExponent, float spotCutoff,\n'
 '                         float constantAttenuation, float linearAttenuation, float quadraticAttenuation);\n'
 '        void setFFPMaterial(const Vec4& emission, const Vec4& ambient, const Vec4& diffuse, const Vec4& specular, float shininess);\n'
 '        void setFFPLightModelAmbient(const Vec4& ambient);\n'
 '        void setFFPFog(int mode, const Vec4& color, float density, float start, float end);\n'
 '        void setFFPTextureMatrix(unsigned int unit, const Matrix& matrix);\n'),
('        int                          _timestampBits;\n};\n',
 '        int                          _timestampBits;\n'
 '\n'
 '        /* fixed-function emulation (FlightGear GLES port) - appended last so the\n'
 '           layout seen by SimGear and FlightGear binaries stays unchanged */\n'
 '        ref_ptr<Uniform>            _modelViewMatrixInverseUniform;\n'
 '        ref_ptr<Uniform>            _modelViewMatrixTransposeUniform;\n'
 '        typedef std::map<std::string, ref_ptr<Uniform> > FFPUniformMap;\n'
 '        FFPUniformMap               _ffpUniforms;\n'
 '        bool                        _ffpDirty;\n'
 '        const Program::PerContextProgram* _ffpLastProgram;\n'
 '        Vec4                        _ffpMaterialEmission, _ffpMaterialAmbient, _ffpMaterialDiffuse, _ffpLightModelAmbient;\n'
 '        Uniform* ffpUniform(const std::string& name, Uniform::Type type);\n'
 '        void initFFPUniforms();\n'
 '        void updateFFPSceneColor();\n};\n'),
])

# ---------------------------------------------------------------- State.cpp
patch('src/osg/State.cpp', [
('#include <sstream>\n#include <algorithm>\n',
 '#include <sstream>\n#include <algorithm>\n#include <regex>\n#include <set>\n#include <cmath>\n'),
('    _normalMatrixUniform = new Uniform(Uniform::FLOAT_MAT3,"osg_NormalMatrix");\n',
 '    _normalMatrixUniform = new Uniform(Uniform::FLOAT_MAT3,"osg_NormalMatrix");\n'
 '    _modelViewMatrixInverseUniform = new Uniform(Uniform::FLOAT_MAT4,"osg_ModelViewMatrixInverse");\n'
 '    _modelViewMatrixTransposeUniform = new Uniform(Uniform::FLOAT_MAT4,"osg_ModelViewMatrixTranspose");\n'
 '    _ffpDirty = true;\n'
 '    _ffpLastProgram = 0;\n'
 '    initFFPUniforms();\n'),
('    if (_normalMatrixUniform) _lastAppliedProgramObject->apply(*_normalMatrixUniform);\n}\n',
 '    if (_normalMatrixUniform) _lastAppliedProgramObject->apply(*_normalMatrixUniform);\n'
 '\n'
 '    /* fixed-function emulation (FlightGear GLES port): re-upload on program\n'
 '       change or value change; PerContextProgram::apply skips unchanged ones. */\n'
 '    if (_ffpDirty || _ffpLastProgram != _lastAppliedProgramObject)\n'
 '    {\n'
 '        _ffpLastProgram = _lastAppliedProgramObject;\n'
 '        _ffpDirty = false;\n'
 '        for (FFPUniformMap::const_iterator it = _ffpUniforms.begin(); it != _ffpUniforms.end(); ++it)\n'
 '            _lastAppliedProgramObject->apply(*it->second);\n'
 '    }\n'
 '    if (_modelViewMatrixInverseUniform.valid() &&\n'
 '        _lastAppliedProgramObject->getUniformLocation(_modelViewMatrixInverseUniform->getNameID()) >= 0)\n'
 '    {\n'
 '        Matrix inverse;\n'
 '        inverse.invert(*_modelView);\n'
 '        _modelViewMatrixInverseUniform->set(inverse);\n'
 '        _lastAppliedProgramObject->apply(*_modelViewMatrixInverseUniform);\n'
 '    }\n'
 '    if (_modelViewMatrixTransposeUniform.valid() &&\n'
 '        _lastAppliedProgramObject->getUniformLocation(_modelViewMatrixTransposeUniform->getNameID()) >= 0)\n'
 '    {\n'
 '        Matrix t;\n'
 '        for (int i = 0; i < 4; ++i) for (int j = 0; j < 4; ++j) t(i, j) = (*_modelView)(j, i);\n'
 '        _modelViewMatrixTransposeUniform->set(t);\n'
 '        _lastAppliedProgramObject->apply(*_modelViewMatrixTransposeUniform);\n'
 '    }\n'
 '}\n'),
('bool State::convertVertexShaderSourceToOsgBuiltIns(std::string& source) const\n',
 '/* ===== fixed-function emulation for GLES builds (FlightGear port) =====\n'
 ' * FlightGear\'s effects are desktop GLSL 1.20 against the fixed-function\n'
 ' * built-ins; GLES has neither.  convertShaderSourceForGLES() rewrites the\n'
 ' * source, and Light/Material/LightModel/Fog/TexMat feed the setters below,\n'
 ' * whose values reach the current program as osg_* uniforms. */\n'
 + CORE +
 '\n'
 'namespace\n'
 '{\n'
 '    template<class T> void ffpSet(Uniform* u, const T& value, bool& dirty)\n'
 '    {\n'
 '        T current;\n'
 '        if (u->get(current) && current == value) return;\n'
 '        u->set(value);\n'
 '        dirty = true;\n'
 '    }\n'
 '}\n'
 '\n'
 'Uniform* State::ffpUniform(const std::string& name, Uniform::Type type)\n'
 '{\n'
 '    FFPUniformMap::iterator it = _ffpUniforms.find(name);\n'
 '    if (it != _ffpUniforms.end()) return it->second.get();\n'
 '    Uniform* u = new Uniform(type, name);\n'
 '    _ffpUniforms[name] = u;\n'
 '    _ffpDirty = true;\n'
 '    return u;\n'
 '}\n'
 '\n'
 'void State::initFFPUniforms()\n'
 '{\n'
 '    /* OpenGL fixed-function defaults */\n'
 '    _ffpMaterialEmission.set(0.0f, 0.0f, 0.0f, 1.0f);\n'
 '    _ffpMaterialAmbient.set(0.2f, 0.2f, 0.2f, 1.0f);\n'
 '    _ffpMaterialDiffuse.set(0.8f, 0.8f, 0.8f, 1.0f);\n'
 '    _ffpLightModelAmbient.set(0.2f, 0.2f, 0.2f, 1.0f);\n'
 '    setFFPLight(0, Vec4(0.0f, 0.0f, 0.0f, 1.0f), Vec4(1.0f, 1.0f, 1.0f, 1.0f), Vec4(1.0f, 1.0f, 1.0f, 1.0f),\n'
 '                Vec4(0.0f, 0.0f, 1.0f, 0.0f), Vec3(0.0f, 0.0f, -1.0f), 0.0f, 180.0f, 1.0f, 0.0f, 0.0f);\n'
 '    setFFPMaterial(_ffpMaterialEmission, _ffpMaterialAmbient, _ffpMaterialDiffuse, Vec4(0.0f, 0.0f, 0.0f, 1.0f), 0.0f);\n'
 '    setFFPLightModelAmbient(_ffpLightModelAmbient);\n'
 '    setFFPFog(0x0800 /* GL_EXP */, Vec4(0.0f, 0.0f, 0.0f, 0.0f), 1.0f, 0.0f, 1.0f);\n'
 '    for (unsigned int unit = 0; unit < 2; ++unit) setFFPTextureMatrix(unit, Matrix::identity());\n'
 '}\n'
 '\n'
 'void State::setFFPLight(unsigned int num, const Vec4& ambient, const Vec4& diffuse, const Vec4& specular,\n'
 '                        const Vec4& eyePosition, const Vec3& eyeSpotDirection, float spotExponent, float spotCutoff,\n'
 '                        float constantAttenuation, float linearAttenuation, float quadraticAttenuation)\n'
 '{\n'
 '    if (num >= 8) return;\n'
 '    std::ostringstream p; p << "osg_LightSource" << num << "_";\n'
 '    const std::string pfx = p.str();\n'
 '    ffpSet(ffpUniform(pfx + "ambient", Uniform::FLOAT_VEC4), ambient, _ffpDirty);\n'
 '    ffpSet(ffpUniform(pfx + "diffuse", Uniform::FLOAT_VEC4), diffuse, _ffpDirty);\n'
 '    ffpSet(ffpUniform(pfx + "specular", Uniform::FLOAT_VEC4), specular, _ffpDirty);\n'
 '    ffpSet(ffpUniform(pfx + "position", Uniform::FLOAT_VEC4), eyePosition, _ffpDirty);\n'
 '    /* half vector for an infinite light and an infinite viewer, as GL does */\n'
 '    Vec3 dir(eyePosition.x(), eyePosition.y(), eyePosition.z());\n'
 '    if (dir.length2() > 0.0f) dir.normalize();\n'
 '    Vec3 half = dir + Vec3(0.0f, 0.0f, 1.0f);\n'
 '    if (half.length2() > 0.0f) half.normalize();\n'
 '    ffpSet(ffpUniform(pfx + "halfVector", Uniform::FLOAT_VEC4), Vec4(half, 0.0f), _ffpDirty);\n'
 '    ffpSet(ffpUniform(pfx + "spotDirection", Uniform::FLOAT_VEC3), eyeSpotDirection, _ffpDirty);\n'
 '    ffpSet(ffpUniform(pfx + "spotExponent", Uniform::FLOAT), spotExponent, _ffpDirty);\n'
 '    ffpSet(ffpUniform(pfx + "spotCutoff", Uniform::FLOAT), spotCutoff, _ffpDirty);\n'
 '    ffpSet(ffpUniform(pfx + "spotCosCutoff", Uniform::FLOAT), float(cos(DegreesToRadians(double(spotCutoff)))), _ffpDirty);\n'
 '    ffpSet(ffpUniform(pfx + "constantAttenuation", Uniform::FLOAT), constantAttenuation, _ffpDirty);\n'
 '    ffpSet(ffpUniform(pfx + "linearAttenuation", Uniform::FLOAT), linearAttenuation, _ffpDirty);\n'
 '    ffpSet(ffpUniform(pfx + "quadraticAttenuation", Uniform::FLOAT), quadraticAttenuation, _ffpDirty);\n'
 '}\n'
 '\n'
 'void State::updateFFPSceneColor()\n'
 '{\n'
 '    /* gl_FrontLightModelProduct.sceneColor = emission + ambient * lightmodel.ambient */\n'
 '    Vec4 scene = _ffpMaterialEmission + componentMultiply(_ffpMaterialAmbient, _ffpLightModelAmbient);\n'
 '    scene.w() = _ffpMaterialDiffuse.w();\n'
 '    ffpSet(ffpUniform("osg_FrontLightModelProduct_sceneColor", Uniform::FLOAT_VEC4), scene, _ffpDirty);\n'
 '}\n'
 '\n'
 'void State::setFFPMaterial(const Vec4& emission, const Vec4& ambient, const Vec4& diffuse, const Vec4& specular, float shininess)\n'
 '{\n'
 '    _ffpMaterialEmission = emission;\n'
 '    _ffpMaterialAmbient = ambient;\n'
 '    _ffpMaterialDiffuse = diffuse;\n'
 '    ffpSet(ffpUniform("osg_FrontMaterial_emission", Uniform::FLOAT_VEC4), emission, _ffpDirty);\n'
 '    ffpSet(ffpUniform("osg_FrontMaterial_ambient", Uniform::FLOAT_VEC4), ambient, _ffpDirty);\n'
 '    ffpSet(ffpUniform("osg_FrontMaterial_diffuse", Uniform::FLOAT_VEC4), diffuse, _ffpDirty);\n'
 '    ffpSet(ffpUniform("osg_FrontMaterial_specular", Uniform::FLOAT_VEC4), specular, _ffpDirty);\n'
 '    ffpSet(ffpUniform("osg_FrontMaterial_shininess", Uniform::FLOAT), shininess, _ffpDirty);\n'
 '    updateFFPSceneColor();\n'
 '}\n'
 '\n'
 'void State::setFFPLightModelAmbient(const Vec4& ambient)\n'
 '{\n'
 '    _ffpLightModelAmbient = ambient;\n'
 '    ffpSet(ffpUniform("osg_LightModel_ambient", Uniform::FLOAT_VEC4), ambient, _ffpDirty);\n'
 '    updateFFPSceneColor();\n'
 '}\n'
 '\n'
 'void State::setFFPFog(int mode, const Vec4& color, float density, float start, float end)\n'
 '{\n'
 '    (void)mode;   /* FlightGear\'s shaders compute EXP2 themselves */\n'
 '    ffpSet(ffpUniform("osg_Fog_color", Uniform::FLOAT_VEC4), color, _ffpDirty);\n'
 '    ffpSet(ffpUniform("osg_Fog_density", Uniform::FLOAT), density, _ffpDirty);\n'
 '    ffpSet(ffpUniform("osg_Fog_start", Uniform::FLOAT), start, _ffpDirty);\n'
 '    ffpSet(ffpUniform("osg_Fog_end", Uniform::FLOAT), end, _ffpDirty);\n'
 '    ffpSet(ffpUniform("osg_Fog_scale", Uniform::FLOAT), (end != start) ? 1.0f / (end - start) : 1.0f, _ffpDirty);\n'
 '}\n'
 '\n'
 'void State::setFFPTextureMatrix(unsigned int unit, const Matrix& matrix)\n'
 '{\n'
 '    if (unit >= 8) return;\n'
 '    std::ostringstream n; n << "osg_TextureMatrix" << unit;\n'
 '    ffpSet(ffpUniform(n.str(), Uniform::FLOAT_MAT4), matrix, _ffpDirty);\n'
 '}\n'
 '\n'
 'bool State::convertShaderSourceForGLES(Shader::Type type, std::string& source) const\n'
 '{\n'
 '    if (type != Shader::VERTEX && type != Shader::FRAGMENT) return false;\n'
 '    State_Utils::substitudeEnvVars(*this, source);\n'
 '    std::vector<osg_gles::Alias> aliases;\n'
 '    const VertexAttribAlias* fixed[] = { &_vertexAlias, &_normalAlias, &_colorAlias, &_secondaryColorAlias, &_fogCoordAlias };\n'
 '    for (unsigned int i = 0; i < sizeof(fixed) / sizeof(fixed[0]); ++i)\n'
 '    {\n'
 '        osg_gles::Alias a;\n'
 '        a.glName = fixed[i]->_glName; a.osgName = fixed[i]->_osgName; a.declaration = fixed[i]->_declaration;\n'
 '        aliases.push_back(a);\n'
 '    }\n'
 '    for (size_t i = 0; i < _texCoordAliasList.size(); ++i)\n'
 '    {\n'
 '        osg_gles::Alias a;\n'
 '        a.glName = _texCoordAliasList[i]._glName; a.osgName = _texCoordAliasList[i]._osgName; a.declaration = _texCoordAliasList[i]._declaration;\n'
 '        aliases.push_back(a);\n'
 '    }\n'
 '    source = osg_gles::convert(source, type == Shader::VERTEX, aliases);\n'
 '    return true;\n'
 '}\n'
 '\n'
 'bool State::convertVertexShaderSourceToOsgBuiltIns(std::string& source) const\n'),
])

# ---------------------------------------------------------------- Shader.cpp
patch('src/osg/Shader.cpp', [
('    std::string source = _shader->getShaderSource();\n'
 '    // if (_shader->getType()==osg::Shader::VERTEX && (state.getUseVertexAttributeAliasing() || state.getUseModelViewAndProjectionUniforms()))\n'
 '    {\n'
 '        state.convertVertexShaderSourceToOsgBuiltIns(source);\n'
 '    }\n',
 '    std::string source = _shader->getShaderSource();\n'
 '#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)\n'
 '    /* GLES (FlightGear port): rewrite desktop GLSL 1.20 to ES 1.00, including\n'
 '       the fixed-function built-ins, not just the attributes and matrices. */\n'
 '    state.convertShaderSourceForGLES(_shader->getType(), source);\n'
 '#else\n'
 '    // if (_shader->getType()==osg::Shader::VERTEX && (state.getUseVertexAttributeAliasing() || state.getUseModelViewAndProjectionUniforms()))\n'
 '    {\n'
 '        state.convertVertexShaderSourceToOsgBuiltIns(source);\n'
 '    }\n'
 '#endif\n'),
])

# ---------------------------------------------------------------- attributes
add_include('src/osg/Light.cpp', '#include <osg/Light>\n', '#include <osg/State>\n')
patch('src/osg/Light.cpp', [
('void Light::apply(State&) const\n{\n#ifdef OSG_GL_FIXED_FUNCTION_AVAILABLE\n',
 'void Light::apply(State& state) const\n{\n#ifdef OSG_GL_FIXED_FUNCTION_AVAILABLE\n    (void)state;\n'),
('#else\n    OSG_NOTICE<<"Warning: Light::apply(State&) - not supported."<<std::endl;\n#endif\n}\n',
 '#else\n'
 '    /* GLES (FlightGear port): no fixed-function lights.  Position and spot\n'
 '       direction go to eye space with the modelview matrix current now,\n'
 '       exactly as glLightfv(GL_POSITION) does. */\n'
 '    const Matrix& mv = state.getModelViewMatrix();\n'
 '    Vec4 eyePosition = _position * mv;\n'
 '    Vec3 eyeDirection = Matrix::transform3x3(_direction, mv);\n'
 '    state.setFFPLight(_lightnum, _ambient, _diffuse, _specular, eyePosition, eyeDirection,\n'
 '                      _spot_exponent, _spot_cutoff, _constant_attenuation, _linear_attenuation, _quadratic_attenuation);\n'
 '#endif\n}\n'),
])
patch('src/osg/Material.cpp', [
('void Material::apply(State& state) const\n{\n    OSG_NOTICE<<"Warning: Material::apply(State&) - not supported."<<std::endl;\n\n    state.Color(',
 'void Material::apply(State& state) const\n{\n'
 '    /* GLES (FlightGear port): values go to the osg_FrontMaterial_* uniforms */\n'
 '    state.setFFPMaterial(_emissionFront, _ambientFront, _diffuseFront, _specularFront, _shininessFront);\n\n'
 '    state.Color('),
])
patch('src/osg/LightModel.cpp', [
('void LightModel::apply(State&) const\n{\n    OSG_NOTICE<<"Warning: LightModel::apply(State&) - not supported."<<std::endl;\n}\n',
 'void LightModel::apply(State& state) const\n{\n'
 '    /* GLES (FlightGear port): global ambient goes to osg_LightModel_ambient */\n'
 '    state.setFFPLightModelAmbient(_ambient);\n}\n'),
])
patch('src/osg/Fog.cpp', [
('#else\n    OSG_NOTICE<<"Warning: Fog::apply(State&) - not supported."<<std::endl;\n#endif\n}\n',
 '#else\n'
 '    /* GLES (FlightGear port): values go to the osg_Fog_* uniforms */\n'
 '    state.setFFPFog(_mode, _color, _density, _start, _end);\n'
 '#endif\n}\n'),
])
add_include('src/osg/TexMat.cpp', '#include <osg/GL>\n', '#include <osg/State>\n')
patch('src/osg/TexMat.cpp', [
('#else\n    OSG_NOTICE<<"Warning: TexMat::apply(State&) - not supported."<<std::endl;\n#endif\n}\n',
 '#else\n'
 '    /* GLES (FlightGear port): goes to osg_TextureMatrix<unit> */\n'
 '    state.setFFPTextureMatrix(state.getActiveTextureUnit(), _matrix);\n'
 '#endif\n}\n'),
])

# ---------------------------------------------------------------- GraphicsWindowEGL: log GL strings once
gw = os.path.join(ROOT, 'src/osgViewer/GraphicsWindowEGL.cpp')
if os.path.exists(gw):
    patch('src/osgViewer/GraphicsWindowEGL.cpp', [
    ('        if (!loadFboEntryPoints()) {\n',
     '        {\n'
     '            const char* v = (const char*)glGetString(GL_VERSION);\n'
     '            const char* r = (const char*)glGetString(GL_RENDERER);\n'
     '            const char* e = (const char*)glGetString(GL_EXTENSIONS);\n'
     '            OSG_WARN << "GraphicsWindowEGL: GL " << (v ? v : "?") << " on " << (r ? r : "?") << std::endl;\n'
     '            OSG_WARN << "GraphicsWindowEGL: GL extensions: " << (e ? e : "?") << std::endl;\n'
     '        }\n'
     '        if (!loadFboEntryPoints()) {\n'),
    ])
print('fertig')

#!/usr/bin/env python3
"""Thirteenth round (FlightGear GLES port): confine the port to GLES builds.

Several pieces of the GLES work compile into the desktop profile as well and
change how the Zink build behaves: the fixed-function uniform bookkeeping in
State, the merged-shader member and the reserved-name aliasing in Program, the
grow-only dispatcher lists, and two debug logs.  Everything here is either
useless or unwanted with a real fixed-function pipeline, so it is now guarded
by OSG_GL_FIXED_FUNCTION_AVAILABLE.  The GLES builds are unchanged.

Run after ffp_gles.py .. ffp_gles12.py: python3 ffp_gles13.py [osg-source-root]"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'
GUARD_OPEN = '#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)\n'
GUARD_CLOSE = '#endif\n'

def wrap(rel, blocks):
    p = os.path.join(ROOT, rel)
    s = open(p).read()
    done = 0
    for block in blocks:
        if GUARD_OPEN + block in s:
            continue                      # already guarded
        assert s.count(block) == 1, '%s: Anker fehlt oder mehrdeutig: %r' % (rel, block[:60])
        s = s.replace(block, GUARD_OPEN + block + GUARD_CLOSE)
        done += 1
    open(p, 'w').write(s)
    print('%s: %d Bloecke eingegrenzt' % (rel, done))

# ---- State: the whole fixed-function emulation
wrap('include/osg/State', [
'''        /* --- fixed-function emulation for GLES builds (FlightGear port) ---
           Desktop GLSL 1.20 shaders are rewritten to ES 1.00, and the values
           of Light/Material/LightModel/Fog/TexMat are uploaded as osg_*
           uniforms to the current program. */
        bool convertShaderSourceForGLES(Shader::Type type, std::string& source) const;
        void setFFPLight(unsigned int num, const Vec4& ambient, const Vec4& diffuse, const Vec4& specular,
                         const Vec4& eyePosition, const Vec3& eyeSpotDirection, float spotExponent, float spotCutoff,
                         float constantAttenuation, float linearAttenuation, float quadraticAttenuation);
        void setFFPMaterial(const Vec4& emission, const Vec4& ambient, const Vec4& diffuse, const Vec4& specular, float shininess);
        void setFFPLightModelAmbient(const Vec4& ambient);
        void setFFPFog(int mode, const Vec4& color, float density, float start, float end);
        void setFFPTextureMatrix(unsigned int unit, const Matrix& matrix);
''',
'''        /* fixed-function emulation (FlightGear GLES port) - appended last so the
           layout seen by SimGear and FlightGear binaries stays unchanged */
        ref_ptr<Uniform>            _modelViewMatrixInverseUniform;
        ref_ptr<Uniform>            _modelViewMatrixTransposeUniform;
        typedef std::map<std::string, ref_ptr<Uniform> > FFPUniformMap;
        FFPUniformMap               _ffpUniforms;
        bool                        _ffpDirty;
        const Program::PerContextProgram* _ffpLastProgram;
        Vec4                        _ffpMaterialEmission, _ffpMaterialAmbient, _ffpMaterialDiffuse, _ffpLightModelAmbient;
        Uniform* ffpUniform(const std::string& name, Uniform::Type type);
        void initFFPUniforms();
        void updateFFPSceneColor();
''',
])

wrap('src/osg/State.cpp', [
'''    _modelViewMatrixInverseUniform = new Uniform(Uniform::FLOAT_MAT4,"osg_ModelViewMatrixInverse");
    _modelViewMatrixTransposeUniform = new Uniform(Uniform::FLOAT_MAT4,"osg_ModelViewMatrixTranspose");
    _ffpDirty = true;
    _ffpLastProgram = 0;
    initFFPUniforms();
''',
])

# ---- Program: merged shader list and the reserved-name alias
wrap('include/osg/Program', [
'''                /** GLES allows a single shader object per stage (FlightGear port):
                  * merge same-stage shaders of the Program into one and compile them. */
                void mergeShadersForGLES(osg::State& state);
''',
'''                ShaderList _mergedShaders;   /* FlightGear GLES port, see mergeShadersForGLES() */
''',
])

wrap('src/osg/Program.cpp', [
'''                /* FlightGear GLES port: the shader converter renames identifiers that
                   GLSL ES reserves (e.g. "texture"); keep the original name reachable
                   so osg::Uniform("texture") still finds the sampler. */
                {
                    static const std::string renamePrefix("osg_ru_");
                    std::string uniformName(reinterpret_cast<const char*>(name));
                    if (uniformName.compare(0, renamePrefix.size(), renamePrefix) == 0)
                        _uniformInfoMap[Uniform::getNameID(uniformName.substr(renamePrefix.size()))] = ActiveVarInfo(loc,type,size);
                }
''',
])

# ---- dispatcher lists and the two remaining logs
wrap('src/osg/VertexArrayState.cpp', [
'''/* FlightGear GLES port: OSG_GLES_DEBUG_AFTER=<seconds> - only log once the
   scene is up, so the probes are not used up by the splash screen. */
static bool osg_gles_debug_now()
{
    static double after = -1.0;
    static osg::Timer_t start = osg::Timer::instance()->tick();
    if (after < 0.0)
    {
        const char* e = getenv("OSG_GLES_DEBUG_AFTER");
        after = (e && *e) ? atof(e) : 0.0;
    }
    return osg::Timer::instance()->delta_s(start, osg::Timer::instance()->tick()) >= after;
}
''',
])

wrap('src/osg/VertexAttribDivisor.cpp', [
'''        {
            static int logged = 0;   /* FlightGear GLES port */
            if (logged < 24) { ++logged; OSG_WARN << "VertexAttribDivisor::apply index=" << _index << " divisor=" << _divisor << std::endl; }
        }
''',
])

# ---- the grow-only dispatchers stay, but only for GLES
p = os.path.join(ROOT, 'src/osg/VertexArrayState.cpp')
s = open(p).read()
for old, new in (
    ('''    /* FlightGear GLES port: only ever grow.  Shrinking would leave the
       drawable's higher units without a dispatcher, and setTexCoordArray()
       indexes this vector unchecked. */
    if (numUnits > _texCoordArrays.size()) _texCoordArrays.resize(numUnits);
''',
     '''#if defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)
    _texCoordArrays.resize(numUnits);
#else
    /* FlightGear GLES port: only ever grow.  Shrinking would leave the
       drawable's higher units without a dispatcher, and setTexCoordArray()
       indexes this vector unchecked. */
    if (numUnits > _texCoordArrays.size()) _texCoordArrays.resize(numUnits);
#endif
'''),
    ('''    /* FlightGear GLES port: grow only, see assignTexCoordArrayDispatcher(). */
    if (numUnits > _vertexAttribArrays.size()) _vertexAttribArrays.resize(numUnits);
''',
     '''#if defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)
    _vertexAttribArrays.resize(numUnits);
#else
    /* FlightGear GLES port: grow only, see assignTexCoordArrayDispatcher(). */
    if (numUnits > _vertexAttribArrays.size()) _vertexAttribArrays.resize(numUnits);
#endif
'''),
):
    if new in s:
        continue
    assert s.count(old) == 1, 'VertexArrayState: Anker fehlt'
    s = s.replace(old, new)
open(p, 'w').write(s)
print('src/osg/VertexArrayState.cpp: assign*Dispatcher nach Profil getrennt')

p = os.path.join(ROOT, 'src/osg/Geometry.cpp')
s = open(p).read()
old = '''    /* FlightGear GLES port: the current VertexArrayState may be the global
       one, with fewer dispatchers than this drawable has units; setTexCoordArray()
       and setVertexAttribArray() would then index out of range. */
    if (!_texCoordList.empty()) vas->assignTexCoordArrayDispatcher(_texCoordList.size());
    if (handleVertexAttributes && !_vertexAttribList.empty())
        vas->assignVertexAttribArrayDispatcher(_vertexAttribList.size());
'''
if GUARD_OPEN + old not in s:
    assert s.count(old) == 1, 'Geometry: Anker fehlt'
    s = s.replace(old, GUARD_OPEN + old + GUARD_CLOSE)
    open(p, 'w').write(s)
    print('src/osg/Geometry.cpp: Dispatcher-Wachstum nur fuer GLES')
else:
    print('src/osg/Geometry.cpp: schon eingegrenzt')
# ---- the remaining users of those members, in State.cpp and Program.cpp
wrap('src/osg/State.cpp', [
"""    /* fixed-function emulation (FlightGear GLES port): re-upload on program
       change or value change; PerContextProgram::apply skips unchanged ones. */
    if (_ffpDirty || _ffpLastProgram != _lastAppliedProgramObject)
    {
        _ffpLastProgram = _lastAppliedProgramObject;
        _ffpDirty = false;
        for (FFPUniformMap::const_iterator it = _ffpUniforms.begin(); it != _ffpUniforms.end(); ++it)
            _lastAppliedProgramObject->apply(*it->second);
    }
    if (_modelViewMatrixInverseUniform.valid() &&
        _lastAppliedProgramObject->getUniformLocation(_modelViewMatrixInverseUniform->getNameID()) >= 0)
    {
        Matrix inverse;
        inverse.invert(*_modelView);
        _modelViewMatrixInverseUniform->set(inverse);
        _lastAppliedProgramObject->apply(*_modelViewMatrixInverseUniform);
    }
    if (_modelViewMatrixTransposeUniform.valid() &&
        _lastAppliedProgramObject->getUniformLocation(_modelViewMatrixTransposeUniform->getNameID()) >= 0)
    {
        Matrix t;
        for (int i = 0; i < 4; ++i) for (int j = 0; j < 4; ++j) t(i, j) = (*_modelView)(j, i);
        _modelViewMatrixTransposeUniform->set(t);
        _lastAppliedProgramObject->apply(*_modelViewMatrixTransposeUniform);
    }
""",
])

# the converter core, the ffp setters and convertShaderSourceForGLES live between
# these two markers in State.cpp and are GLES only as a whole
p2 = os.path.join(ROOT, 'src/osg/State.cpp')
s2 = open(p2).read()
start_marker = "/* ===== fixed-function emulation for GLES builds (FlightGear port) ====="
end_marker = "bool State::convertVertexShaderSourceToOsgBuiltIns(std::string& source) const\n"
i = s2.index(start_marker)
j = s2.index(end_marker)
if not s2[:i].rstrip().endswith("#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)"):
    s2 = s2[:i] + GUARD_OPEN + s2[i:j] + GUARD_CLOSE + s2[j:]
    open(p2, 'w').write(s2)
    print('src/osg/State.cpp: Konverter und FFP-Setter nur fuer GLES')
else:
    print('src/osg/State.cpp: Konverter schon eingegrenzt')

# Program.cpp: mergeShadersForGLES definition
p3 = os.path.join(ROOT, 'src/osg/Program.cpp')
s3 = open(p3).read()
m_start = "void Program::PerContextProgram::mergeShadersForGLES(osg::State& state)"
m_end = "void Program::PerContextProgram::linkProgram(osg::State& state)"
i = s3.index(m_start)
j = s3.index(m_end)
if not s3[:i].rstrip().endswith("#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)"):
    s3 = s3[:i] + GUARD_OPEN + s3[i:j] + GUARD_CLOSE + s3[j:]
    open(p3, 'w').write(s3)
    print('src/osg/Program.cpp: mergeShadersForGLES nur fuer GLES')
else:
    print('src/osg/Program.cpp: schon eingegrenzt')

# linkProgram uses _mergedShaders
p5 = os.path.join(ROOT, 'src/osg/Program.cpp')
s5 = open(p5).read()
old5 = """        const bool useMerged = !_mergedShaders.empty();   /* FlightGear GLES port */
        const unsigned int shaderCount = useMerged ? _mergedShaders.size() : getProgram()->getNumShaders();
"""
new5 = """#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)
        const bool useMerged = !_mergedShaders.empty();   /* FlightGear GLES port */
        const unsigned int shaderCount = useMerged ? _mergedShaders.size() : getProgram()->getNumShaders();
#else
        const unsigned int shaderCount = getProgram()->getNumShaders();
#endif
"""
if new5 not in s5:
    assert s5.count(old5) == 1
    s5 = s5.replace(old5, new5)
    open(p5, 'w').write(s5)
    print('src/osg/Program.cpp: shaderCount nach Profil')
p4 = os.path.join(ROOT, 'src/osg/Program.cpp')
s4 = open(p4).read()
old4 = """            const Shader* shader = useMerged ? _mergedShaders[i].get() : getProgram()->getShader( i );"""
new4 = """#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)
            const Shader* shader = useMerged ? _mergedShaders[i].get() : getProgram()->getShader( i );
#else
            const Shader* shader = getProgram()->getShader( i );
#endif"""
if new4 not in s4:
    assert s4.count(old4) == 1
    s4 = s4.replace(old4, new4)
    open(p4, 'w').write(s4)
    print('src/osg/Program.cpp: Shaderauswahl nach Profil')

print('fertig')

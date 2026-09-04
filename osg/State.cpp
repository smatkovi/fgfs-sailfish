/* -*-c++-*- OpenSceneGraph - Copyright (C) 1998-2006 Robert Osfield
 *
 * This library is open source and may be redistributed and/or modified under
 * the terms of the OpenSceneGraph Public License (OSGPL) version 0.0 or
 * (at your option) any later version.  The full license is in LICENSE file
 * included with this distribution, and on the openscenegraph.org website.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * OpenSceneGraph Public License for more details.
*/
#include <osg/State>
#include <osg/Texture>
#include <osg/Notify>
#include <osg/GLU>
#include <osg/GLExtensions>
#include <osg/Drawable>
#include <osg/ApplicationUsage>
#include <osg/ContextData>
#include <osg/PointSprite>
#include <osg/os_utils>
#include <osg/io_utils>

#include <sstream>
#include <algorithm>
#include <regex>
#include <set>
#include <cmath>

#ifndef GL_MAX_TEXTURE_COORDS
#define GL_MAX_TEXTURE_COORDS 0x8871
#endif

#ifndef GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS
#define GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS 0x8B4D
#endif

#ifndef GL_MAX_TEXTURE_UNITS
#define GL_MAX_TEXTURE_UNITS 0x84E2
#endif

using namespace std;
using namespace osg;

static ApplicationUsageProxy State_e0(ApplicationUsage::ENVIRONMENTAL_VARIABLE,"OSG_GL_ERROR_CHECKING <type>","ONCE_PER_ATTRIBUTE | ON | on enables fine grained checking,  ONCE_PER_FRAME enables coarse grained checking");

State::State():
    Referenced(true)
{
    _graphicsContext = 0;
    _contextID = 0;

    _shaderCompositionEnabled = false;
    _shaderCompositionDirty = true;
    _shaderComposer = new ShaderComposer;
    _currentShaderCompositionProgram = 0L;

    _drawBuffer = GL_INVALID_ENUM; // avoid the lazy state mechanism from ignoreing the first call to State::glDrawBuffer() to make sure it's always passed to OpenGL
    _readBuffer = GL_INVALID_ENUM; // avoid the lazy state mechanism from ignoreing the first call to State::glReadBuffer() to make sure it's always passed to OpenGL

    _identity = new osg::RefMatrix(); // default RefMatrix constructs to identity.
    _initialViewMatrix = _identity;
    _projection = _identity;
    _modelView = _identity;
    _modelViewCache = new osg::RefMatrix;

    #if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)
        _useModelViewAndProjectionUniforms = true;
        _useVertexAttributeAliasing = true;
    #else
        _useModelViewAndProjectionUniforms = false;
        _useVertexAttributeAliasing = false;
    #endif

    _modelViewMatrixUniform = new Uniform(Uniform::FLOAT_MAT4,"osg_ModelViewMatrix");
    _projectionMatrixUniform = new Uniform(Uniform::FLOAT_MAT4,"osg_ProjectionMatrix");
    _modelViewProjectionMatrixUniform = new Uniform(Uniform::FLOAT_MAT4,"osg_ModelViewProjectionMatrix");
    _normalMatrixUniform = new Uniform(Uniform::FLOAT_MAT3,"osg_NormalMatrix");
#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)
    _modelViewMatrixInverseUniform = new Uniform(Uniform::FLOAT_MAT4,"osg_ModelViewMatrixInverse");
    _modelViewMatrixTransposeUniform = new Uniform(Uniform::FLOAT_MAT4,"osg_ModelViewMatrixTranspose");
    _ffpDirty = true;
#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)
    /* FlightGear GLES port: with FGFS_GLES_LEAN=1 the per-attribute check is
       pure cost - the errors it reports are the desktop-only modes above. */
    if (!::getenv("FGFS_GLES_FAT")) _checkGLErrors = NEVER_CHECK_GL_ERRORS;
#endif
    _ffpLastProgram = 0;
    initFFPUniforms();
#endif

    _fgfsNumAttribs = _fgfsNumModes = _fgfsNumDrawables = 0;

    resetVertexAttributeAlias();

    _abortRenderingPtr = NULL;

    _checkGLErrors = ONCE_PER_FRAME;

    std::string str;
    if (getEnvVar("OSG_GL_ERROR_CHECKING", str))
    {
        if (str=="ONCE_PER_ATTRIBUTE" || str=="ON" || str=="on")
        {
            _checkGLErrors = ONCE_PER_ATTRIBUTE;
        }
        else if (str=="OFF" || str=="off")
        {
            _checkGLErrors = NEVER_CHECK_GL_ERRORS;
        }
    }

    _currentActiveTextureUnit=0;
    _currentClientActiveTextureUnit=0;

    _currentPBO = 0;
    _currentDIBO = 0;
    _currentVAO = 0;

    _isSecondaryColorSupported = false;
    _isFogCoordSupported = false;
    _isVertexBufferObjectSupported = false;
    _isVertexArrayObjectSupported = false;

#if OSG_GL3_FEATURES
    _forceVertexBufferObject = true;
    _forceVertexArrayObject = true;
#else
    _forceVertexBufferObject = false;
    _forceVertexArrayObject = false;
#endif


    _lastAppliedProgramObject = 0;

    _extensionProcsInitialized = false;
    _glClientActiveTexture = 0;
    _glActiveTexture = 0;
    _glFogCoordPointer = 0;
    _glSecondaryColorPointer = 0;
    _glVertexAttribPointer = 0;
    _glVertexAttribIPointer = 0;
    _glVertexAttribLPointer = 0;
    _glEnableVertexAttribArray = 0;
    _glDisableVertexAttribArray = 0;
    _glDrawArraysInstanced = 0;
    _glDrawElementsInstanced = 0;
    _glMultiTexCoord4f = 0;
    _glVertexAttrib4fv = 0;
    _glVertexAttrib4f = 0;
    _glBindBuffer = 0;

    _dynamicObjectCount  = 0;

    _glMaxTextureCoords = 1;
    _glMaxTextureUnits = 1;

    _maxTexturePoolSize = 0;
    _maxBufferObjectPoolSize = 0;

    _arrayDispatchers.setState(this);

    _graphicsCostEstimator = new GraphicsCostEstimator;

    _startTick = 0;
    _gpuTick = 0;
    _gpuTimestamp = 0;
    _timestampBits = 0;

    _vas = 0;
}

State::~State()
{
    // delete the GLExtensions object associated with this osg::State.
    if (_glExtensions)
    {
        _glExtensions = 0;
        GLExtensions* glExtensions = GLExtensions::Get(_contextID, false);
        if (glExtensions && glExtensions->referenceCount() == 1) {
            // the only reference left to the extension is in the static map itself, so we clean it up now
            GLExtensions::Set(_contextID, 0);
        }
    }

    //_texCoordArrayList.clear();

    //_vertexAttribArrayList.clear();
}

void State::setUseVertexAttributeAliasing(bool flag)
{
    _useVertexAttributeAliasing = flag;
    if (_globalVertexArrayState.valid()) _globalVertexArrayState->assignAllDispatchers();
}

void State::initializeExtensionProcs()
{
    if (_extensionProcsInitialized) return;

    const char* vendor = (const char*) glGetString( GL_VENDOR );
    if (vendor)
    {
        std::string str_vendor(vendor);
        std::replace(str_vendor.begin(), str_vendor.end(), ' ', '_');
        OSG_INFO<<"GL_VENDOR = ["<<str_vendor<<"]"<<std::endl;
        _defineMap.map[str_vendor].defineVec.push_back(osg::StateSet::DefinePair("1",osg::StateAttribute::ON));
        _defineMap.map[str_vendor].changed = true;
        _defineMap.changed = true;
    }

    {
        const char* ver = (const char*) glGetString(GL_VERSION);
        const char* ren = (const char*) glGetString(GL_RENDERER);
        OSG_WARN << "STATEDBG vor GLExtensions::Get, GL_VERSION=["
                 << (ver ? ver : "NULL") << "] GL_RENDERER=["
                 << (ren ? ren : "NULL") << "]" << std::endl;
    }
    _glExtensions = GLExtensions::Get(_contextID, true);
    OSG_WARN << "STATEDBG GLExtensions::Get lieferte "
             << (void*)_glExtensions.get() << std::endl;
    if (!_glExtensions) {
        OSG_WARN << "STATEDBG: GLExtensions ist NULL - Abbruch" << std::endl;
        return;
    }

    _isSecondaryColorSupported = osg::isGLExtensionSupported(_contextID,"GL_EXT_secondary_color");
    _isFogCoordSupported = osg::isGLExtensionSupported(_contextID,"GL_EXT_fog_coord");
    _isVertexBufferObjectSupported = OSG_GLES2_FEATURES || OSG_GLES3_FEATURES || OSG_GL3_FEATURES || osg::isGLExtensionSupported(_contextID,"GL_ARB_vertex_buffer_object");
    _isVertexArrayObjectSupported = _glExtensions->isVAOSupported;

    const DisplaySettings* ds = getDisplaySettings() ? getDisplaySettings() : osg::DisplaySettings::instance().get();

    if (ds->getVertexBufferHint()==DisplaySettings::VERTEX_BUFFER_OBJECT)
    {
        _forceVertexBufferObject = true;
        _forceVertexArrayObject = false;
    }
    else if (ds->getVertexBufferHint()==DisplaySettings::VERTEX_ARRAY_OBJECT)
    {
        _forceVertexBufferObject = true;
        _forceVertexArrayObject = true;
    }

    OSG_INFO<<"osg::State::initializeExtensionProcs() _forceVertexArrayObject = "<<_forceVertexArrayObject<<std::endl;
    OSG_INFO<<"                                       _forceVertexBufferObject = "<<_forceVertexBufferObject<<std::endl;


    // Set up up global VertexArrayState object
    OSG_WARN << "STATEDBG vor VertexArrayState" << std::endl;
    _globalVertexArrayState = new VertexArrayState(this);
    OSG_WARN << "STATEDBG VertexArrayState angelegt" << std::endl;
    _globalVertexArrayState->assignAllDispatchers();
    OSG_WARN << "STATEDBG Dispatcher zugewiesen" << std::endl;
    // if (_useVertexArrayObject) _globalVertexArrayState->generateVertexArrayObject();

    setCurrentToGlobalVertexArrayState();


    setGLExtensionFuncPtr(_glClientActiveTexture,"glClientActiveTexture","glClientActiveTextureARB");
    setGLExtensionFuncPtr(_glActiveTexture, "glActiveTexture","glActiveTextureARB");
    setGLExtensionFuncPtr(_glFogCoordPointer, "glFogCoordPointer","glFogCoordPointerEXT");
    setGLExtensionFuncPtr(_glSecondaryColorPointer, "glSecondaryColorPointer","glSecondaryColorPointerEXT");
    setGLExtensionFuncPtr(_glVertexAttribPointer, "glVertexAttribPointer","glVertexAttribPointerARB");
    setGLExtensionFuncPtr(_glVertexAttribIPointer, "glVertexAttribIPointer");
    setGLExtensionFuncPtr(_glVertexAttribLPointer, "glVertexAttribLPointer","glVertexAttribPointerARB");
    setGLExtensionFuncPtr(_glEnableVertexAttribArray, "glEnableVertexAttribArray","glEnableVertexAttribArrayARB");
    setGLExtensionFuncPtr(_glMultiTexCoord4f, "glMultiTexCoord4f","glMultiTexCoord4fARB");
    setGLExtensionFuncPtr(_glVertexAttrib4f, "glVertexAttrib4f");
    setGLExtensionFuncPtr(_glVertexAttrib4fv, "glVertexAttrib4fv");
    setGLExtensionFuncPtr(_glDisableVertexAttribArray, "glDisableVertexAttribArray","glDisableVertexAttribArrayARB");
    setGLExtensionFuncPtr(_glBindBuffer, "glBindBuffer","glBindBufferARB");

    setGLExtensionFuncPtr(_glDrawArraysInstanced, "glDrawArraysInstanced","glDrawArraysInstancedARB","glDrawArraysInstancedEXT");
    setGLExtensionFuncPtr(_glDrawElementsInstanced, "glDrawElementsInstanced","glDrawElementsInstancedARB","glDrawElementsInstancedEXT");

    if (osg::getGLVersionNumber() >= 2.0 || osg::isGLExtensionSupported(_contextID, "GL_ARB_vertex_shader") || OSG_GLES2_FEATURES || OSG_GLES3_FEATURES || OSG_GL3_FEATURES)
    {
        glGetIntegerv(GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS,&_glMaxTextureUnits);
        #ifdef OSG_GL_FIXED_FUNCTION_AVAILABLE
            glGetIntegerv(GL_MAX_TEXTURE_COORDS, &_glMaxTextureCoords);
        #else
            _glMaxTextureCoords = _glMaxTextureUnits;
        #endif
    }
    else if ( osg::getGLVersionNumber() >= 1.3 ||
                                 osg::isGLExtensionSupported(_contextID,"GL_ARB_multitexture") ||
                                 osg::isGLExtensionSupported(_contextID,"GL_EXT_multitexture") ||
                                 OSG_GLES1_FEATURES)
    {
        GLint maxTextureUnits = 0;
        glGetIntegerv(GL_MAX_TEXTURE_UNITS,&maxTextureUnits);
        _glMaxTextureUnits = maxTextureUnits;
        _glMaxTextureCoords = maxTextureUnits;
    }
    else
    {
        _glMaxTextureUnits = 1;
        _glMaxTextureCoords = 1;
    }

    if (_glExtensions->isARBTimerQuerySupported)
    {
        const GLubyte* renderer = glGetString(GL_RENDERER);
        std::string rendererString = renderer ? (const char*)renderer : "";
        if (rendererString.find("Radeon")!=std::string::npos || rendererString.find("RADEON")!=std::string::npos || rendererString.find("FirePro")!=std::string::npos)
        {
            // AMD/ATI drivers are producing an invalid enumerate error on the
            // glGetQueryiv(GL_TIMESTAMP, GL_QUERY_COUNTER_BITS_ARB, &bits);
            // call so work around it by assuming 64 bits for counter.
            setTimestampBits(64);
            //setTimestampBits(0);
        }
        else
        {
            GLint bits = 0;
            _glExtensions->glGetQueryiv(GL_TIMESTAMP, GL_QUERY_COUNTER_BITS_ARB, &bits);
            setTimestampBits(bits);
        }
    }

    // set the validity of Modes
    {
        bool pointSpriteModeValid = _glExtensions->isPointSpriteModeSupported;

    #if defined( OSG_GLES1_AVAILABLE ) //point sprites don't exist on es 2.0
        setModeValidity(GL_POINT_SPRITE_OES, pointSpriteModeValid);
    #else
        setModeValidity(GL_POINT_SPRITE_ARB, pointSpriteModeValid);
    #endif
    }


    OSG_WARN << "STATEDBG initializeExtensionProcs fertig" << std::endl;
    _extensionProcsInitialized = true;

    if (_graphicsCostEstimator.valid())
    {
        RenderInfo renderInfo(this,0);
        _graphicsCostEstimator->calibrate(renderInfo);
    }
}

void State::releaseGLObjects()
{
    // release any GL objects held by the shader composer
    _shaderComposer->releaseGLObjects(this);

    // release any StateSet's on the stack
    for(StateSetStack::iterator itr = _stateStateStack.begin();
        itr != _stateStateStack.end();
        ++itr)
    {
        (*itr)->releaseGLObjects(this);
    }

    _modeMap.clear();
    _textureModeMapList.clear();

    // release any cached attributes
    for(AttributeMap::iterator aitr = _attributeMap.begin();
        aitr != _attributeMap.end();
        ++aitr)
    {
        AttributeStack& as = aitr->second;
        if (as.global_default_attribute.valid())
        {
            as.global_default_attribute->releaseGLObjects(this);
        }
    }
    _attributeMap.clear();

    // release any cached texture attributes
    for(TextureAttributeMapList::iterator itr = _textureAttributeMapList.begin();
        itr != _textureAttributeMapList.end();
        ++itr)
    {
        AttributeMap& attributeMap = *itr;
        for(AttributeMap::iterator aitr = attributeMap.begin();
            aitr != attributeMap.end();
            ++aitr)
        {
            AttributeStack& as = aitr->second;
            if (as.global_default_attribute.valid())
            {
                as.global_default_attribute->releaseGLObjects(this);
            }
        }
    }

    _textureAttributeMapList.clear();
}

void State::reset()
{
    OSG_NOTICE<<std::endl<<"State::reset() *************************** "<<std::endl;

#if 1
    for(ModeMap::iterator mitr=_modeMap.begin();
        mitr!=_modeMap.end();
        ++mitr)
    {
        ModeStack& ms = mitr->second;
        ms.valueVec.clear();
        ms.last_applied_value = !ms.global_default_value;
        ms.changed = true;
    }
#else
    _modeMap.clear();
#endif

    _modeMap[GL_DEPTH_TEST].global_default_value = true;
    _modeMap[GL_DEPTH_TEST].changed = true;

    // go through all active StateAttribute's, setting to change to force update,
    // the idea is to leave only the global defaults left.
    for(AttributeMap::iterator aitr=_attributeMap.begin();
        aitr!=_attributeMap.end();
        ++aitr)
    {
        AttributeStack& as = aitr->second;
        as.attributeVec.clear();
        as.last_applied_attribute = NULL;
        as.last_applied_shadercomponent = NULL;
        as.changed = true;
    }

    // we can do a straight clear, we aren't interested in GL_DEPTH_TEST defaults in texture modes.
    for(TextureModeMapList::iterator tmmItr=_textureModeMapList.begin();
        tmmItr!=_textureModeMapList.end();
        ++tmmItr)
    {
        tmmItr->clear();
    }

    // empty all the texture attributes as per normal attributes, leaving only the global defaults left.
    for(TextureAttributeMapList::iterator tamItr=_textureAttributeMapList.begin();
        tamItr!=_textureAttributeMapList.end();
        ++tamItr)
    {
        AttributeMap& attributeMap = *tamItr;
        // go through all active StateAttribute's, setting to change to force update.
        for(AttributeMap::iterator aitr=attributeMap.begin();
            aitr!=attributeMap.end();
            ++aitr)
        {
            AttributeStack& as = aitr->second;
            as.attributeVec.clear();
            as.last_applied_attribute = NULL;
            as.last_applied_shadercomponent = NULL;
            as.changed = true;
        }
    }

    _stateStateStack.clear();

    _modelView = _identity;
    _projection = _identity;

    dirtyAllVertexArrays();

#if 1
    // reset active texture unit values and call OpenGL
    // note, this OpenGL op precludes the use of State::reset() without a
    // valid graphics context, therefore the new implementation below
    // is preferred.
    setActiveTextureUnit(0);
#else
    // reset active texture unit values without calling OpenGL
    _currentActiveTextureUnit = 0;
    _currentClientActiveTextureUnit = 0;
#endif

    _shaderCompositionDirty = true;
    _currentShaderCompositionUniformList.clear();

    _lastAppliedProgramObject = 0;

    // what about uniforms??? need to clear them too...
    // go through all active Uniform's, setting to change to force update,
    // the idea is to leave only the global defaults left.
    for(UniformMap::iterator uitr=_uniformMap.begin();
        uitr!=_uniformMap.end();
        ++uitr)
    {
        UniformStack& us = uitr->second;
        us.uniformVec.clear();
    }

}

void State::glDrawBuffer(GLenum buffer)
{
    if (_drawBuffer!=buffer)
    {
        #if !defined(OSG_GLES1_AVAILABLE) && !defined(OSG_GLES2_AVAILABLE) && !defined(OSG_GLES3_AVAILABLE)
        ::glDrawBuffer(buffer);
        #endif
        _drawBuffer=buffer;
    }
}

void State::glReadBuffer(GLenum buffer)
{
    if (_readBuffer!=buffer)
    {
        #if !defined(OSG_GLES1_AVAILABLE) && !defined(OSG_GLES2_AVAILABLE) && !defined(OSG_GLES3_AVAILABLE)
        ::glReadBuffer(buffer);
        #endif
        _readBuffer=buffer;
    }
}

void State::setInitialViewMatrix(const osg::RefMatrix* matrix)
{
    if (matrix) _initialViewMatrix = matrix;
    else _initialViewMatrix = _identity;

    _initialInverseViewMatrix.invert(*_initialViewMatrix);
}

void State::setMaxTexturePoolSize(unsigned int size)
{
    _maxTexturePoolSize = size;
    osg::get<TextureObjectManager>(_contextID)->setMaxTexturePoolSize(size);
    OSG_INFO<<"osg::State::_maxTexturePoolSize="<<_maxTexturePoolSize<<std::endl;
}

void State::setMaxBufferObjectPoolSize(unsigned int size)
{
    _maxBufferObjectPoolSize = size;
    osg::get<GLBufferObjectManager>(_contextID)->setMaxGLBufferObjectPoolSize(_maxBufferObjectPoolSize);
    OSG_INFO<<"osg::State::_maxBufferObjectPoolSize="<<_maxBufferObjectPoolSize<<std::endl;
}

void State::pushStateSet(const StateSet* dstate)
{

    _stateStateStack.push_back(dstate);
    if (dstate)
    {

        pushModeList(_modeMap,dstate->getModeList());

        // iterator through texture modes.
        unsigned int unit;
        const StateSet::TextureModeList& ds_textureModeList = dstate->getTextureModeList();
        for(unit=0;unit<ds_textureModeList.size();++unit)
        {
            pushModeList(getOrCreateTextureModeMap(unit),ds_textureModeList[unit]);
        }

        pushAttributeList(_attributeMap,dstate->getAttributeList());

        // iterator through texture attributes.
        const StateSet::TextureAttributeList& ds_textureAttributeList = dstate->getTextureAttributeList();
        for(unit=0;unit<ds_textureAttributeList.size();++unit)
        {
            pushAttributeList(getOrCreateTextureAttributeMap(unit),ds_textureAttributeList[unit]);
        }

        pushUniformList(_uniformMap,dstate->getUniformList());

        pushDefineList(_defineMap,dstate->getDefineList());
    }

    // OSG_NOTICE<<"State::pushStateSet()"<<_stateStateStack.size()<<std::endl;
}

void State::popAllStateSets()
{
    // OSG_NOTICE<<"State::popAllStateSets()"<<_stateStateStack.size()<<std::endl;

    while (!_stateStateStack.empty()) popStateSet();

    applyProjectionMatrix(0);
    applyModelViewMatrix(0);

    _lastAppliedProgramObject = 0;
}

void State::popStateSet()
{
    // OSG_NOTICE<<"State::popStateSet()"<<_stateStateStack.size()<<std::endl;

    if (_stateStateStack.empty()) return;


    const StateSet* dstate = _stateStateStack.back();

    if (dstate)
    {

        popModeList(_modeMap,dstate->getModeList());

        // iterator through texture modes.
        unsigned int unit;
        const StateSet::TextureModeList& ds_textureModeList = dstate->getTextureModeList();
        for(unit=0;unit<ds_textureModeList.size();++unit)
        {
            popModeList(getOrCreateTextureModeMap(unit),ds_textureModeList[unit]);
        }

        popAttributeList(_attributeMap,dstate->getAttributeList());

        // iterator through texture attributes.
        const StateSet::TextureAttributeList& ds_textureAttributeList = dstate->getTextureAttributeList();
        for(unit=0;unit<ds_textureAttributeList.size();++unit)
        {
            popAttributeList(getOrCreateTextureAttributeMap(unit),ds_textureAttributeList[unit]);
        }

        popUniformList(_uniformMap,dstate->getUniformList());

        popDefineList(_defineMap,dstate->getDefineList());

    }

    // remove the top draw state from the stack.
    _stateStateStack.pop_back();
}

void State::insertStateSet(unsigned int pos,const StateSet* dstate)
{
    StateSetStack tempStack;

    // first pop the StateSet above the position we need to insert at
    while (_stateStateStack.size()>pos)
    {
        tempStack.push_back(_stateStateStack.back());
        popStateSet();
    }

    // push our new stateset
    pushStateSet(dstate);

    // push back the original ones
    for(StateSetStack::reverse_iterator itr = tempStack.rbegin();
        itr != tempStack.rend();
        ++itr)
    {
        pushStateSet(*itr);
    }

}

void State::removeStateSet(unsigned int pos)
{
    if (pos >= _stateStateStack.size())
    {
        OSG_NOTICE<<"Warning: State::removeStateSet("<<pos<<") out of range"<<std::endl;
        return;
    }

    // record the StateSet above the one we intend to remove
    StateSetStack tempStack;
    while (_stateStateStack.size()-1>pos)
    {
        tempStack.push_back(_stateStateStack.back());
        popStateSet();
    }

    // remove the intended StateSet as well
    popStateSet();

    // push back the original ones that were above the remove StateSet
    for(StateSetStack::reverse_iterator itr = tempStack.rbegin();
        itr != tempStack.rend();
        ++itr)
    {
        pushStateSet(*itr);
    }
}

void State::captureCurrentState(StateSet& stateset) const
{
    // empty the stateset first.
    stateset.clear();

    for(ModeMap::const_iterator mitr=_modeMap.begin();
        mitr!=_modeMap.end();
        ++mitr)
    {
        // note GLMode = mitr->first
        const ModeStack& ms = mitr->second;
        if (!ms.valueVec.empty())
        {
            stateset.setMode(mitr->first,ms.valueVec.back());
        }
    }

    for(AttributeMap::const_iterator aitr=_attributeMap.begin();
        aitr!=_attributeMap.end();
        ++aitr)
    {
        const AttributeStack& as = aitr->second;
        if (!as.attributeVec.empty())
        {
            stateset.setAttribute(const_cast<StateAttribute*>(as.attributeVec.back().first));
        }
    }

}

void State::apply(const StateSet* dstate)
{
    if (_checkGLErrors==ONCE_PER_ATTRIBUTE) checkGLErrors("start of State::apply(StateSet*)");

    // equivalent to:
    //pushStateSet(dstate);
    //apply();
    //popStateSet();
    //return;

    if (dstate)
    {
        // push the stateset on the stack so it can be querried from within StateAttribute
        _stateStateStack.push_back(dstate);

        _currentShaderCompositionUniformList.clear();

        // apply all texture state and modes
        const StateSet::TextureModeList& ds_textureModeList = dstate->getTextureModeList();
        const StateSet::TextureAttributeList& ds_textureAttributeList = dstate->getTextureAttributeList();

        unsigned int unit;
        unsigned int unitMax = maximum(static_cast<unsigned int>(ds_textureModeList.size()),static_cast<unsigned int>(ds_textureAttributeList.size()));
        unitMax = maximum(static_cast<unsigned int>(unitMax),static_cast<unsigned int>(_textureModeMapList.size()));
        unitMax = maximum(static_cast<unsigned int>(unitMax),static_cast<unsigned int>(_textureAttributeMapList.size()));
        for(unit=0;unit<unitMax;++unit)
        {
            if (unit<ds_textureModeList.size()) applyModeListOnTexUnit(unit,getOrCreateTextureModeMap(unit),ds_textureModeList[unit]);
            else if (unit<_textureModeMapList.size()) applyModeMapOnTexUnit(unit,_textureModeMapList[unit]);

            if (unit<ds_textureAttributeList.size()) applyAttributeListOnTexUnit(unit,getOrCreateTextureAttributeMap(unit),ds_textureAttributeList[unit]);
            else if (unit<_textureAttributeMapList.size()) applyAttributeMapOnTexUnit(unit,_textureAttributeMapList[unit]);
        }

        const Program::PerContextProgram* previousLastAppliedProgramObject = _lastAppliedProgramObject;

        applyModeList(_modeMap,dstate->getModeList());
#if 1
        pushDefineList(_defineMap, dstate->getDefineList());
#else
        applyDefineList(_defineMap, dstate->getDefineList());
#endif

        applyAttributeList(_attributeMap,dstate->getAttributeList());

        if ((_lastAppliedProgramObject!=0) && (previousLastAppliedProgramObject==_lastAppliedProgramObject) && _defineMap.changed)
        {
            // OSG_NOTICE<<"State::apply(StateSet*) Program already applied ("<<(previousLastAppliedProgramObject==_lastAppliedProgramObject)<<") and _defineMap.changed= "<<_defineMap.changed<<std::endl;
            _lastAppliedProgramObject->getProgram()->apply(*this);
        }

        if (_shaderCompositionEnabled)
        {
            if (previousLastAppliedProgramObject == _lastAppliedProgramObject || _lastAppliedProgramObject==0)
            {
                // No program has been applied by the StateSet stack so assume shader composition is required
                applyShaderComposition();
            }
        }

#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)
        applyFallbackProgramIfNeeded();   /* FlightGear GLES port */
#endif
        if (dstate->getUniformList().empty())
        {
            if (_currentShaderCompositionUniformList.empty()) applyUniformMap(_uniformMap);
            else applyUniformList(_uniformMap, _currentShaderCompositionUniformList);
        }
        else
        {
            if (_currentShaderCompositionUniformList.empty()) applyUniformList(_uniformMap, dstate->getUniformList());
            else
            {
                // need top merge uniforms lists, but cheat for now by just applying both.
                _currentShaderCompositionUniformList.insert(dstate->getUniformList().begin(), dstate->getUniformList().end());
                applyUniformList(_uniformMap, _currentShaderCompositionUniformList);
            }
        }

#if 1
        popDefineList(_defineMap, dstate->getDefineList());
#endif

        // pop the stateset from the stack
        _stateStateStack.pop_back();
    }
    else
    {
        // no incoming stateset, so simply apply state.
        apply();
    }

    if (_checkGLErrors==ONCE_PER_ATTRIBUTE) checkGLErrors("end of State::apply(StateSet*)");
}

void State::apply()
{
    if (_checkGLErrors==ONCE_PER_ATTRIBUTE) checkGLErrors("start of State::apply()");

    _currentShaderCompositionUniformList.clear();

    // apply all texture state and modes
    unsigned int unit;
    unsigned int unitMax = maximum(_textureModeMapList.size(),_textureAttributeMapList.size());
    for(unit=0;unit<unitMax;++unit)
    {
        if (unit<_textureModeMapList.size()) applyModeMapOnTexUnit(unit,_textureModeMapList[unit]);
        if (unit<_textureAttributeMapList.size()) applyAttributeMapOnTexUnit(unit,_textureAttributeMapList[unit]);
    }

    // go through all active OpenGL modes, enabling/disable where
    // appropriate.
    applyModeMap(_modeMap);

    const Program::PerContextProgram* previousLastAppliedProgramObject = _lastAppliedProgramObject;

    // go through all active StateAttribute's, applying where appropriate.
    applyAttributeMap(_attributeMap);


    if ((_lastAppliedProgramObject!=0) && (previousLastAppliedProgramObject==_lastAppliedProgramObject) && _defineMap.changed)
    {
        //OSG_NOTICE<<"State::apply() Program already applied ("<<(previousLastAppliedProgramObject==_lastAppliedProgramObject)<<") and _defineMap.changed= "<<_defineMap.changed<<std::endl;
        if (_lastAppliedProgramObject) _lastAppliedProgramObject->getProgram()->apply(*this);
    }


    if (_shaderCompositionEnabled)
    {
        applyShaderComposition();
    }

#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)
    applyFallbackProgramIfNeeded();   /* FlightGear GLES port */
#endif
    if (_currentShaderCompositionUniformList.empty()) applyUniformMap(_uniformMap);
    else applyUniformList(_uniformMap, _currentShaderCompositionUniformList);

    if (_checkGLErrors==ONCE_PER_ATTRIBUTE) checkGLErrors("end of State::apply()");
}

void State::applyShaderComposition()
{
    if (_shaderCompositionEnabled)
    {
        if (_shaderCompositionDirty)
        {
            // if (isNotifyEnabled(osg::INFO)) print(notify(osg::INFO));

            // build lits of current ShaderComponents
            ShaderComponents shaderComponents;

            // OSG_NOTICE<<"State::applyShaderComposition() : _attributeMap.size()=="<<_attributeMap.size()<<std::endl;

            for(AttributeMap::iterator itr = _attributeMap.begin();
                itr != _attributeMap.end();
                ++itr)
            {
                // OSG_NOTICE<<"  itr->first="<<itr->first.first<<", "<<itr->first.second<<std::endl;

                AttributeStack& as = itr->second;
                if (as.last_applied_shadercomponent)
                {
                    shaderComponents.push_back(const_cast<ShaderComponent*>(as.last_applied_shadercomponent));
                }
            }

            _currentShaderCompositionProgram = _shaderComposer->getOrCreateProgram(shaderComponents);
        }

        if (_currentShaderCompositionProgram)
        {
            Program::PerContextProgram* pcp = _currentShaderCompositionProgram->getPCP(*this);
            if (_lastAppliedProgramObject != pcp) applyAttribute(_currentShaderCompositionProgram);
        }
    }
}


void State::haveAppliedMode(StateAttribute::GLMode mode,StateAttribute::GLModeValue value)
{
    haveAppliedMode(_modeMap,mode,value);
}

void State::haveAppliedMode(StateAttribute::GLMode mode)
{
    haveAppliedMode(_modeMap,mode);
}

void State::haveAppliedAttribute(const StateAttribute* attribute)
{
    haveAppliedAttribute(_attributeMap,attribute);
}

void State::haveAppliedAttribute(StateAttribute::Type type, unsigned int member)
{
    haveAppliedAttribute(_attributeMap,type,member);
}

bool State::getLastAppliedMode(StateAttribute::GLMode mode) const
{
    return getLastAppliedMode(_modeMap,mode);
}

const StateAttribute* State::getLastAppliedAttribute(StateAttribute::Type type, unsigned int member) const
{
    return getLastAppliedAttribute(_attributeMap,type,member);
}


void State::haveAppliedTextureMode(unsigned int unit,StateAttribute::GLMode mode,StateAttribute::GLModeValue value)
{
    haveAppliedMode(getOrCreateTextureModeMap(unit),mode,value);
}

void State::haveAppliedTextureMode(unsigned int unit,StateAttribute::GLMode mode)
{
    haveAppliedMode(getOrCreateTextureModeMap(unit),mode);
}

void State::haveAppliedTextureAttribute(unsigned int unit,const StateAttribute* attribute)
{
    haveAppliedAttribute(getOrCreateTextureAttributeMap(unit),attribute);
}

void State::haveAppliedTextureAttribute(unsigned int unit,StateAttribute::Type type, unsigned int member)
{
    haveAppliedAttribute(getOrCreateTextureAttributeMap(unit),type,member);
}

bool State::getLastAppliedTextureMode(unsigned int unit,StateAttribute::GLMode mode) const
{
    if (unit>=_textureModeMapList.size()) return false;
    return getLastAppliedMode(_textureModeMapList[unit],mode);
}

const StateAttribute* State::getLastAppliedTextureAttribute(unsigned int unit,StateAttribute::Type type, unsigned int member) const
{
    if (unit>=_textureAttributeMapList.size()) return NULL;
    return getLastAppliedAttribute(_textureAttributeMapList[unit],type,member);
}


void State::haveAppliedMode(ModeMap& modeMap,StateAttribute::GLMode mode,StateAttribute::GLModeValue value)
{
    ModeStack& ms = modeMap[mode];

    ms.last_applied_value = value & StateAttribute::ON;

    // will need to disable this mode on next apply so set it to changed.
    ms.changed = true;
}

/** mode has been set externally, update state to reflect this setting.*/
void State::haveAppliedMode(ModeMap& modeMap,StateAttribute::GLMode mode)
{
    ModeStack& ms = modeMap[mode];

    // don't know what last applied value is can't apply it.
    // assume that it has changed by toggle the value of last_applied_value.
    ms.last_applied_value = !ms.last_applied_value;

    // will need to disable this mode on next apply so set it to changed.
    ms.changed = true;
}

/** attribute has been applied externally, update state to reflect this setting.*/
void State::haveAppliedAttribute(AttributeMap& attributeMap,const StateAttribute* attribute)
{
    if (attribute)
    {
        AttributeStack& as = attributeMap[attribute->getTypeMemberPair()];

        as.last_applied_attribute = attribute;

        // will need to update this attribute on next apply so set it to changed.
        as.changed = true;
    }
}

void State::haveAppliedAttribute(AttributeMap& attributeMap,StateAttribute::Type type, unsigned int member)
{

    AttributeMap::iterator itr = attributeMap.find(StateAttribute::TypeMemberPair(type,member));
    if (itr!=attributeMap.end())
    {
        AttributeStack& as = itr->second;
        as.last_applied_attribute = 0L;

        // will need to update this attribute on next apply so set it to changed.
        as.changed = true;
    }
}

bool State::getLastAppliedMode(const ModeMap& modeMap,StateAttribute::GLMode mode) const
{
    ModeMap::const_iterator itr = modeMap.find(mode);
    if (itr!=modeMap.end())
    {
        const ModeStack& ms = itr->second;
        return ms.last_applied_value;
    }
    else
    {
        return false;
    }
}

const StateAttribute* State::getLastAppliedAttribute(const AttributeMap& attributeMap,StateAttribute::Type type, unsigned int member) const
{
    AttributeMap::const_iterator itr = attributeMap.find(StateAttribute::TypeMemberPair(type,member));
    if (itr!=attributeMap.end())
    {
        const AttributeStack& as = itr->second;
        return as.last_applied_attribute;
    }
    else
    {
        return NULL;
    }
}

void State::dirtyAllModes()
{
    for(ModeMap::iterator mitr=_modeMap.begin();
        mitr!=_modeMap.end();
        ++mitr)
    {
        ModeStack& ms = mitr->second;
        ms.last_applied_value = !ms.last_applied_value;
        ms.changed = true;

    }

    for(TextureModeMapList::iterator tmmItr=_textureModeMapList.begin();
        tmmItr!=_textureModeMapList.end();
        ++tmmItr)
    {
        for(ModeMap::iterator mitr=tmmItr->begin();
            mitr!=tmmItr->end();
            ++mitr)
        {
            ModeStack& ms = mitr->second;
            ms.last_applied_value = !ms.last_applied_value;
            ms.changed = true;

        }
    }
}

void State::dirtyAllAttributes()
{
    for(AttributeMap::iterator aitr=_attributeMap.begin();
        aitr!=_attributeMap.end();
        ++aitr)
    {
        AttributeStack& as = aitr->second;
        as.last_applied_attribute = 0;
        as.changed = true;
    }


    for(TextureAttributeMapList::iterator tamItr=_textureAttributeMapList.begin();
        tamItr!=_textureAttributeMapList.end();
        ++tamItr)
    {
        AttributeMap& attributeMap = *tamItr;
        for(AttributeMap::iterator aitr=attributeMap.begin();
            aitr!=attributeMap.end();
            ++aitr)
        {
            AttributeStack& as = aitr->second;
            as.last_applied_attribute = 0;
            as.changed = true;
        }
    }

}


Polytope State::getViewFrustum() const
{
    Polytope cv;
    cv.setToUnitFrustum();
    cv.transformProvidingInverse((*_modelView)*(*_projection));
    return cv;
}


void State::resetVertexAttributeAlias(bool compactAliasing, unsigned int numTextureUnits)
{
    _texCoordAliasList.clear();
    _attributeBindingList.clear();

    if (compactAliasing)
    {
        unsigned int slot = 0;
        setUpVertexAttribAlias(_vertexAlias, slot++, "gl_Vertex","osg_Vertex","vec4 ");
        setUpVertexAttribAlias(_normalAlias, slot++, "gl_Normal","osg_Normal","vec3 ");
        setUpVertexAttribAlias(_colorAlias, slot++, "gl_Color","osg_Color","vec4 ");

        _texCoordAliasList.resize(numTextureUnits);
        for(unsigned int i=0; i<_texCoordAliasList.size(); i++)
        {
            std::stringstream gl_MultiTexCoord;
            std::stringstream osg_MultiTexCoord;
            gl_MultiTexCoord<<"gl_MultiTexCoord"<<i;
            osg_MultiTexCoord<<"osg_MultiTexCoord"<<i;

            setUpVertexAttribAlias(_texCoordAliasList[i], slot++, gl_MultiTexCoord.str(), osg_MultiTexCoord.str(), "vec4 ");
        }

        setUpVertexAttribAlias(_secondaryColorAlias, slot++, "gl_SecondaryColor","osg_SecondaryColor","vec4 ");
        setUpVertexAttribAlias(_fogCoordAlias, slot++, "gl_FogCoord","osg_FogCoord","float ");

    }
    else
    {
        setUpVertexAttribAlias(_vertexAlias,0, "gl_Vertex","osg_Vertex","vec4 ");
        setUpVertexAttribAlias(_normalAlias, 2, "gl_Normal","osg_Normal","vec3 ");
        setUpVertexAttribAlias(_colorAlias, 3, "gl_Color","osg_Color","vec4 ");
        setUpVertexAttribAlias(_secondaryColorAlias, 4, "gl_SecondaryColor","osg_SecondaryColor","vec4 ");
        setUpVertexAttribAlias(_fogCoordAlias, 5, "gl_FogCoord","osg_FogCoord","float ");

        unsigned int base = 8;
        _texCoordAliasList.resize(numTextureUnits);
        for(unsigned int i=0; i<_texCoordAliasList.size(); i++)
        {
            std::stringstream gl_MultiTexCoord;
            std::stringstream osg_MultiTexCoord;
            gl_MultiTexCoord<<"gl_MultiTexCoord"<<i;
            osg_MultiTexCoord<<"osg_MultiTexCoord"<<i;

            setUpVertexAttribAlias(_texCoordAliasList[i], base+i, gl_MultiTexCoord.str(), osg_MultiTexCoord.str(), "vec4 ");
        }
    }
}


void State::disableAllVertexArrays()
{
    disableVertexPointer();
    disableColorPointer();
    disableFogCoordPointer();
    disableNormalPointer();
    disableSecondaryColorPointer();
    disableTexCoordPointersAboveAndIncluding(0);
    disableVertexAttribPointersAboveAndIncluding(0);
}

void State::dirtyAllVertexArrays()
{
    OSG_INFO<<"State::dirtyAllVertexArrays()"<<std::endl;
}

bool State::setClientActiveTextureUnit( unsigned int unit )
{
    // if (true)
    if (_currentClientActiveTextureUnit!=unit)
    {
        // OSG_NOTICE<<"State::setClientActiveTextureUnit( "<<unit<<") done"<<std::endl;

        _glClientActiveTexture(GL_TEXTURE0+unit);

        _currentClientActiveTextureUnit = unit;
    }
    else
    {
        //OSG_NOTICE<<"State::setClientActiveTextureUnit( "<<unit<<") not required."<<std::endl;
    }
    return true;
}


unsigned int State::getClientActiveTextureUnit() const
{
    return _currentClientActiveTextureUnit;
}


bool State::checkGLErrors(const char* str1, const char* str2) const
{
    GLenum errorNo = glGetError();
    if (errorNo!=GL_NO_ERROR)
    {
        osg::NotifySeverity notifyLevel = NOTICE; // WARN;
        const char* error = (char*)gluErrorString(errorNo);
        if (error)
        {
            OSG_NOTIFY(notifyLevel)<<"Warning: detected OpenGL error '" << error<<"'";
        }
        else
        {
            OSG_NOTIFY(notifyLevel)<<"Warning: detected OpenGL error number 0x" << std::hex << errorNo << std::dec;
        }

        if (str1 || str2)
        {
            OSG_NOTIFY(notifyLevel)<<" at";
            if (str1) { OSG_NOTIFY(notifyLevel)<<" "<<str1; }
            if (str2) { OSG_NOTIFY(notifyLevel)<<" "<<str2; }
        }
        else
        {
            OSG_NOTIFY(notifyLevel)<<" in osg::State.";
        }

        OSG_NOTIFY(notifyLevel)<< std::endl;

        return true;
    }
    return false;
}

bool State::checkGLErrors(StateAttribute::GLMode mode) const
{
    GLenum errorNo = glGetError();
    if (errorNo!=GL_NO_ERROR)
    {
        const char* error = (char*)gluErrorString(errorNo);
        if (error)
        {
            OSG_NOTIFY(WARN)<<"Warning: detected OpenGL error '"<< error <<"' after applying GLMode 0x"<<hex<<mode<<dec<< std::endl;
        }
        else
        {
            OSG_NOTIFY(WARN)<<"Warning: detected OpenGL error number 0x"<< std::hex << errorNo <<" after applying GLMode 0x"<<hex<<mode<<dec<< std::endl;
        }
        return true;
    }
    return false;
}

bool State::checkGLErrors(const StateAttribute* attribute) const
{
    GLenum errorNo = glGetError();
    if (errorNo!=GL_NO_ERROR)
    {
        const char* error = (char*)gluErrorString(errorNo);
        if (error)
        {
            OSG_NOTIFY(WARN)<<"Warning: detected OpenGL error '"<< error <<"' after applying attribute "<<attribute->className()<<" "<<attribute<< std::endl;
        }
        else
        {
            OSG_NOTIFY(WARN)<<"Warning: detected OpenGL error number 0x"<< std::hex << errorNo <<" after applying attribute "<<attribute->className()<<" "<<attribute<< std::dec << std::endl;
        }

        return true;
    }
    return false;
}


void State::applyModelViewAndProjectionUniformsIfRequired()
{
    if (!_lastAppliedProgramObject) return;

    if (_modelViewMatrixUniform.valid()) _lastAppliedProgramObject->apply(*_modelViewMatrixUniform);
    if (_projectionMatrixUniform) _lastAppliedProgramObject->apply(*_projectionMatrixUniform);
    if (_modelViewProjectionMatrixUniform) _lastAppliedProgramObject->apply(*_modelViewProjectionMatrixUniform);
    if (_normalMatrixUniform) _lastAppliedProgramObject->apply(*_normalMatrixUniform);

#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)
    /* fixed-function emulation (FlightGear GLES port): re-upload on program
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
#endif
}

namespace State_Utils
{
    bool replace(std::string& str, const std::string& original_phrase, const std::string& new_phrase)
    {
        // Prevent infinite loop : if original_phrase is empty, do nothing and return false
        if (original_phrase.empty()) return false;

        bool replacedStr = false;
        std::string::size_type pos = 0;
        while((pos=str.find(original_phrase, pos))!=std::string::npos)
        {
            std::string::size_type endOfPhrasePos = pos+original_phrase.size();
            if (endOfPhrasePos<str.size())
            {
                char c = str[endOfPhrasePos];
                if ((c>='0' && c<='9') ||
                    (c>='a' && c<='z') ||
                    (c>='A' && c<='Z'))
                {
                    pos = endOfPhrasePos;
                    continue;
                }
            }

            replacedStr = true;
            str.replace(pos, original_phrase.size(), new_phrase);
        }
        return replacedStr;
    }

    void replaceAndInsertDeclaration(std::string& source, std::string::size_type declPos, const std::string& originalStr, const std::string& newStr, const std::string& qualifier, const std::string& declarationPrefix)
    {
        if (replace(source, originalStr, newStr))
        {
            source.insert(declPos, qualifier + declarationPrefix + newStr + std::string(";\n"));
        }
    }

    void replaceVar(const osg::State& state, std::string& str, std::string::size_type start_pos,  std::string::size_type num_chars)
    {
        std::string var_str(str.substr(start_pos+1, num_chars-1));
        std::string value;
        if (state.getActiveDisplaySettings()->getValue(var_str, value))
        {
            str.replace(start_pos, num_chars, value);
        }
        else
        {
            str.erase(start_pos, num_chars);
        }
    }


    void substitudeEnvVars(const osg::State& state, std::string& str)
    {
        std::string::size_type pos = 0;
        while (pos<str.size() && ((pos=str.find_first_of("$'\"", pos)) != std::string::npos))
        {
            if (pos==str.size())
            {
                break;
            }

            if (str[pos]=='"' || str[pos]=='\'')
            {
                std::string::size_type start_quote = pos;
                ++pos; // skip over first quote
                pos = str.find(str[start_quote], pos);

                if (pos!=std::string::npos)
                {
                    ++pos; // skip over second quote
                }
            }
            else
            {
                std::string::size_type start_var = pos;
                ++pos;
                pos = str.find_first_not_of("ABCDEFGHIJKLMNOPQRTSUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_", pos);
                if (pos != std::string::npos)
                {

                    replaceVar(state, str, start_var, pos-start_var);
                    pos = start_var;
                }
                else
                {
                    replaceVar(state, str, start_var, str.size()-start_var);
                    pos = start_var;
                }
            }
        }
    }
}

#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)
/* ===== fixed-function emulation for GLES builds (FlightGear port) =====
 * FlightGear's effects are desktop GLSL 1.20 against the fixed-function
 * built-ins; GLES has neither.  convertShaderSourceForGLES() rewrites the
 * source, and Light/Material/LightModel/Fog/TexMat feed the setters below,
 * whose values reach the current program as osg_* uniforms. */
namespace osg_gles
{
    struct Alias
    {
        std::string glName, osgName, declaration;   /* e.g. gl_Vertex, osg_Vertex, "vec4 " */
    };

    /* Same semantics as osg::State_Utils::replace: the match must not be
       followed by an identifier character. */
    inline bool replaceWord(std::string& str, const std::string& original, const std::string& replacement)
    {
        if (original.empty()) return false;
        bool replaced = false;
        std::string::size_type pos = 0;
        while ((pos = str.find(original, pos)) != std::string::npos)
        {
            std::string::size_type end = pos + original.size();
            if (end < str.size())
            {
                char c = str[end];
                if ((c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_')
                {
                    pos = end;
                    continue;
                }
            }
            str.replace(pos, original.size(), replacement);
            pos += replacement.size();
            replaced = true;
        }
        return replaced;
    }

    inline bool contains(const std::string& str, const std::string& what)
    {
        return str.find(what) != std::string::npos;
    }

    inline void addDecl(std::vector<std::string>& decls, const std::string& decl)
    {
        for (std::vector<std::string>::const_iterator it = decls.begin(); it != decls.end(); ++it)
            if (*it == decl) return;
        decls.push_back(decl);
    }

    /* ES 1.00 only allows constant expressions as global initialisers.
       Split "type name = expr;" at brace depth 0 into a plain declaration
       and remember the assignment for main(). */
    inline std::string hoistGlobalInitialisers(const std::string& src, std::vector<std::string>& hoisted)
    {
        static const std::regex decl("^(\\s*)(float|int|bool|vec[234]|ivec[234]|mat[234])\\s+([A-Za-z_][A-Za-z0-9_]*)\\s*=\\s*([^;]+);(.*)$");
        static const std::regex literal("^[\\s\\d.,()eE+*/-]*$");
        std::ostringstream out;
        std::istringstream in(src);
        std::string line;
        int depth = 0;
        bool first = true;
        while (std::getline(in, line))
        {
            if (!first) out << '\n';
            first = false;
            std::string code = line.substr(0, line.find("//"));
            std::smatch m;
            if (depth == 0 && std::regex_match(line, m, decl) && !std::regex_match(m[4].str(), literal)
                && !contains(code, "const"))
            {
                out << m[1].str() << m[2].str() << ' ' << m[3].str() << ';' << m[5].str();
                std::string rhs = m[4].str();
                std::string::size_type a = rhs.find_first_not_of(" \t"), b = rhs.find_last_not_of(" \t");
                hoisted.push_back(m[3].str() + " = " + rhs.substr(a, b - a + 1) + ";");
                continue;
            }
            for (std::string::size_type i = 0; i < code.size(); ++i)
            {
                if (code[i] == '{') ++depth;
                else if (code[i] == '}') --depth;
            }
            out << line;
        }
        return out.str();
    }

    /* Comment out #version / #extension lines in place so that line
       numbers in compiler messages stay meaningful. */
    inline std::string neutraliseDirectives(const std::string& src)
    {
        static const std::regex directive("^[ \\t]*#(version|extension)\\b");
        std::ostringstream out;
        std::istringstream in(src);
        std::string line;
        bool first = true;
        while (std::getline(in, line))
        {
            if (!first) out << '\n';
            first = false;
            if (std::regex_search(line, directive)) out << "// ";
            out << line;
        }
        return out.str();
    }

    inline std::string convert(const std::string& input, bool vertexStage, const std::vector<Alias>& aliases, bool es3)
    {
        const std::string attrQ = es3 ? "in " : "attribute ";
        /* OSG_GLES_DEBUG_MAGENTA=1: every fragment that survives main() ends up magenta;
           OSG_GLES_DEBUG_TEXEL=1: ... ends up as the first sampler2D looked up at osg_TexCoord[0] */
        const bool debugMagenta = !vertexStage && getenv("OSG_GLES_DEBUG_MAGENTA") != 0;
        const bool debugTexel = !vertexStage && getenv("OSG_GLES_DEBUG_TEXEL") != 0;
        /* OSG_GLES_DEBUG_TEXCOORD=1: ... ends up as vec4(fract(osg_TexCoord[0].st), 0, 1) */
        const bool debugTexCoord = !vertexStage && getenv("OSG_GLES_DEBUG_TEXCOORD") != 0;
        /* OSG_GLES_DEBUG_TEXCOORD_RAW=1: ... as the attribute before any texture matrix;
           OSG_GLES_DEBUG_NOTEXMAT=1: every gl_TextureMatrix[n] becomes the identity */
        const bool debugRaw = getenv("OSG_GLES_DEBUG_TEXCOORD_RAW") != 0;
        const bool debugNoTexMat = getenv("OSG_GLES_DEBUG_NOTEXMAT") != 0;
        const std::string varyQ = es3 ? (vertexStage ? "out " : "in ") : "varying ";
        std::string src = input;
        std::string::size_type p;
        while ((p = src.find("\r\n")) != std::string::npos) src.replace(p, 2, "\n");
        while ((p = src.find('\r')) != std::string::npos) src[p] = '\n';

        std::vector<std::string> decls, ext, tail;

        src = neutraliseDirectives(src);

        /* --- what OSG's own conversion does: matrices, attributes --- */
        replaceWord(src, "ftransform()", "(gl_ModelViewProjectionMatrix * gl_Vertex)");
        static const char* matrices[][3] = {
            { "gl_ModelViewMatrixInverse",   "osg_ModelViewMatrixInverse",   "mat4" },
            { "gl_ModelViewMatrixTranspose", "osg_ModelViewMatrixTranspose", "mat4" },
            { "gl_ModelViewProjectionMatrix", "osg_ModelViewProjectionMatrix", "mat4" },
            { "gl_ModelViewMatrix",          "osg_ModelViewMatrix",          "mat4" },
            { "gl_ProjectionMatrix",         "osg_ProjectionMatrix",         "mat4" },
            { "gl_NormalMatrix",             "osg_NormalMatrix",             "mat3" } };
        for (unsigned i = 0; i < sizeof(matrices) / sizeof(matrices[0]); ++i)
            if (replaceWord(src, matrices[i][0], matrices[i][1]))
                addDecl(decls, std::string("uniform ") + matrices[i][2] + " " + matrices[i][1] + ";");

        bool wroteBack = false;
        if (vertexStage)
        {
            replaceWord(src, "gl_FrontColor", "osg_FrontColor");
            wroteBack = replaceWord(src, "gl_BackColor", "osg_BackColor");
            replaceWord(src, "gl_FrontSecondaryColor", "osg_FrontSecondaryColor");
            replaceWord(src, "gl_BackSecondaryColor", "osg_BackSecondaryColor");
            addDecl(decls, varyQ + "vec4 osg_FrontColor;");
            addDecl(decls, varyQ + "vec4 osg_BackColor;");
            if (contains(src, "osg_FrontSecondaryColor")) addDecl(decls, varyQ + "vec4 osg_FrontSecondaryColor;");
            if (contains(src, "osg_BackSecondaryColor")) addDecl(decls, varyQ + "vec4 osg_BackSecondaryColor;");
            if (replaceWord(src, "gl_FogFragCoord", "osg_FogFragCoord")) addDecl(decls, varyQ + "float osg_FogFragCoord;");
            if (replaceWord(src, "gl_ClipVertex", "osg_ClipVertexDummy")) addDecl(decls, "vec4 osg_ClipVertexDummy;");
            for (std::vector<Alias>::const_iterator a = aliases.begin(); a != aliases.end(); ++a)
                if (replaceWord(src, a->glName, a->osgName))
                    addDecl(decls, attrQ + a->declaration + a->osgName + ";");
        }
        else
        {
            if (replaceWord(src, "gl_Color", "(gl_FrontFacing ? osg_FrontColor : osg_BackColor)"))
            {
                addDecl(decls, varyQ + "vec4 osg_FrontColor;");
                addDecl(decls, varyQ + "vec4 osg_BackColor;");
            }
            if (replaceWord(src, "gl_SecondaryColor", "osg_FrontSecondaryColor")) addDecl(decls, varyQ + "vec4 osg_FrontSecondaryColor;");
            if (replaceWord(src, "gl_FogFragCoord", "osg_FogFragCoord")) addDecl(decls, varyQ + "float osg_FogFragCoord;");
            replaceWord(src, "gl_FragData[0]", "gl_FragColor");
            if (es3)
            {
                /* OSG's own shaders (osgText) already declare osg_FragColor */
                const bool declaredByShader = contains(src, "osg_FragColor");
                const bool usesFragColor = replaceWord(src, "gl_FragColor", "osg_FragColor");
                if ((usesFragColor || debugMagenta || debugTexel || debugTexCoord || debugRaw) && !declaredByShader) addDecl(decls, "out vec4 osg_FragColor;");
            }
            else if (replaceWord(src, "gl_FragDepth", "osg_FragDepthDummy")) addDecl(decls, "float osg_FragDepthDummy;");
        }

        /* --- gl_TexCoord[n]: varying array sized by the largest index --- */
        {
            static const std::regex texCoord("gl_TexCoord\\[(\\d+)\\]");
            int maxIndex = -1;
            for (std::sregex_iterator it(src.begin(), src.end(), texCoord), end; it != end; ++it)
            {
                int idx = atoi((*it)[1].str().c_str());
                if (idx > maxIndex) maxIndex = idx;
            }
            if (maxIndex >= 0)
            {
                while ((p = src.find("gl_TexCoord[")) != std::string::npos) src.replace(p, 12, "osg_TexCoord[");
                std::ostringstream d; d << varyQ << "vec4 osg_TexCoord[" << (maxIndex + 1) << "];";
                addDecl(decls, d.str());
            }
        }

        /* --- fixed-function state structs -> flat uniforms --- */
        static const char* lightMembers[][2] = {
            { "ambient", "vec4" }, { "diffuse", "vec4" }, { "specular", "vec4" }, { "position", "vec4" },
            { "halfVector", "vec4" }, { "spotDirection", "vec3" }, { "spotExponent", "float" },
            { "spotCutoff", "float" }, { "spotCosCutoff", "float" }, { "constantAttenuation", "float" },
            { "linearAttenuation", "float" }, { "quadraticAttenuation", "float" } };
        for (int n = 0; n < 8; ++n)
        {
            std::ostringstream num; num << n;
            for (unsigned i = 0; i < sizeof(lightMembers) / sizeof(lightMembers[0]); ++i)
            {
                std::string osgName = "osg_LightSource" + num.str() + "_" + lightMembers[i][0];
                if (replaceWord(src, "gl_LightSource[" + num.str() + "]." + lightMembers[i][0], osgName))
                    addDecl(decls, std::string("uniform ") + lightMembers[i][1] + " " + osgName + ";");
            }
        }
        static const char* materialMembers[][2] = {
            { "emission", "vec4" }, { "ambient", "vec4" }, { "diffuse", "vec4" }, { "specular", "vec4" }, { "shininess", "float" } };
        static const char* materialPrefixes[] = { "gl_FrontMaterial", "gl_BackMaterial" };
        for (unsigned pfx = 0; pfx < 2; ++pfx)
            for (unsigned i = 0; i < sizeof(materialMembers) / sizeof(materialMembers[0]); ++i)
            {
                std::string osgName = std::string("osg_FrontMaterial_") + materialMembers[i][0];
                if (replaceWord(src, std::string(materialPrefixes[pfx]) + "." + materialMembers[i][0], osgName))
                    addDecl(decls, std::string("uniform ") + materialMembers[i][1] + " " + osgName + ";");
            }
        if (replaceWord(src, "gl_LightModel.ambient", "osg_LightModel_ambient")) addDecl(decls, "uniform vec4 osg_LightModel_ambient;");
        if (replaceWord(src, "gl_FrontLightModelProduct.sceneColor", "osg_FrontLightModelProduct_sceneColor"))
            addDecl(decls, "uniform vec4 osg_FrontLightModelProduct_sceneColor;");
        static const char* fogMembers[][2] = { { "color", "vec4" }, { "density", "float" }, { "start", "float" }, { "end", "float" }, { "scale", "float" } };
        for (unsigned i = 0; i < sizeof(fogMembers) / sizeof(fogMembers[0]); ++i)
        {
            std::string osgName = std::string("osg_Fog_") + fogMembers[i][0];
            if (replaceWord(src, std::string("gl_Fog.") + fogMembers[i][0], osgName))
                addDecl(decls, std::string("uniform ") + fogMembers[i][1] + " " + osgName + ";");
        }
        for (int n = 0; n < 8; ++n)
        {
            std::ostringstream num; num << n;
            if (debugNoTexMat) replaceWord(src, "gl_TextureMatrix[" + num.str() + "]", "mat4(1.0)");
            else if (replaceWord(src, "gl_TextureMatrix[" + num.str() + "]", "osg_TextureMatrix" + num.str()))
                addDecl(decls, "uniform mat4 osg_TextureMatrix" + num.str() + ";");
        }

        /* No 1D textures in GLSL ES.  sampler1D becomes sampler2D, and
           texture1D(s, x) becomes texture2D(s, vec2(x, 0.5)); Texture1D::apply
           uploads the image as a 2D texture of height 1 to match. */
        {
            static const std::regex s1d("\\bsampler1D\\b");
            src = std::regex_replace(src, s1d, "sampler2D");
            std::string::size_type pos = 0;
            while ((pos = src.find("texture1D", pos)) != std::string::npos)
            {
                std::string::size_type open = src.find('(', pos);
                if (open == std::string::npos) break;
                int depth = 0; std::string::size_type comma = std::string::npos, close = std::string::npos;
                for (std::string::size_type i = open; i < src.size(); ++i)
                {
                    if (src[i] == '(') ++depth;
                    else if (src[i] == ')') { if (--depth == 0) { close = i; break; } }
                    else if (src[i] == ',' && depth == 1 && comma == std::string::npos) comma = i;
                }
                if (close == std::string::npos || comma == std::string::npos) { pos += 9; continue; }
                std::string sampler = src.substr(open + 1, comma - open - 1);
                std::string coord   = src.substr(comma + 1, close - comma - 1);
                std::string repl = "texture2D(" + sampler + ", vec2(" + coord + ", 0.5))";
                src.replace(pos, close - pos + 1, repl);
                pos += repl.size();
            }
            /* "const float X = SOME_INT_MACRO;" is not a constant expression of
               type float in GLSL ES; a float() constructor around it is. */
            static const std::regex constFloat("(\\bconst\\s+float\\s+[A-Za-z_][A-Za-z0-9_]*\\s*=\\s*)([A-Za-z_][A-Za-z0-9_]*)\\s*;");
            src = std::regex_replace(src, constFloat, "$1float($2);");
        }

        if (es3)
        {
            /* GLSL ES 3.00 reserves some names FlightGear uses as identifiers
               (above all "uniform sampler2D texture").  Rename them; the
               program keeps the original uniform name reachable (Program.cpp). */
            static const char* reserved[] = { "texture", "filter", "input", "output", "sample" };
            for (unsigned i = 0; i < sizeof(reserved) / sizeof(reserved[0]); ++i)
            {
                /* only when the shader declares a variable of that name; a bare
                   "texture" elsewhere (e.g. "#define TEXTURE texture") is the function */
                std::regex declared(std::string("\\b(?:float|int|bool|vec[234]|ivec[234]|mat[234]|sampler[A-Za-z0-9]*)\\s+") + reserved[i] + "\\b");
                if (!std::regex_search(src, declared)) continue;
                std::regex ident(std::string("\\b") + reserved[i] + "\\b(?!\\s*\\()");
                src = std::regex_replace(src, ident, std::string("osg_ru_") + reserved[i]);
            }
            /* GLSL ES 3.00: attribute/varying became in/out, texture2D() became texture() */
            static const std::regex attrDecl("\\battribute\\b");
            static const std::regex varyDecl("\\bvarying\\b");
            src = std::regex_replace(src, attrDecl, "in");
            src = std::regex_replace(src, varyDecl, vertexStage ? "out" : "in");
            static const char* texFuncs[][2] = {
                { "texture2DProjLod", "textureProjLod" }, { "texture2DLod", "textureLod" }, { "texture2DProj", "textureProj" },
                { "texture3DLod", "textureLod" }, { "textureCubeLod", "textureLod" }, { "shadow2DProj", "textureProj" },
                { "texture2D", "texture" }, { "texture3D", "texture" }, { "textureCube", "texture" }, { "shadow2D", "texture" } };
            for (unsigned i = 0; i < sizeof(texFuncs) / sizeof(texFuncs[0]); ++i) replaceWord(src, texFuncs[i][0], texFuncs[i][1]);
        }

        /* --- spellings ES 1.00 lacks --- */
        replaceWord(src, "mat2x2", "mat2");
        replaceWord(src, "mat3x3", "mat3");
        replaceWord(src, "mat4x4", "mat4");

        /* --- integer literals where ES 1.00 wants floats --- */
        {
            static const std::regex floatDeclInit("\\bfloat\\s+([A-Za-z_][A-Za-z0-9_]*)\\s*=\\s*(\\d+)\\s*;");
            src = std::regex_replace(src, floatDeclInit, "float $1 = $2.0;");
            static const std::regex swizzleCompare("(\\.[rgbaxyzwst]{1,4})\\s*(>=|<=|==|!=|>|<)\\s*(\\d+)\\b(?![.\\w])");
            src = std::regex_replace(src, swizzleCompare, "$1 $2 $3.0");
            static const std::regex floatDecls("\\bfloat\\s+([A-Za-z_][A-Za-z0-9_]*(?:\\s*,\\s*[A-Za-z_][A-Za-z0-9_]*)*)");
            std::set<std::string> names;
            for (std::sregex_iterator it(src.begin(), src.end(), floatDecls), end; it != end; ++it)
            {
                std::string list = (*it)[1].str();
                std::string::size_type start = 0;
                while (start <= list.size())
                {
                    std::string::size_type comma = list.find(',', start);
                    std::string name = list.substr(start, comma == std::string::npos ? std::string::npos : comma - start);
                    std::string::size_type a = name.find_first_not_of(" \t"), b = name.find_last_not_of(" \t");
                    if (a != std::string::npos) names.insert(name.substr(a, b - a + 1));
                    if (comma == std::string::npos) break;
                    start = comma + 1;
                }
            }
            for (std::set<std::string>::const_iterator n = names.begin(); n != names.end(); ++n)
            {
                std::regex cmp("\\b(" + *n + ")\\s*(>=|<=|==|!=|>|<)\\s*(\\d+)\\b(?![.\\w])");
                src = std::regex_replace(src, cmp, "$1 $2 $3.0");
                std::regex assign("\\b(" + *n + ")\\s*=\\s*(\\d+)\\s*;");
                src = std::regex_replace(src, assign, "$1 = $2.0;");
            }
        }

        /* --- extensions ES has to be told about --- */
        if (contains(src, "sampler3D"))
        {
            if (!es3) ext.push_back("#extension GL_OES_texture_3D : enable");
            decls.insert(decls.begin(), "precision mediump sampler3D;");
        }
        if (!vertexStage && !es3)
        {
            static const std::regex lod("\\btexture2D(Proj)?Lod\\b");
            if (std::regex_search(src, lod))
            {
                src = std::regex_replace(src, lod, "texture2D$1LodEXT");
                ext.push_back("#extension GL_EXT_shader_texture_lod : enable");
            }
        }

        /* --- main() wrapper: colour defaults and hoisted initialisers --- */
        std::vector<std::string> hoisted;
        src = hoistGlobalInitialisers(src, hoisted);
        std::string debugSampler;
        if (debugTexel && contains(src, "osg_TexCoord["))
        {
            static const std::regex sampler2D("uniform\\s+(?:lowp\\s+|mediump\\s+|highp\\s+)?sampler2D\\s+([A-Za-z_][A-Za-z0-9_]*)");
            std::smatch m;
            if (std::regex_search(src, m, sampler2D)) debugSampler = m[1].str();
        }
        const bool debugCoords = debugTexCoord && contains(src, "osg_TexCoord[");
        std::string rawAttr;
        if (debugRaw)
        {
            for (std::vector<Alias>::const_iterator a = aliases.begin(); a != aliases.end(); ++a)
                if (a->glName == "gl_MultiTexCoord0") rawAttr = a->osgName;
            if (vertexStage && !contains(src, rawAttr)) rawAttr.clear();
            if (!rawAttr.empty()) addDecl(decls, varyQ + "vec2 osg_dbgRawTexCoord;");
            if (vertexStage && !rawAttr.empty()) addDecl(decls, attrQ + "vec4 " + rawAttr + ";");
        }
        if (vertexStage || !hoisted.empty() || debugMagenta || !debugSampler.empty() || debugCoords || !rawAttr.empty())
        {
            static const std::regex mainDecl("\\bvoid\\s+main\\s*\\(\\s*(void)?\\s*\\)");
            if (std::regex_search(src, mainDecl))
            {
                src = std::regex_replace(src, mainDecl, "void osg_ffp_main()");
                std::ostringstream w;
                w << "void main() {\n";
                if (vertexStage) w << "    osg_FrontColor = vec4(1.0);\n    osg_BackColor = vec4(1.0);\n";
                for (std::vector<std::string>::const_iterator h = hoisted.begin(); h != hoisted.end(); ++h) w << "    " << *h << '\n';
                w << "    osg_ffp_main();\n";
                if (vertexStage && !wroteBack) w << "    osg_BackColor = osg_FrontColor;\n";
                if (debugMagenta) w << "    " << (es3 ? "osg_FragColor" : "gl_FragColor") << " = vec4(1.0, 0.0, 1.0, 1.0);\n";
                if (!debugSampler.empty()) w << "    " << (es3 ? "osg_FragColor = texture(" : "gl_FragColor = texture2D(")
                                              << debugSampler << ", osg_TexCoord[0].st);\n";
                if (debugCoords) w << "    " << (es3 ? "osg_FragColor" : "gl_FragColor") << " = vec4(fract(osg_TexCoord[0].st), 0.0, 1.0);\n";
                if (!rawAttr.empty() && vertexStage) w << "    osg_dbgRawTexCoord = " << rawAttr << ".st;\n";
                if (!rawAttr.empty() && !vertexStage) w << "    " << (es3 ? "osg_FragColor" : "gl_FragColor") << " = vec4(fract(osg_dbgRawTexCoord), 0.0, 1.0);\n";
                w << "}";
                tail.push_back(w.str());
            }
        }

        /* --- assemble --- */
        std::ostringstream out;
        out << (es3 ? "#version 300 es\n" : "#version 100\n");
        for (std::vector<std::string>::const_iterator e = ext.begin(); e != ext.end(); ++e) out << *e << '\n';
        if (vertexStage) out << "precision highp float;\n";
        else out << "#ifdef GL_FRAGMENT_PRECISION_HIGH\nprecision highp float;\n#else\nprecision mediump float;\n#endif\n";
        out << "precision highp int;\n";
        for (std::vector<std::string>::const_iterator d = decls.begin(); d != decls.end(); ++d) out << *d << '\n';
        out << src;
        for (std::vector<std::string>::const_iterator t = tail.begin(); t != tail.end(); ++t) out << '\n' << *t << '\n';
        return out.str();
    }
}

namespace
{
    template<class T> void ffpSet(Uniform* u, const T& value, bool& dirty)
    {
        T current;
        if (u->get(current) && current == value) return;
        u->set(value);
        dirty = true;
    }
}

Uniform* State::ffpUniform(const std::string& name, Uniform::Type type)
{
    FFPUniformMap::iterator it = _ffpUniforms.find(name);
    if (it != _ffpUniforms.end()) return it->second.get();
    Uniform* u = new Uniform(type, name);
    _ffpUniforms[name] = u;
    _ffpDirty = true;
    return u;
}

void State::initFFPUniforms()
{
    /* OpenGL fixed-function defaults */
    _ffpMaterialEmission.set(0.0f, 0.0f, 0.0f, 1.0f);
    _ffpMaterialAmbient.set(0.2f, 0.2f, 0.2f, 1.0f);
    _ffpMaterialDiffuse.set(0.8f, 0.8f, 0.8f, 1.0f);
    _ffpLightModelAmbient.set(0.2f, 0.2f, 0.2f, 1.0f);
    setFFPLight(0, Vec4(0.0f, 0.0f, 0.0f, 1.0f), Vec4(1.0f, 1.0f, 1.0f, 1.0f), Vec4(1.0f, 1.0f, 1.0f, 1.0f),
                Vec4(0.0f, 0.0f, 1.0f, 0.0f), Vec3(0.0f, 0.0f, -1.0f), 0.0f, 180.0f, 1.0f, 0.0f, 0.0f);
    setFFPMaterial(_ffpMaterialEmission, _ffpMaterialAmbient, _ffpMaterialDiffuse, Vec4(0.0f, 0.0f, 0.0f, 1.0f), 0.0f);
    setFFPLightModelAmbient(_ffpLightModelAmbient);
    setFFPFog(0x0800 /* GL_EXP */, Vec4(0.0f, 0.0f, 0.0f, 0.0f), 1.0f, 0.0f, 1.0f);
    for (unsigned int unit = 0; unit < 2; ++unit) setFFPTextureMatrix(unit, Matrix::identity());
}

void State::setFFPLight(unsigned int num, const Vec4& ambient, const Vec4& diffuse, const Vec4& specular,
                        const Vec4& eyePosition, const Vec3& eyeSpotDirection, float spotExponent, float spotCutoff,
                        float constantAttenuation, float linearAttenuation, float quadraticAttenuation)
{
    if (num >= 8) return;
    std::ostringstream p; p << "osg_LightSource" << num << "_";
    const std::string pfx = p.str();
    ffpSet(ffpUniform(pfx + "ambient", Uniform::FLOAT_VEC4), ambient, _ffpDirty);
    ffpSet(ffpUniform(pfx + "diffuse", Uniform::FLOAT_VEC4), diffuse, _ffpDirty);
    ffpSet(ffpUniform(pfx + "specular", Uniform::FLOAT_VEC4), specular, _ffpDirty);
    ffpSet(ffpUniform(pfx + "position", Uniform::FLOAT_VEC4), eyePosition, _ffpDirty);
    /* half vector for an infinite light and an infinite viewer, as GL does */
    Vec3 dir(eyePosition.x(), eyePosition.y(), eyePosition.z());
    if (dir.length2() > 0.0f) dir.normalize();
    Vec3 half = dir + Vec3(0.0f, 0.0f, 1.0f);
    if (half.length2() > 0.0f) half.normalize();
    ffpSet(ffpUniform(pfx + "halfVector", Uniform::FLOAT_VEC4), Vec4(half, 0.0f), _ffpDirty);
    ffpSet(ffpUniform(pfx + "spotDirection", Uniform::FLOAT_VEC3), eyeSpotDirection, _ffpDirty);
    ffpSet(ffpUniform(pfx + "spotExponent", Uniform::FLOAT), spotExponent, _ffpDirty);
    ffpSet(ffpUniform(pfx + "spotCutoff", Uniform::FLOAT), spotCutoff, _ffpDirty);
    ffpSet(ffpUniform(pfx + "spotCosCutoff", Uniform::FLOAT), float(cos(DegreesToRadians(double(spotCutoff)))), _ffpDirty);
    ffpSet(ffpUniform(pfx + "constantAttenuation", Uniform::FLOAT), constantAttenuation, _ffpDirty);
    ffpSet(ffpUniform(pfx + "linearAttenuation", Uniform::FLOAT), linearAttenuation, _ffpDirty);
    ffpSet(ffpUniform(pfx + "quadraticAttenuation", Uniform::FLOAT), quadraticAttenuation, _ffpDirty);
}

void State::updateFFPSceneColor()
{
    /* gl_FrontLightModelProduct.sceneColor = emission + ambient * lightmodel.ambient */
    Vec4 scene = _ffpMaterialEmission + componentMultiply(_ffpMaterialAmbient, _ffpLightModelAmbient);
    scene.w() = _ffpMaterialDiffuse.w();
    ffpSet(ffpUniform("osg_FrontLightModelProduct_sceneColor", Uniform::FLOAT_VEC4), scene, _ffpDirty);
}

void State::setFFPMaterial(const Vec4& emission, const Vec4& ambient, const Vec4& diffuse, const Vec4& specular, float shininess)
{
    _ffpMaterialEmission = emission;
    _ffpMaterialAmbient = ambient;
    _ffpMaterialDiffuse = diffuse;
    ffpSet(ffpUniform("osg_FrontMaterial_emission", Uniform::FLOAT_VEC4), emission, _ffpDirty);
    ffpSet(ffpUniform("osg_FrontMaterial_ambient", Uniform::FLOAT_VEC4), ambient, _ffpDirty);
    ffpSet(ffpUniform("osg_FrontMaterial_diffuse", Uniform::FLOAT_VEC4), diffuse, _ffpDirty);
    ffpSet(ffpUniform("osg_FrontMaterial_specular", Uniform::FLOAT_VEC4), specular, _ffpDirty);
    ffpSet(ffpUniform("osg_FrontMaterial_shininess", Uniform::FLOAT), shininess, _ffpDirty);
    updateFFPSceneColor();
}

void State::setFFPLightModelAmbient(const Vec4& ambient)
{
    _ffpLightModelAmbient = ambient;
    ffpSet(ffpUniform("osg_LightModel_ambient", Uniform::FLOAT_VEC4), ambient, _ffpDirty);
    updateFFPSceneColor();
}

void State::setFFPFog(int mode, const Vec4& color, float density, float start, float end)
{
    (void)mode;   /* FlightGear's shaders compute EXP2 themselves */
    ffpSet(ffpUniform("osg_Fog_color", Uniform::FLOAT_VEC4), color, _ffpDirty);
    /* OSG_GLES_DEBUG_NOFOG=1: switch the fog term off in every shader */
    static const bool noFog = getenv("OSG_GLES_DEBUG_NOFOG") != 0;
    ffpSet(ffpUniform("osg_Fog_density", Uniform::FLOAT), noFog ? 0.0f : density, _ffpDirty);
    ffpSet(ffpUniform("osg_Fog_start", Uniform::FLOAT), start, _ffpDirty);
    ffpSet(ffpUniform("osg_Fog_end", Uniform::FLOAT), end, _ffpDirty);
    ffpSet(ffpUniform("osg_Fog_scale", Uniform::FLOAT), (end != start) ? 1.0f / (end - start) : 1.0f, _ffpDirty);
}

void State::setFFPTextureMatrix(unsigned int unit, const Matrix& matrix)
{
    if (unit >= 8) return;
    std::ostringstream n; n << "osg_TextureMatrix" << unit;
    ffpSet(ffpUniform(n.str(), Uniform::FLOAT_MAT4), matrix, _ffpDirty);
}

bool State::convertShaderSourceForGLES(Shader::Type type, std::string& source) const
{
    if (type != Shader::VERTEX && type != Shader::FRAGMENT) return false;
    State_Utils::substitudeEnvVars(*this, source);
    std::vector<osg_gles::Alias> aliases;
    const VertexAttribAlias* fixed[] = { &_vertexAlias, &_normalAlias, &_colorAlias, &_secondaryColorAlias, &_fogCoordAlias };
    for (unsigned int i = 0; i < sizeof(fixed) / sizeof(fixed[0]); ++i)
    {
        osg_gles::Alias a;
        a.glName = fixed[i]->_glName; a.osgName = fixed[i]->_osgName; a.declaration = fixed[i]->_declaration;
        aliases.push_back(a);
    }
    for (size_t i = 0; i < _texCoordAliasList.size(); ++i)
    {
        osg_gles::Alias a;
        a.glName = _texCoordAliasList[i]._glName; a.osgName = _texCoordAliasList[i]._osgName; a.declaration = _texCoordAliasList[i]._declaration;
        aliases.push_back(a);
    }
    /* the Mali driver hands out an ES 3.2 context even when 2.0 was asked for;
       GLSL ES 3.00 has 3D textures, textureLod() and in/out without extensions */
    const GLExtensions* ext = GLExtensions::Get(getContextID(), false);
    const bool es3 = ext && ext->glVersion >= 3.0f;
    source = osg_gles::convert(source, type == Shader::VERTEX, aliases, es3);
    return true;
}

#endif
#if !defined(OSG_GL_FIXED_FUNCTION_AVAILABLE)
/* FlightGear GLES port: nothing draws without a program under GLES, and
   FlightGear's sky dome, HUD and 2D panel have none.  Bind a built-in one
   when the state set left none bound - vertex colour, times the texture on
   unit 0 if there is one.  That is what the fixed-function pipeline does
   for such geometry with lighting off. */
void State::applyFallbackProgramIfNeeded()
{
    if (_lastAppliedProgramObject) return;
    static const int off = (::getenv("FGFS_GLES_NO_FALLBACK") != 0) ? 1 : 0;
    if (off) return;

    const bool textured = getLastAppliedTextureAttribute(0, StateAttribute::TEXTURE) != 0;
    ref_ptr<Program>& prog = _fallbackProgram[textured ? 1 : 0];
    if (!prog)
    {
        /* GLSL ES 1.00, which the converter leaves alone; State supplies
           osg_ModelViewProjectionMatrix, the attribute aliases and
           osg_TextureMatrix0. */
        const char* vs =
            "attribute vec4 osg_Vertex;\n"
            "attribute vec4 osg_Color;\n"
            "attribute vec4 osg_MultiTexCoord0;\n"
            "uniform mat4 osg_ModelViewProjectionMatrix;\n"
            "uniform mat4 osg_TextureMatrix0;\n"
            "varying vec4 fgfs_color;\n"
            "varying vec2 fgfs_tc;\n"
            "void main() {\n"
            "  gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;\n"
            "  fgfs_color = osg_Color;\n"
            "  fgfs_tc = (osg_TextureMatrix0 * osg_MultiTexCoord0).st;\n"
            "}\n";
        const char* fsPlain =
            "precision mediump float;\n"
            "varying vec4 fgfs_color;\n"
            "varying vec2 fgfs_tc;\n"
            "void main() { gl_FragColor = fgfs_color; }\n";
        const char* fsTex =
            "precision mediump float;\n"
            "uniform sampler2D fgfs_tex;\n"
            "varying vec4 fgfs_color;\n"
            "varying vec2 fgfs_tc;\n"
            "void main() { gl_FragColor = fgfs_color * texture2D(fgfs_tex, fgfs_tc); }\n";
        prog = new Program;
        prog->setName(textured ? "fgfs_fallback_textured" : "fgfs_fallback_plain");
        prog->addShader(new Shader(Shader::VERTEX, vs));
        prog->addShader(new Shader(Shader::FRAGMENT, textured ? fsTex : fsPlain));
        if (!_fallbackSampler) _fallbackSampler = new Uniform("fgfs_tex", 0);
        OSG_WARN << "State: fallback program (" << prog->getName()
                 << ") for geometry without a shader" << std::endl;
    }
    prog->apply(*this);
    if (textured && _lastAppliedProgramObject) _lastAppliedProgramObject->apply(*_fallbackSampler);
    /* the fixed-function uniforms (texture matrix etc.) need a fresh upload
       for this program */
    _ffpDirty = true;
}
#endif

bool State::convertVertexShaderSourceToOsgBuiltIns(std::string& source) const
{
    OSG_DEBUG<<"State::convertShaderSourceToOsgBuiltIns()"<<std::endl;

    OSG_DEBUG<<"++Before Converted source "<<std::endl<<source<<std::endl<<"++++++++"<<std::endl;


    State_Utils::substitudeEnvVars(*this, source);


    std::string attributeQualifier("attribute ");

    // find the first legal insertion point for replacement declarations. GLSL requires that nothing
    // precede a "#version" compiler directive, so we must insert new declarations after it.
    std::string::size_type declPos = source.rfind( "#version " );
    if ( declPos != std::string::npos )
    {
        declPos = source.find(" ", declPos); // move to the first space after "#version"
        declPos = source.find_first_not_of(std::string(" "), declPos); // skip all the spaces until you reach the version number
        std::string versionNumber(source, declPos, 3);
        int glslVersion = atoi(versionNumber.c_str());
        OSG_INFO<<"shader version found: "<< glslVersion <<std::endl;
        if (glslVersion >= 130) attributeQualifier = "in ";
        // found the string, now find the next linefeed and set the insertion point after it.
        declPos = source.find( '\n', declPos );
        declPos = declPos != std::string::npos ? declPos+1 : source.length();
    }
    else
    {
        declPos = 0;
    }

    std::string::size_type extPos = source.rfind( "#extension " );
    if ( extPos != std::string::npos )
    {
        // found the string, now find the next linefeed and set the insertion point after it.
        declPos = source.find( '\n', extPos );
        declPos = declPos != std::string::npos ? declPos+1 : source.length();
    }
    if (_useModelViewAndProjectionUniforms)
    {
        // replace ftransform as it only works with built-ins
        State_Utils::replace(source, "ftransform()", "gl_ModelViewProjectionMatrix * gl_Vertex");

        // replace built in uniform
        State_Utils::replaceAndInsertDeclaration(source, declPos, "gl_ModelViewMatrix", "osg_ModelViewMatrix", "uniform ", "mat4 ");
        State_Utils::replaceAndInsertDeclaration(source, declPos, "gl_ModelViewProjectionMatrix", "osg_ModelViewProjectionMatrix", "uniform ", "mat4 ");
        State_Utils::replaceAndInsertDeclaration(source, declPos, "gl_ProjectionMatrix", "osg_ProjectionMatrix", "uniform ", "mat4 ");
        State_Utils::replaceAndInsertDeclaration(source, declPos, "gl_NormalMatrix", "osg_NormalMatrix", "uniform ", "mat3 ");
    }

    if (_useVertexAttributeAliasing)
    {
        State_Utils::replaceAndInsertDeclaration(source, declPos, _vertexAlias._glName,         _vertexAlias._osgName,         attributeQualifier, _vertexAlias._declaration);
        State_Utils::replaceAndInsertDeclaration(source, declPos, _normalAlias._glName,         _normalAlias._osgName,         attributeQualifier, _normalAlias._declaration);
        State_Utils::replaceAndInsertDeclaration(source, declPos, _colorAlias._glName,          _colorAlias._osgName,          attributeQualifier, _colorAlias._declaration);
        State_Utils::replaceAndInsertDeclaration(source, declPos, _secondaryColorAlias._glName, _secondaryColorAlias._osgName, attributeQualifier, _secondaryColorAlias._declaration);
        State_Utils::replaceAndInsertDeclaration(source, declPos, _fogCoordAlias._glName,       _fogCoordAlias._osgName,       attributeQualifier, _fogCoordAlias._declaration);
        for (size_t i=0; i<_texCoordAliasList.size(); i++)
        {
            const VertexAttribAlias& texCoordAlias = _texCoordAliasList[i];
            State_Utils::replaceAndInsertDeclaration(source, declPos, texCoordAlias._glName, texCoordAlias._osgName, attributeQualifier, texCoordAlias._declaration);
        }
    }

    OSG_DEBUG<<"-------- Converted source "<<std::endl<<source<<std::endl<<"----------------"<<std::endl;

    return true;
}

void State::setUpVertexAttribAlias(VertexAttribAlias& alias, GLuint location, const std::string glName, const std::string osgName, const std::string& declaration)
{
    alias = VertexAttribAlias(location, glName, osgName, declaration);
    _attributeBindingList[osgName] = location;
    // OSG_NOTICE<<"State::setUpVertexAttribAlias("<<location<<" "<<glName<<" "<<osgName<<")"<<std::endl;
}

void State::applyProjectionMatrix(const osg::RefMatrix* matrix)
{
    if (_projection!=matrix)
    {
        if (matrix)
        {
            _projection=matrix;
        }
        else
        {
            _projection=_identity;
        }

        if (_useModelViewAndProjectionUniforms)
        {
            if (_projectionMatrixUniform.valid()) _projectionMatrixUniform->set(*_projection);
            updateModelViewAndProjectionMatrixUniforms();
        }
#ifdef OSG_GL_MATRICES_AVAILABLE
        glMatrixMode( GL_PROJECTION );
            glLoadMatrix(_projection->ptr());
        glMatrixMode( GL_MODELVIEW );
#endif
    }
}

void State::loadModelViewMatrix()
{
    if (_useModelViewAndProjectionUniforms)
    {
        if (_modelViewMatrixUniform.valid()) _modelViewMatrixUniform->set(*_modelView);
        updateModelViewAndProjectionMatrixUniforms();
    }

#ifdef OSG_GL_MATRICES_AVAILABLE
    glLoadMatrix(_modelView->ptr());
#endif
}

void State::applyModelViewMatrix(const osg::RefMatrix* matrix)
{
    if (_modelView!=matrix)
    {
        if (matrix)
        {
            _modelView=matrix;
        }
        else
        {
            _modelView=_identity;
        }

        loadModelViewMatrix();
    }
}

void State::applyModelViewMatrix(const osg::Matrix& matrix)
{
    _modelViewCache->set(matrix);
    _modelView = _modelViewCache;

    loadModelViewMatrix();
}

#include <osg/io_utils>

void State::updateModelViewAndProjectionMatrixUniforms()
{
    if (_modelViewProjectionMatrixUniform.valid()) _modelViewProjectionMatrixUniform->set((*_modelView) * (*_projection));
    if (_normalMatrixUniform.valid())
    {
        Matrix mv(*_modelView);
        mv.setTrans(0.0, 0.0, 0.0);

        Matrix matrix;
        matrix.invert(mv);

        Matrix3 normalMatrix(matrix(0,0), matrix(1,0), matrix(2,0),
                             matrix(0,1), matrix(1,1), matrix(2,1),
                             matrix(0,2), matrix(1,2), matrix(2,2));

        _normalMatrixUniform->set(normalMatrix);
    }
}

void State::drawQuads(GLint first, GLsizei count, GLsizei primCount)
{
    // OSG_NOTICE<<"State::drawQuads("<<first<<", "<<count<<")"<<std::endl;

    unsigned int array = first % 4;
    unsigned int offsetFirst = ((first-array) / 4) * 6;
    unsigned int numQuads = (count/4);
    unsigned int numIndices = numQuads * 6;
    unsigned int endOfIndices = offsetFirst+numIndices;

    if (endOfIndices<65536)
    {
        IndicesGLushort& indices = _quadIndicesGLushort[array];

        if (endOfIndices >= indices.size())
        {
            // we need to expand the _indexArray to be big enough to cope with all the quads required.
            unsigned int numExistingQuads = indices.size()/6;
            unsigned int numRequiredQuads = endOfIndices/6;
            indices.reserve(endOfIndices);
            for(unsigned int i=numExistingQuads; i<numRequiredQuads; ++i)
            {
                unsigned int base = i*4 + array;
                indices.push_back(base);
                indices.push_back(base+1);
                indices.push_back(base+3);

                indices.push_back(base+1);
                indices.push_back(base+2);
                indices.push_back(base+3);

                // OSG_NOTICE<<"   adding quad indices ("<<base<<")"<<std::endl;
            }
        }

        // if (array!=0) return;

        // OSG_NOTICE<<"  glDrawElements(GL_TRIANGLES, "<<numIndices<<", GL_UNSIGNED_SHORT, "<<&(indices[base])<<")"<<std::endl;
        glDrawElementsInstanced(GL_TRIANGLES, numIndices, GL_UNSIGNED_SHORT, &(indices[offsetFirst]), primCount);
    }
    else
    {
        IndicesGLuint& indices = _quadIndicesGLuint[array];

        if (endOfIndices >= indices.size())
        {
            // we need to expand the _indexArray to be big enough to cope with all the quads required.
            unsigned int numExistingQuads = indices.size()/6;
            unsigned int numRequiredQuads = endOfIndices/6;
            indices.reserve(endOfIndices);
            for(unsigned int i=numExistingQuads; i<numRequiredQuads; ++i)
            {
                unsigned int base = i*4 + array;
                indices.push_back(base);
                indices.push_back(base+1);
                indices.push_back(base+3);

                indices.push_back(base+1);
                indices.push_back(base+2);
                indices.push_back(base+3);

                // OSG_NOTICE<<"   adding quad indices ("<<base<<")"<<std::endl;
            }
        }

        // if (array!=0) return;

        // OSG_NOTICE<<"  glDrawElements(GL_TRIANGLES, "<<numIndices<<", GL_UNSIGNED_SHORT, "<<&(indices[base])<<")"<<std::endl;
        glDrawElementsInstanced(GL_TRIANGLES, numIndices, GL_UNSIGNED_INT, &(indices[offsetFirst]), primCount);
    }
}

void State::ModeStack::print(std::ostream& fout) const
{
    fout<<"    valid = "<<valid<<std::endl;
    fout<<"    changed = "<<changed<<std::endl;
    fout<<"    last_applied_value = "<<last_applied_value<<std::endl;
    fout<<"    global_default_value = "<<global_default_value<<std::endl;
    fout<<"    valueVec { "<<std::endl;
    for(ModeStack::ValueVec::const_iterator itr = valueVec.begin();
        itr != valueVec.end();
        ++itr)
    {
        if (itr!=valueVec.begin()) fout<<", ";
        fout<<*itr;
    }
    fout<<" }"<<std::endl;
}

void State::AttributeStack::print(std::ostream& fout) const
{
    fout<<"    changed = "<<changed<<std::endl;
    fout<<"    last_applied_attribute = "<<last_applied_attribute;
    if (last_applied_attribute) fout<<", "<<last_applied_attribute->className()<<", "<<last_applied_attribute->getName()<<std::endl;
    fout<<"    last_applied_shadercomponent = "<<last_applied_shadercomponent<<std::endl;
    if (last_applied_shadercomponent)  fout<<", "<<last_applied_shadercomponent->className()<<", "<<last_applied_shadercomponent->getName()<<std::endl;
    fout<<"    global_default_attribute = "<<global_default_attribute.get()<<std::endl;
    fout<<"    attributeVec { ";
    for(AttributeVec::const_iterator itr = attributeVec.begin();
        itr != attributeVec.end();
        ++itr)
    {
        if (itr!=attributeVec.begin()) fout<<", ";
        fout<<"("<<itr->first<<", "<<itr->second<<")";
    }
    fout<<" }"<<std::endl;
}


void State::UniformStack::print(std::ostream& fout) const
{
    fout<<"    UniformVec { ";
    for(UniformVec::const_iterator itr = uniformVec.begin();
        itr != uniformVec.end();
        ++itr)
    {
        if (itr!=uniformVec.begin()) fout<<", ";
        fout<<"("<<itr->first<<", "<<itr->second<<")";
    }
    fout<<" }"<<std::endl;
}





void State::print(std::ostream& fout) const
{
#if 0
        GraphicsContext*            _graphicsContext;
        unsigned int                _contextID;
        bool                            _shaderCompositionEnabled;
        bool                            _shaderCompositionDirty;
        osg::ref_ptr<ShaderComposer>    _shaderComposer;
#endif

#if 0
        osg::Program*                   _currentShaderCompositionProgram;
        StateSet::UniformList           _currentShaderCompositionUniformList;
#endif

#if 0
        ref_ptr<FrameStamp>         _frameStamp;

        ref_ptr<const RefMatrix>    _identity;
        ref_ptr<const RefMatrix>    _initialViewMatrix;
        ref_ptr<const RefMatrix>    _projection;
        ref_ptr<const RefMatrix>    _modelView;
        ref_ptr<RefMatrix>          _modelViewCache;

        bool                        _useModelViewAndProjectionUniforms;
        ref_ptr<Uniform>            _modelViewMatrixUniform;
        ref_ptr<Uniform>            _projectionMatrixUniform;
        ref_ptr<Uniform>            _modelViewProjectionMatrixUniform;
        ref_ptr<Uniform>            _normalMatrixUniform;

        Matrix                      _initialInverseViewMatrix;

        ref_ptr<DisplaySettings>    _displaySettings;

        bool*                       _abortRenderingPtr;
        CheckForGLErrors            _checkGLErrors;


        bool                        _useVertexAttributeAliasing;
        VertexAttribAlias           _vertexAlias;
        VertexAttribAlias           _normalAlias;
        VertexAttribAlias           _colorAlias;
        VertexAttribAlias           _secondaryColorAlias;
        VertexAttribAlias           _fogCoordAlias;
        VertexAttribAliasList       _texCoordAliasList;

        Program::AttribBindingList  _attributeBindingList;
#endif
        fout<<"ModeMap _modeMap {"<<std::endl;
        for(ModeMap::const_iterator itr = _modeMap.begin();
            itr != _modeMap.end();
            ++itr)
        {
            fout<<"  GLMode="<<itr->first<<", ModeStack {"<<std::endl;
            itr->second.print(fout);
            fout<<"  }"<<std::endl;
        }
        fout<<"}"<<std::endl;

        fout<<"AttributeMap _attributeMap {"<<std::endl;
        for(AttributeMap::const_iterator itr = _attributeMap.begin();
            itr != _attributeMap.end();
            ++itr)
        {
            fout<<"  TypeMemberPaid=("<<itr->first.first<<", "<<itr->first.second<<") AttributeStack {"<<std::endl;
            itr->second.print(fout);
            fout<<"  }"<<std::endl;
        }
        fout<<"}"<<std::endl;

        fout<<"UniformMap _uniformMap {"<<std::endl;
        for(UniformMap::const_iterator itr = _uniformMap.begin();
            itr != _uniformMap.end();
            ++itr)
        {
            fout<<"  name="<<itr->first<<", UniformStack {"<<std::endl;
            itr->second.print(fout);
            fout<<"  }"<<std::endl;
        }
        fout<<"}"<<std::endl;


        fout<<"StateSetStack _stateSetStack {"<<std::endl;
        for(StateSetStack::const_iterator itr = _stateStateStack.begin();
            itr != _stateStateStack.end();
            ++itr)
        {
            fout<<(*itr)->getName()<<"  "<<*itr<<std::endl;
        }
        fout<<"}"<<std::endl;
}

void State::frameCompleted()
{
    if (getTimestampBits())
    {
        GLint64 timestamp;
        _glExtensions->glGetInteger64v(GL_TIMESTAMP, &timestamp);
        setGpuTimestamp(osg::Timer::instance()->tick(), timestamp);
        //OSG_NOTICE<<"State::frameCompleted() setting time stamp. timestamp="<<timestamp<<std::endl;
    }
}

bool State::DefineMap::updateCurrentDefines()
{
    currentDefines.clear();
    for(DefineStackMap::const_iterator itr = map.begin();
        itr != map.end();
        ++itr)
    {
        const DefineStack::DefineVec& dv = itr->second.defineVec;
        if (!dv.empty())
        {
            const StateSet::DefinePair& dp = dv.back();
            if (dp.second & osg::StateAttribute::ON)
            {
                currentDefines[itr->first] = dp;
            }
        }
    }
    changed = false;
    return true;
}

std::string State::getDefineString(const osg::ShaderDefines& shaderDefines)
{
    if (_defineMap.changed) _defineMap.updateCurrentDefines();

    const StateSet::DefineList& currentDefines = _defineMap.currentDefines;

    ShaderDefines::const_iterator sd_itr = shaderDefines.begin();
    StateSet::DefineList::const_iterator cd_itr = currentDefines.begin();

    std::string shaderDefineStr;

    while(sd_itr != shaderDefines.end() && cd_itr != currentDefines.end())
    {
        if ((*sd_itr) < cd_itr->first) ++sd_itr;
        else if (cd_itr->first < (*sd_itr)) ++cd_itr;
        else
        {
            const StateSet::DefinePair& dp = cd_itr->second;
            shaderDefineStr += "#define ";
            shaderDefineStr += cd_itr->first;
            if (!dp.first.empty())
            {
                if (dp.first[0]!='(') shaderDefineStr += " ";
                shaderDefineStr += dp.first;
            }
#ifdef WIN32
            shaderDefineStr += "\r\n";
#else
            shaderDefineStr += "\n";
#endif

            ++sd_itr;
            ++cd_itr;
        }
    }
    return shaderDefineStr;
}

bool State::supportsShaderRequirements(const osg::ShaderDefines& shaderRequirements)
{
    if (shaderRequirements.empty()) return true;

    if (_defineMap.changed) _defineMap.updateCurrentDefines();

    const StateSet::DefineList& currentDefines = _defineMap.currentDefines;
    for(ShaderDefines::const_iterator sr_itr = shaderRequirements.begin();
        sr_itr != shaderRequirements.end();
        ++sr_itr)
    {
        if (currentDefines.find(*sr_itr)==currentDefines.end()) return false;
    }
    return true;
}

bool State::supportsShaderRequirement(const std::string& shaderRequirement)
{
    if (_defineMap.changed) _defineMap.updateCurrentDefines();
    const StateSet::DefineList& currentDefines = _defineMap.currentDefines;
    return (currentDefines.find(shaderRequirement)!=currentDefines.end());
}

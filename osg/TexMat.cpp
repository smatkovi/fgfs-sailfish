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
#include <osg/GL>
#include <osg/State>
#include <osg/io_utils>
#include <osg/TexMat>
#include <osg/Notify>
#include <osg/TextureRectangle>

using namespace osg;

TexMat::TexMat():
    _scaleByTextureRectangleSize(false)
{
}


TexMat::~TexMat()
{
}

void TexMat::apply(State& state) const
{
#ifdef OSG_GL_FIXED_FUNCTION_AVAILABLE
    glMatrixMode( GL_TEXTURE );
    glLoadMatrix(_matrix.ptr());

    if (_scaleByTextureRectangleSize)
    {
        const osg::TextureRectangle* tex = dynamic_cast<const osg::TextureRectangle*>(state.getLastAppliedTextureAttribute(state.getActiveTextureUnit(), osg::StateAttribute::TEXTURE));
        if (tex)
        {
            glScalef(tex->getTextureWidth(),tex->getTextureHeight(),1.0f);
        }
    }

    glMatrixMode( GL_MODELVIEW );
#else
    /* GLES (FlightGear port): goes to osg_TextureMatrix<unit> */
    {
        static int logged = 0;
        if (logged < 8) { ++logged; OSG_WARN << "TexMat::apply unit=" << state.getActiveTextureUnit() << " matrix=" << _matrix << std::endl; }
    }
    state.setFFPTextureMatrix(state.getActiveTextureUnit(), _matrix);
#endif
}

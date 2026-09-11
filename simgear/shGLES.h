/* shGLES.h - ShivaVG's OpenGL 1.x calls on GLES2 (FlightGear GLES port).
 *
 * Included from shDefs.h under SG_GLES2.  Everything ShivaVG uses that ES
 * does not have is mapped to shgl_* in shGLES.c; ES functions that ShivaVG
 * calls with non-ES enums (glEnable(GL_TEXTURE_1D), glBindTexture with
 * GL_TEXTURE_1D) are wrapped so the enums can be translated.
 */
#ifndef __SHGLES_H
#define __SHGLES_H

#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>

/* enums missing from ES */
#ifndef GL_QUADS
#define GL_QUADS                 0x0007
#endif
#ifndef GL_QUAD_STRIP
#define GL_QUAD_STRIP            0x0008
#endif
#ifndef GL_POLYGON
#define GL_POLYGON               0x0009
#endif
#define GL_MODELVIEW             0x1700
#define GL_PROJECTION            0x1701
#ifndef GL_TEXTURE
#define GL_TEXTURE               0x1702
#endif
#define GL_TEXTURE_1D            0x0DE0
#define GL_TEXTURE_GEN_S         0x0C60
#define GL_TEXTURE_GEN_T         0x0C61
#define GL_TEXTURE_GEN_MODE      0x2500
#define GL_OBJECT_PLANE          0x2501
#define GL_OBJECT_LINEAR         0x2401
#define GL_S                     0x2000
#define GL_T                     0x2001
#define GL_TEXTURE_ENV           0x2300
#define GL_TEXTURE_ENV_MODE      0x2200
#define GL_MODULATE              0x2100
#define GL_VERTEX_ARRAY          0x8074
#define GL_TEXTURE_COORD_ARRAY   0x8078
#define GL_LINE_SMOOTH           0x0B20
#define GL_POLYGON_SMOOTH        0x0B41
#ifndef GL_MULTISAMPLE
#define GL_MULTISAMPLE           0x809D
#endif
#ifndef GL_CLAMP_TO_BORDER
#define GL_CLAMP_TO_BORDER       0x812D
#endif
#define GL_TEXTURE_BORDER_COLOR  0x1004
#define GL_COLOR                 0x1800
#ifndef GL_RGBA8
#define GL_RGBA8                 0x8058
#endif
#define GL_PACK_ROW_LENGTH       0x0D02
#define GL_UNPACK_ROW_LENGTH     0x0CF2
#ifndef GL_MIRRORED_REPEAT
#define GL_MIRRORED_REPEAT       0x8370
#endif

#ifdef __cplusplus
extern "C" {
#endif

void shgl_Begin(GLenum mode);
void shgl_End(void);
void shgl_Vertex2f(GLfloat x, GLfloat y);
void shgl_Vertex2i(GLint x, GLint y);
void shgl_Vertex2fv(const GLfloat* v);
void shgl_Color4f(GLfloat r, GLfloat g, GLfloat b, GLfloat a);
void shgl_Color4fv(const GLfloat* c);
void shgl_TexCoord1f(GLfloat s);
void shgl_TexCoord2f(GLfloat s, GLfloat t);
void shgl_MatrixMode(GLenum mode);
void shgl_LoadIdentity(void);
void shgl_PushMatrix(void);
void shgl_PopMatrix(void);
void shgl_MultMatrixf(const GLfloat* m);
void shgl_LoadMatrixf(const GLfloat* m);
void shgl_Scalef(GLfloat x, GLfloat y, GLfloat z);
void shgl_Ortho(double l, double r, double b, double t, double n, double f);
void shgl_EnableClientState(GLenum a);
void shgl_DisableClientState(GLenum a);
void shgl_VertexPointer(GLint size, GLenum type, GLsizei stride, const void* p);
void shgl_TexCoordPointer(GLint size, GLenum type, GLsizei stride, const void* p);
void shgl_DrawArrays(GLenum mode, GLint first, GLsizei count);
void shgl_Enable(GLenum cap);
void shgl_Disable(GLenum cap);
void shgl_BindTexture(GLenum target, GLuint tex);
void shgl_TexParameteri(GLenum target, GLenum pname, GLint v);
void shgl_TexParameterfv(GLenum target, GLenum pname, const GLfloat* v);
void shgl_TexImage1D(GLenum target, GLint level, GLint internal, GLsizei w,
                     GLint border, GLenum format, GLenum type, const void* data);
void shgl_TexSubImage1D(GLenum target, GLint level, GLint xoff, GLsizei w,
                        GLenum format, GLenum type, const void* data);
void shgl_TexImage2D(GLenum target, GLint level, GLint internal, GLsizei w, GLsizei h,
                     GLint border, GLenum format, GLenum type, const void* data);
void shgl_TexGeni(GLenum coord, GLenum pname, GLint param);
void shgl_TexGenfv(GLenum coord, GLenum pname, const GLfloat* v);
void shgl_TexEnvi(GLenum target, GLenum pname, GLint v);
void shgl_TexEnvf(GLenum target, GLenum pname, GLfloat v);
void shgl_RasterPos2i(GLint x, GLint y);
void shgl_DrawPixels(GLsizei w, GLsizei h, GLenum format, GLenum type, const void* p);
void shgl_CopyPixels(GLint x, GLint y, GLsizei w, GLsizei h, GLenum type);
void shgl_PixelStorei(GLenum pname, GLint v);

/* for SimGear: OSG's matrices (column-major, 16 floats each) */
void shgl_SetMatrices(const GLfloat* projection, const GLfloat* modelview);
/* leave the default VAO, buffer 0 and no program bound; called by SimGear
   after vgDrawPath so OSG can re-apply its own state */
void shgl_Finish(void);

#ifdef __cplusplus
}
#endif

#ifndef SHGLES_IMPL
#define glBegin              shgl_Begin
#define glEnd                shgl_End
#define glVertex2f           shgl_Vertex2f
#define glVertex2i           shgl_Vertex2i
#define glVertex2fv          shgl_Vertex2fv
#define glColor4f            shgl_Color4f
#define glColor4fv           shgl_Color4fv
#define glTexCoord1f         shgl_TexCoord1f
#define glTexCoord2f         shgl_TexCoord2f
#define glMatrixMode         shgl_MatrixMode
#define glLoadIdentity       shgl_LoadIdentity
#define glPushMatrix         shgl_PushMatrix
#define glPopMatrix          shgl_PopMatrix
#define glMultMatrixf        shgl_MultMatrixf
#define glLoadMatrixf        shgl_LoadMatrixf
#define glScalef             shgl_Scalef
#define glOrtho              shgl_Ortho
#define glEnableClientState  shgl_EnableClientState
#define glDisableClientState shgl_DisableClientState
#define glVertexPointer      shgl_VertexPointer
#define glTexCoordPointer    shgl_TexCoordPointer
#define glDrawArrays         shgl_DrawArrays
#define glEnable             shgl_Enable
#define glDisable            shgl_Disable
#define glBindTexture        shgl_BindTexture
#define glTexParameteri      shgl_TexParameteri
#define glTexParameterfv     shgl_TexParameterfv
#define glTexImage1D         shgl_TexImage1D
#define glTexSubImage1D      shgl_TexSubImage1D
#define glTexImage2D         shgl_TexImage2D
#define glTexGeni            shgl_TexGeni
#define glTexGenfv           shgl_TexGenfv
#define glTexEnvi            shgl_TexEnvi
#define glTexEnvf            shgl_TexEnvf
#define glRasterPos2i        shgl_RasterPos2i
#define glDrawPixels         shgl_DrawPixels
#define glCopyPixels         shgl_CopyPixels
#define glPixelStorei        shgl_PixelStorei
#endif /* SHGLES_IMPL */

#endif /* __SHGLES_H */

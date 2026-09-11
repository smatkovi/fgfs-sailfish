#!/usr/bin/env python3
"""SimGear: Canvas vector paths under GLES - ShivaVG on a small GL 1.1 shim.

Glass-cockpit displays (A320 PFD/ND/ECAM, most Canvas instruments) are
drawn as OpenVG paths through ShivaVG, which talks OpenGL 1.x: immediate
mode, client vertex arrays, the matrix stack, 1D textures, texture
generation.  None of that exists under GLES, so the GLES trees were built
with vgu_stubs.c - every vg* call a no-op - and the displays stayed blank
while text and images (which go through OSG) appeared.

Rather than rewrite ShivaVG, this puts a shim underneath it: shGLES.h maps
the fixed-function calls ShivaVG makes to shgl_* functions, and shGLES.c
implements exactly those on GLES2 - a matrix stack, an immediate-mode
buffer (quads become triangles), client arrays through glVertexAttribPointer
on the default VAO, 1D textures as Nx1 2D textures, texgen planes and the
texture matrix in a vertex shader, one program of its own.  ShivaVG's
sources stay untouched; they are simply compiled again instead of the stubs.

CanvasPath hands the shim OSG's projection and modelview matrices before
vgDrawPath (GLES has no matrix state to inherit) and, afterwards, tells OSG
that program, vertex arrays, textures and modes have changed behind its
back.

Idempotent.  python3 sg_canvas_gles.py [simgear-source-root]"""
import os, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/simgear-2020.3.19'
VG = os.path.join(ROOT, 'simgear/canvas/ShivaVG/src')

SHGLES_H = r'''/* shGLES.h - ShivaVG's OpenGL 1.x calls on GLES2 (FlightGear GLES port).
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
'''

SHGLES_C = r'''/* shGLES.c - the GL 1.1 subset ShivaVG needs, on GLES2.  See shGLES.h. */
#define SHGLES_IMPL
#include "shGLES.h"
/* ES3 entry point; libGLESv2 on the device exports it, and declaring it
   here keeps the ES2 headers of shDefs.h in charge */
GL_APICALL void GL_APIENTRY glBindVertexArray(GLuint array);
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

/* ---- matrices (column-major, as OpenGL) -------------------------------- */
#define STACK_DEPTH 16
typedef struct { GLfloat m[STACK_DEPTH][16]; int top; } MatStack;
static MatStack s_stack[3];          /* modelview, projection, texture */
static int s_mode = 0;
static int s_inited = 0;

static void mat_identity(GLfloat* m)
{
    memset(m, 0, 16 * sizeof(GLfloat));
    m[0] = m[5] = m[10] = m[15] = 1.0f;
}
/* r = a * b */
static void mat_mul(GLfloat* r, const GLfloat* a, const GLfloat* b)
{
    GLfloat t[16];
    int c, k;
    for (c = 0; c < 4; ++c)
        for (k = 0; k < 4; ++k)
            t[c * 4 + k] = a[0 * 4 + k] * b[c * 4 + 0] + a[1 * 4 + k] * b[c * 4 + 1]
                         + a[2 * 4 + k] * b[c * 4 + 2] + a[3 * 4 + k] * b[c * 4 + 3];
    memcpy(r, t, sizeof t);
}
static GLfloat* cur(void) { return s_stack[s_mode].m[s_stack[s_mode].top]; }

static void ensure_init(void)
{
    int i;
    if (s_inited) return;
    for (i = 0; i < 3; ++i) { s_stack[i].top = 0; mat_identity(s_stack[i].m[0]); }
    s_inited = 1;
}

void shgl_MatrixMode(GLenum mode)
{
    ensure_init();
    s_mode = (mode == GL_PROJECTION) ? 1 : (mode == GL_TEXTURE) ? 2 : 0;
}
void shgl_LoadIdentity(void) { ensure_init(); mat_identity(cur()); }
void shgl_LoadMatrixf(const GLfloat* m) { ensure_init(); memcpy(cur(), m, 16 * sizeof(GLfloat)); }
void shgl_MultMatrixf(const GLfloat* m) { ensure_init(); mat_mul(cur(), cur(), m); }
void shgl_PushMatrix(void)
{
    MatStack* s;
    ensure_init();
    s = &s_stack[s_mode];
    if (s->top + 1 < STACK_DEPTH) { memcpy(s->m[s->top + 1], s->m[s->top], 16 * sizeof(GLfloat)); ++s->top; }
}
void shgl_PopMatrix(void) { ensure_init(); if (s_stack[s_mode].top > 0) --s_stack[s_mode].top; }
void shgl_Scalef(GLfloat x, GLfloat y, GLfloat z)
{
    GLfloat m[16]; mat_identity(m); m[0] = x; m[5] = y; m[10] = z;
    shgl_MultMatrixf(m);
}
void shgl_Ortho(double l, double r, double b, double t, double n, double f)
{
    GLfloat m[16]; mat_identity(m);
    m[0] = (GLfloat)(2.0 / (r - l)); m[5] = (GLfloat)(2.0 / (t - b)); m[10] = (GLfloat)(-2.0 / (f - n));
    m[12] = (GLfloat)(-(r + l) / (r - l)); m[13] = (GLfloat)(-(t + b) / (t - b)); m[14] = (GLfloat)(-(f + n) / (f - n));
    shgl_MultMatrixf(m);
}
void shgl_SetMatrices(const GLfloat* projection, const GLfloat* modelview)
{
    ensure_init();
    s_stack[0].top = 0; s_stack[1].top = 0; s_stack[2].top = 0;
    memcpy(s_stack[1].m[0], projection, 16 * sizeof(GLfloat));
    memcpy(s_stack[0].m[0], modelview, 16 * sizeof(GLfloat));
    mat_identity(s_stack[2].m[0]);
}

/* ---- state the fixed function pipeline would hold ----------------------- */
static GLfloat s_color[4] = { 1, 1, 1, 1 };
static GLfloat s_tc[2] = { 0, 0 };
static int s_tex1d_on = 0, s_tex2d_on = 0;
static int s_texgen_s = 0, s_texgen_t = 0;
static GLfloat s_plane_s[4] = { 1, 0, 0, 0 }, s_plane_t[4] = { 0, 1, 0, 0 };
static GLuint s_bound1d = 0, s_bound2d = 0;
static int s_va_on = 0, s_ta_on = 0;
static const void* s_vp = 0; static GLint s_vsize = 2; static GLenum s_vtype = GL_FLOAT; static GLsizei s_vstride = 0;
static const void* s_tp = 0; static GLint s_tsize = 2; static GLenum s_ttype = GL_FLOAT; static GLsizei s_tstride = 0;

void shgl_Color4f(GLfloat r, GLfloat g, GLfloat b, GLfloat a) { s_color[0] = r; s_color[1] = g; s_color[2] = b; s_color[3] = a; }
void shgl_Color4fv(const GLfloat* c) { memcpy(s_color, c, sizeof s_color); }
void shgl_TexCoord1f(GLfloat s) { s_tc[0] = s; s_tc[1] = 0.0f; }
void shgl_TexCoord2f(GLfloat s, GLfloat t) { s_tc[0] = s; s_tc[1] = t; }

void shgl_Enable(GLenum cap)
{
    switch (cap) {
    case GL_TEXTURE_1D: s_tex1d_on = 1; return;
    case GL_TEXTURE_2D: s_tex2d_on = 1; return;
    case GL_TEXTURE_GEN_S: s_texgen_s = 1; return;
    case GL_TEXTURE_GEN_T: s_texgen_t = 1; return;
    case GL_LINE_SMOOTH: case GL_POLYGON_SMOOTH: case GL_MULTISAMPLE: return;
    default: glEnable(cap); return;
    }
}
void shgl_Disable(GLenum cap)
{
    switch (cap) {
    case GL_TEXTURE_1D: s_tex1d_on = 0; return;
    case GL_TEXTURE_2D: s_tex2d_on = 0; return;
    case GL_TEXTURE_GEN_S: s_texgen_s = 0; return;
    case GL_TEXTURE_GEN_T: s_texgen_t = 0; return;
    case GL_LINE_SMOOTH: case GL_POLYGON_SMOOTH: case GL_MULTISAMPLE: return;
    default: glDisable(cap); return;
    }
}
void shgl_TexGeni(GLenum coord, GLenum pname, GLint param) { (void)coord; (void)pname; (void)param; }
void shgl_TexGenfv(GLenum coord, GLenum pname, const GLfloat* v)
{
    if (pname != GL_OBJECT_PLANE) return;
    if (coord == GL_S) memcpy(s_plane_s, v, sizeof s_plane_s);
    else if (coord == GL_T) memcpy(s_plane_t, v, sizeof s_plane_t);
}
void shgl_TexEnvi(GLenum target, GLenum pname, GLint v) { (void)target; (void)pname; (void)v; }
void shgl_TexEnvf(GLenum target, GLenum pname, GLfloat v) { (void)target; (void)pname; (void)v; }
void shgl_PixelStorei(GLenum pname, GLint v)
{
    if (pname == GL_PACK_ALIGNMENT || pname == GL_UNPACK_ALIGNMENT) glPixelStorei(pname, v);
}
/* no raster position under ES; vgSetPixels/vgCopyPixels are not used by the canvas */
void shgl_RasterPos2i(GLint x, GLint y) { (void)x; (void)y; }
void shgl_DrawPixels(GLsizei w, GLsizei h, GLenum format, GLenum type, const void* p) { (void)w; (void)h; (void)format; (void)type; (void)p; }
void shgl_CopyPixels(GLint x, GLint y, GLsizei w, GLsizei h, GLenum type) { (void)x; (void)y; (void)w; (void)h; (void)type; }

/* ---- textures: 1D becomes Nx1 2D, float data becomes bytes -------------- */
static GLenum tgt(GLenum target) { return target == GL_TEXTURE_1D ? GL_TEXTURE_2D : target; }

void shgl_BindTexture(GLenum target, GLuint tex)
{
    if (target == GL_TEXTURE_1D) s_bound1d = tex; else s_bound2d = tex;
    glBindTexture(tgt(target), tex);
}
void shgl_TexParameteri(GLenum target, GLenum pname, GLint v)
{
    if (pname == GL_TEXTURE_WRAP_S || pname == GL_TEXTURE_WRAP_T) {
        if (v == GL_CLAMP_TO_BORDER) v = GL_CLAMP_TO_EDGE;   /* no border colour in ES */
    }
    glTexParameteri(tgt(target), pname, v);
}
void shgl_TexParameterfv(GLenum target, GLenum pname, const GLfloat* v)
{
    if (pname == GL_TEXTURE_BORDER_COLOR) return;
    glTexParameterfv(tgt(target), pname, v);
}
static unsigned char* to_bytes(GLsizei count, GLenum format, GLenum type, const void* data)
{
    /* RGBA float -> RGBA ubyte; anything else is passed through */
    unsigned char* out;
    const GLfloat* f = (const GLfloat*)data;
    GLsizei i;
    if (!data || type != GL_FLOAT || format != GL_RGBA) return 0;
    out = (unsigned char*)malloc((size_t)count * 4);
    if (!out) return 0;
    for (i = 0; i < count * 4; ++i) {
        GLfloat v = f[i]; if (v < 0.0f) v = 0.0f; if (v > 1.0f) v = 1.0f;
        out[i] = (unsigned char)(v * 255.0f + 0.5f);
    }
    return out;
}
void shgl_TexImage1D(GLenum target, GLint level, GLint internal, GLsizei w,
                     GLint border, GLenum format, GLenum type, const void* data)
{
    unsigned char* conv = to_bytes(w, format, type, data);
    (void)internal; (void)border; (void)target;
    glTexImage2D(GL_TEXTURE_2D, level, GL_RGBA, w, 1, 0, GL_RGBA, GL_UNSIGNED_BYTE, conv ? conv : (type == GL_FLOAT ? 0 : data));
    free(conv);
}
void shgl_TexSubImage1D(GLenum target, GLint level, GLint xoff, GLsizei w,
                        GLenum format, GLenum type, const void* data)
{
    unsigned char* conv = to_bytes(w, format, type, data);
    (void)target;
    if (!conv && type == GL_FLOAT) return;
    glTexSubImage2D(GL_TEXTURE_2D, level, xoff, 0, w, 1, GL_RGBA, GL_UNSIGNED_BYTE, conv ? conv : data);
    free(conv);
}
void shgl_TexImage2D(GLenum target, GLint level, GLint internal, GLsizei w, GLsizei h,
                     GLint border, GLenum format, GLenum type, const void* data)
{
    /* ES wants internal format == format for unsized formats */
    (void)internal; (void)target;
    if (format == GL_BGRA_EXT) format = GL_RGBA;
    glTexImage2D(GL_TEXTURE_2D, level, format, w, h, border, format, type, data);
}

/* ---- the program ------------------------------------------------------- */
static GLuint s_prog = 0;
static GLint u_mvp = -1, u_texmat = -1, u_texgen = -1, u_planeS = -1, u_planeT = -1, u_color = -1, u_useTex = -1, u_tex = -1;
static int s_prog_failed = 0;
#define A_POS 0
#define A_TEX 1

static const char* VS =
    "attribute vec2 a_pos;\n"
    "attribute vec2 a_tex;\n"
    "uniform mat4 u_mvp;\n"
    "uniform mat4 u_texmat;\n"
    "uniform int u_texgen;\n"
    "uniform vec4 u_planeS;\n"
    "uniform vec4 u_planeT;\n"
    "varying vec2 v_tex;\n"
    "void main() {\n"
    "  vec4 p = vec4(a_pos, 0.0, 1.0);\n"
    "  gl_Position = u_mvp * p;\n"
    "  vec2 tc = a_tex;\n"
    "  if (u_texgen == 1) tc = vec2(dot(u_planeS, p), dot(u_planeT, p));\n"
    "  v_tex = (u_texmat * vec4(tc, 0.0, 1.0)).xy;\n"
    "}\n";
static const char* FS =
    "precision mediump float;\n"
    "uniform vec4 u_color;\n"
    "uniform int u_useTex;\n"
    "uniform sampler2D u_tex;\n"
    "varying vec2 v_tex;\n"
    "void main() {\n"
    "  vec4 c = u_color;\n"
    "  if (u_useTex == 1) c *= texture2D(u_tex, v_tex);\n"
    "  gl_FragColor = c;\n"
    "}\n";

static GLuint compile(GLenum type, const char* src)
{
    GLuint sh = glCreateShader(type);
    GLint ok = 0;
    glShaderSource(sh, 1, &src, 0);
    glCompileShader(sh);
    glGetShaderiv(sh, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[1024]; GLsizei n = 0;
        glGetShaderInfoLog(sh, sizeof log, &n, log);
        fprintf(stderr, "shGLES: shader compile failed: %.*s\n", (int)n, log);
        glDeleteShader(sh); return 0;
    }
    return sh;
}
static int ensure_program(void)
{
    GLuint vs, fs; GLint ok = 0;
    if (s_prog) return 1;
    if (s_prog_failed) return 0;
    vs = compile(GL_VERTEX_SHADER, VS);
    fs = compile(GL_FRAGMENT_SHADER, FS);
    if (!vs || !fs) { s_prog_failed = 1; return 0; }
    s_prog = glCreateProgram();
    glAttachShader(s_prog, vs); glAttachShader(s_prog, fs);
    glBindAttribLocation(s_prog, A_POS, "a_pos");
    glBindAttribLocation(s_prog, A_TEX, "a_tex");
    glLinkProgram(s_prog);
    glGetProgramiv(s_prog, GL_LINK_STATUS, &ok);
    glDeleteShader(vs); glDeleteShader(fs);
    if (!ok) {
        char log[1024]; GLsizei n = 0;
        glGetProgramInfoLog(s_prog, sizeof log, &n, log);
        fprintf(stderr, "shGLES: program link failed: %.*s\n", (int)n, log);
        glDeleteProgram(s_prog); s_prog = 0; s_prog_failed = 1; return 0;
    }
    u_mvp = glGetUniformLocation(s_prog, "u_mvp");
    u_texmat = glGetUniformLocation(s_prog, "u_texmat");
    u_texgen = glGetUniformLocation(s_prog, "u_texgen");
    u_planeS = glGetUniformLocation(s_prog, "u_planeS");
    u_planeT = glGetUniformLocation(s_prog, "u_planeT");
    u_color = glGetUniformLocation(s_prog, "u_color");
    u_useTex = glGetUniformLocation(s_prog, "u_useTex");
    u_tex = glGetUniformLocation(s_prog, "u_tex");
    return 1;
}


static void bind_our_state(void)
{
    GLfloat mvp[16];
    int useTex;
    glBindVertexArray(0);                     /* never touch OSG's VAOs */
    glBindBuffer(GL_ARRAY_BUFFER, 0);         /* client-side pointers */
    glUseProgram(s_prog);
    mat_mul(mvp, s_stack[1].m[s_stack[1].top], s_stack[0].m[s_stack[0].top]);
    glUniformMatrix4fv(u_mvp, 1, GL_FALSE, mvp);
    glUniformMatrix4fv(u_texmat, 1, GL_FALSE, s_stack[2].m[s_stack[2].top]);
    glUniform1i(u_texgen, (s_texgen_s || s_texgen_t) ? 1 : 0);
    glUniform4fv(u_planeS, 1, s_plane_s);
    glUniform4fv(u_planeT, 1, s_plane_t);
    glUniform4fv(u_color, 1, s_color);
    useTex = (s_tex1d_on || s_tex2d_on) ? 1 : 0;
    if (useTex) {
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, s_tex1d_on ? s_bound1d : s_bound2d);
    }
    glUniform1i(u_useTex, useTex);
    glUniform1i(u_tex, 0);
}

/* ---- client arrays ----------------------------------------------------- */
void shgl_EnableClientState(GLenum a) { if (a == GL_VERTEX_ARRAY) s_va_on = 1; else if (a == GL_TEXTURE_COORD_ARRAY) s_ta_on = 1; }
void shgl_DisableClientState(GLenum a) { if (a == GL_VERTEX_ARRAY) s_va_on = 0; else if (a == GL_TEXTURE_COORD_ARRAY) s_ta_on = 0; }
void shgl_VertexPointer(GLint size, GLenum type, GLsizei stride, const void* p) { s_vsize = size; s_vtype = type; s_vstride = stride; s_vp = p; }
void shgl_TexCoordPointer(GLint size, GLenum type, GLsizei stride, const void* p) { s_tsize = size; s_ttype = type; s_tstride = stride; s_tp = p; }

void shgl_DrawArrays(GLenum mode, GLint first, GLsizei count)
{
    ensure_init();
    if (!ensure_program() || !s_va_on || !s_vp || count <= 0) return;
    bind_our_state();
    glEnableVertexAttribArray(A_POS);
    glVertexAttribPointer(A_POS, s_vsize, s_vtype, GL_FALSE, s_vstride, s_vp);
    if (s_ta_on && s_tp) {
        glEnableVertexAttribArray(A_TEX);
        glVertexAttribPointer(A_TEX, s_tsize, s_ttype, GL_FALSE, s_tstride, s_tp);
    } else {
        glDisableVertexAttribArray(A_TEX);
        glVertexAttrib2fv(A_TEX, s_tc);
    }
    if (mode == GL_QUADS || mode == GL_POLYGON) mode = GL_TRIANGLE_FAN;
    glDrawArrays(mode, first, count);
    glDisableVertexAttribArray(A_POS);
    glDisableVertexAttribArray(A_TEX);
}

/* ---- immediate mode ---------------------------------------------------- */
typedef struct { GLfloat x, y, s, t; } ImmVertex;
static ImmVertex* s_imm = 0;
static int s_imm_n = 0, s_imm_cap = 0;
static GLenum s_imm_mode = 0;
static int s_in_begin = 0;

void shgl_Begin(GLenum mode) { s_imm_mode = mode; s_imm_n = 0; s_in_begin = 1; }
static void imm_push(GLfloat x, GLfloat y)
{
    if (s_imm_n >= s_imm_cap) {
        int ncap = s_imm_cap ? s_imm_cap * 2 : 64;
        ImmVertex* nv = (ImmVertex*)realloc(s_imm, (size_t)ncap * sizeof(ImmVertex));
        if (!nv) return;
        s_imm = nv; s_imm_cap = ncap;
    }
    s_imm[s_imm_n].x = x; s_imm[s_imm_n].y = y; s_imm[s_imm_n].s = s_tc[0]; s_imm[s_imm_n].t = s_tc[1];
    ++s_imm_n;
}
void shgl_Vertex2f(GLfloat x, GLfloat y) { if (s_in_begin) imm_push(x, y); }
void shgl_Vertex2i(GLint x, GLint y) { shgl_Vertex2f((GLfloat)x, (GLfloat)y); }
void shgl_Vertex2fv(const GLfloat* v) { shgl_Vertex2f(v[0], v[1]); }

void shgl_End(void)
{
    GLenum mode = s_imm_mode;
    ImmVertex* verts = s_imm;
    int n = s_imm_n;
    ImmVertex* tri = 0;
    s_in_begin = 0;
    if (n < 3) return;
    ensure_init();
    if (!ensure_program()) return;
    if (mode == GL_QUADS) {
        /* every quad as two triangles, keeping the winding */
        int q, nq = n / 4, k = 0;
        tri = (ImmVertex*)malloc((size_t)nq * 6 * sizeof(ImmVertex));
        if (!tri) return;
        for (q = 0; q < nq; ++q) {
            const ImmVertex* v = verts + q * 4;
            tri[k++] = v[0]; tri[k++] = v[1]; tri[k++] = v[2];
            tri[k++] = v[0]; tri[k++] = v[2]; tri[k++] = v[3];
        }
        verts = tri; n = nq * 6; mode = GL_TRIANGLES;
    } else if (mode == GL_QUAD_STRIP) {
        mode = GL_TRIANGLE_STRIP;      /* same vertex order */
    } else if (mode == GL_POLYGON) {
        mode = GL_TRIANGLE_FAN;
    }
    bind_our_state();
    glEnableVertexAttribArray(A_POS);
    glVertexAttribPointer(A_POS, 2, GL_FLOAT, GL_FALSE, sizeof(ImmVertex), &verts[0].x);
    glEnableVertexAttribArray(A_TEX);
    glVertexAttribPointer(A_TEX, 2, GL_FLOAT, GL_FALSE, sizeof(ImmVertex), &verts[0].s);
    glDrawArrays(mode, 0, n);
    glDisableVertexAttribArray(A_POS);
    glDisableVertexAttribArray(A_TEX);
    free(tri);
}

void shgl_Finish(void)
{
    glUseProgram(0);
    glBindBuffer(GL_ARRAY_BUFFER, 0);
}
'''


def patch_file(path, transforms, marker):
    s = open(path).read()
    if marker in s:
        print('  schon aktuell:', os.path.relpath(path, ROOT)); return
    for old, new in transforms:
        assert s.count(old) == 1, 'Anker nicht eindeutig in %s: %r' % (path, old[:60])
        s = s.replace(old, new, 1)
    open(path, 'w').write(s)
    print('  geaendert:', os.path.relpath(path, ROOT))


# 1. the shim itself
for name, body in (('shGLES.h', SHGLES_H), ('shGLES.c', SHGLES_C)):
    p = os.path.join(VG, name)
    if os.path.exists(p) and open(p).read() == body:
        print('  schon aktuell:', name)
    else:
        open(p, 'w').write(body); print('  geschrieben:', name)

# 2. shDefs.h pulls the shim in under GLES
patch_file(os.path.join(VG, 'shDefs.h'), [(
    '''#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
''',
    '''#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>
/* the GL 1.x subset ShivaVG uses, implemented on ES2 (shGLES.c) */
#include "shGLES.h"
''')], '#include "shGLES.h"')

# 3. build ShivaVG again, plus the shim, instead of the stubs - into the
#    scene library like upstream, whose include path for ShivaVG/include
#    already sits on that target
def patch_canvas_cmake():
    path = os.path.join(ROOT, 'simgear/canvas/CMakeLists.txt')
    s = open(path).read()
    final = '''# ShivaVG itself again, on the GLES shim shGLES.c instead of the stubs:
# the canvas paths (glass cockpit displays) draw through it.
set(SHIVAVG_SOURCES "")
foreach(f shArrays.c shContext.c shExtensions.c shGeometry.c shImage.c shPaint.c
          shParams.c shPath.c shPipeline.c shVectors.c shVgu.c shGLES.c)
  list(APPEND SHIVAVG_SOURCES "ShivaVG/src/${f}")
endforeach()
simgear_scene_component(canvas_vgu canvas "${SHIVAVG_SOURCES}" "")'''
    if final in s:
        print('  schon aktuell: simgear/canvas/CMakeLists.txt'); return
    stubs = '''simgear_component(canvas_vgu canvas "ShivaVG/src/shVgu.c;vgu_stubs.c" "")'''
    if stubs in s:
        s = s.replace(stubs, final, 1)
    else:
        # an earlier form of this patch: core component, extra include line
        a = s.index('# ShivaVG itself again'); b = s.index('"${SHIVAVG_SOURCES}" "")') + len('"${SHIVAVG_SOURCES}" "")')
        s = s[:a] + final + s[b:]
    open(path, 'w').write(s); print('  geaendert: simgear/canvas/CMakeLists.txt')
patch_canvas_cmake()

# 3b. shExtensions.c looks GL extension functions up through EGL; under ES
#     none of those extensions exist (multitexture is core), the lookup is
#     never reached, and libEGL is not on fgfs' link line.  Skip it.
patch_file(os.path.join(VG, 'shExtensions.c'), [(
    '''  return (PFVOID)eglGetProcAddress((const unsigned char *)name);
''',
    '''  #if defined(SG_GLES2)
  /* never reached under ES (no ARB extensions there), and libEGL is not
     on the link line */
  (void)name;
  return (PFVOID)NULL;
  #else
  return (PFVOID)eglGetProcAddress((const unsigned char *)name);
  #endif
''')], 'never reached under ES')

# 4. CanvasPath: matrices in, OSG state out
cp = os.path.join(ROOT, 'simgear/canvas/elements/CanvasPath.cxx')
patch_file(cp, [(
    '''        // And finally draw the path
        if( _mode )
          vgDrawPath(_path, _mode);
''',
    '''        // And finally draw the path
#if defined(SG_GLES2)
        // GLES has no matrix state for ShivaVG to inherit; hand it OSG's.
        {
          osg::Matrixf proj(state->getProjectionMatrix());
          osg::Matrixf mv(state->getModelViewMatrix());
          shgl_SetMatrices(proj.ptr(), mv.ptr());
        }
#endif
        if( _mode )
          vgDrawPath(_path, _mode);
#if defined(SG_GLES2)
        // The shim bound its own program, vertex attributes, texture and
        // modes behind OSG's back; make OSG re-apply everything.
        shgl_Finish();
        state->setLastAppliedProgramObject(0);
        state->dirtyAllModes();
        state->dirtyAllAttributes();
        state->dirtyAllVertexArrays();
        if( osg::VertexArrayState* vas = state->getCurrentVertexArrayState() )
          vas->dirty();
#endif
'''), (
    '''#include <vg/openvg.h>
''',
    '''#include <vg/openvg.h>
#if defined(SG_GLES2)
#include "../ShivaVG/src/shGLES.h"
#endif
''')], 'shgl_SetMatrices')

print('fertig')

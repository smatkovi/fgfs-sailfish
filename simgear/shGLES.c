/* shGLES.c - the GL 1.1 subset ShivaVG needs, on GLES2.  See shGLES.h. */
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

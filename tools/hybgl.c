/* hybgl.c - GPU rendert in einen geteilten hybris-Nativpuffer
 *
 * Fortsetzung von hybshare.c: dort schrieb der Client per CPU-Lock
 * hinein, hier zeichnet die GPU. Der Puffer wird als EGLImage
 * eingehaengt und als Farbattachment eines FBO benutzt.
 *
 * Traegt das, koennen Simulator und App denselben Speicher benutzen -
 * die GPU schreibt, die andere Seite liest oder texturiert daraus.
 * Kein memcpy, kein glReadPixels, und ohne den dmabuf-Import, den
 * hybris-EGL nicht anbietet.
 *
 * Uebersetzen:
 *   gcc hybgl.c -o hybgl /usr/lib64/libEGL.so.1 /usr/lib64/libGLESv2.so.2
 * Aufruf:
 *   ./hybgl server &   ./hybgl client
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>

#define SOCK_PATH "/tmp/hybgl.sock"
#define W 256
#define H 128

typedef void*        EGLDisplay;
typedef void*        EGLClientBuffer;
typedef void*        EGLImageKHR;
typedef void*        EGLConfig;
typedef void*        EGLSurface;
typedef void*        EGLContext;
typedef int          EGLint;
typedef unsigned     EGLBoolean;
typedef unsigned     EGLenum;
typedef void       (*fn)(void);
typedef unsigned     GLuint;
typedef unsigned     GLenum;
typedef float        GLfloat;

extern EGLDisplay eglGetDisplay(void*);
extern EGLBoolean eglInitialize(EGLDisplay, EGLint*, EGLint*);
extern EGLBoolean eglBindAPI(EGLenum);
extern EGLBoolean eglChooseConfig(EGLDisplay, const EGLint*, EGLConfig*,
                                  EGLint, EGLint*);
extern EGLSurface eglCreatePbufferSurface(EGLDisplay, EGLConfig, const EGLint*);
extern EGLContext eglCreateContext(EGLDisplay, EGLConfig, EGLContext,
                                   const EGLint*);
extern EGLBoolean eglMakeCurrent(EGLDisplay, EGLSurface, EGLSurface,
                                 EGLContext);
extern EGLint     eglGetError(void);
extern fn         eglGetProcAddress(const char*);

extern void glGenTextures(int, GLuint*);
extern void glBindTexture(GLenum, GLuint);
extern void glTexParameteri(GLenum, GLenum, int);
extern void glGenFramebuffers(int, GLuint*);
extern void glBindFramebuffer(GLenum, GLuint);
extern void glFramebufferTexture2D(GLenum, GLenum, GLenum, GLuint, int);
extern GLenum glCheckFramebufferStatus(GLenum);
extern void glViewport(int, int, int, int);
extern void glClearColor(GLfloat, GLfloat, GLfloat, GLfloat);
extern void glClear(unsigned);
extern void glEnable(GLenum);
extern void glDisable(GLenum);
extern void glScissor(int, int, int, int);
extern void glFinish(void);

#define EGL_OPENGL_ES_API        0x30A0
#define EGL_NO_CONTEXT           ((EGLContext)0)
#define EGL_NO_SURFACE           ((EGLSurface)0)
#define EGL_NONE                 0x3038
#define EGL_WIDTH                0x3057
#define EGL_HEIGHT               0x3056
#define EGL_SURFACE_TYPE         0x3033
#define EGL_PBUFFER_BIT          0x0001
#define EGL_RENDERABLE_TYPE      0x3040
#define EGL_OPENGL_ES2_BIT       0x0004
#define EGL_RED_SIZE             0x3024
#define EGL_GREEN_SIZE           0x3023
#define EGL_BLUE_SIZE            0x3022
#define EGL_ALPHA_SIZE           0x3021
#define EGL_CONTEXT_CLIENT_VERSION 0x3098
#define EGL_NATIVE_BUFFER_HYBRIS 0x3140

#define GL_TEXTURE_2D            0x0DE1
#define GL_TEXTURE_MIN_FILTER    0x2801
#define GL_TEXTURE_MAG_FILTER    0x2800
#define GL_NEAREST               0x2600
#define GL_FRAMEBUFFER           0x8D40
#define GL_COLOR_ATTACHMENT0     0x8CE0
#define GL_FRAMEBUFFER_COMPLETE  0x8CD5
#define GL_COLOR_BUFFER_BIT      0x00004000
#define GL_SCISSOR_TEST          0x0C11

/* Android-Gralloc */
#define FMT_RGBA8888       1
#define USE_SW_READ_OFTEN  0x00000003
#define USE_SW_WRITE_OFTEN 0x00000030
#define USE_HW_TEXTURE     0x00000100
#define USE_HW_RENDER      0x00000200
#define USAGE (USE_HW_TEXTURE | USE_HW_RENDER | \
               USE_SW_READ_OFTEN | USE_SW_WRITE_OFTEN)

typedef EGLBoolean  (*PFNCREATE)(EGLint, EGLint, EGLint, EGLint,
                                 EGLint*, EGLClientBuffer*);
typedef void        (*PFNINFO)(EGLClientBuffer, int*, int*);
typedef void        (*PFNSER)(EGLClientBuffer, int*, int*);
typedef EGLBoolean  (*PFNREMOTE)(EGLint, EGLint, EGLint, EGLint, EGLint,
                                 int, int*, int, int*, EGLClientBuffer*);
typedef EGLBoolean  (*PFNLOCK)(EGLClientBuffer, EGLint, EGLint, EGLint,
                               EGLint, EGLint, void**);
typedef EGLBoolean  (*PFNUNLOCK)(EGLClientBuffer);
typedef EGLImageKHR (*PFNIMAGE)(EGLDisplay, EGLContext, EGLenum,
                                EGLClientBuffer, const EGLint*);
typedef void        (*PFNTARGET)(GLenum, EGLImageKHR);

static EGLDisplay dpy;
static PFNCREATE p_create;
static PFNINFO   p_info;
static PFNSER    p_ser;
static PFNREMOTE p_remote;
static PFNLOCK   p_lock;
static PFNUNLOCK p_unlock;
static PFNIMAGE  p_image;
static PFNTARGET p_target;

static int load_procs(void)
{
    EGLint a, b;
    dpy = eglGetDisplay((void*)0);
    if (!eglInitialize(dpy, &a, &b)) { puts("EGL-Init fehlgeschlagen"); return 0; }
    p_create = (PFNCREATE)eglGetProcAddress("eglHybrisCreateNativeBuffer");
    p_info   = (PFNINFO)  eglGetProcAddress("eglHybrisGetNativeBufferInfo");
    p_ser    = (PFNSER)   eglGetProcAddress("eglHybrisSerializeNativeBuffer");
    p_remote = (PFNREMOTE)eglGetProcAddress("eglHybrisCreateRemoteBuffer");
    p_lock   = (PFNLOCK)  eglGetProcAddress("eglHybrisLockNativeBuffer");
    p_unlock = (PFNUNLOCK)eglGetProcAddress("eglHybrisUnlockNativeBuffer");
    p_image  = (PFNIMAGE) eglGetProcAddress("eglCreateImageKHR");
    p_target = (PFNTARGET)eglGetProcAddress("glEGLImageTargetTexture2DOES");
    if (!p_create || !p_remote || !p_lock || !p_image || !p_target) {
        puts("Funktionen fehlen"); return 0;
    }
    return 1;
}

static int make_context(void)
{
    const EGLint cfgAttr[] = {
        EGL_SURFACE_TYPE,    EGL_PBUFFER_BIT,
        EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
        EGL_RED_SIZE, 8, EGL_GREEN_SIZE, 8,
        EGL_BLUE_SIZE, 8, EGL_ALPHA_SIZE, 8,
        EGL_NONE };
    const EGLint pbAttr[]  = { EGL_WIDTH, 16, EGL_HEIGHT, 16, EGL_NONE };
    const EGLint ctxAttr[] = { EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE };
    EGLConfig cfg; EGLint num = 0;
    EGLSurface surf; EGLContext ctx;

    if (!eglBindAPI(EGL_OPENGL_ES_API)) { puts("BindAPI fehlgeschlagen"); return 0; }
    if (!eglChooseConfig(dpy, cfgAttr, &cfg, 1, &num) || num < 1) {
        puts("keine passende Config"); return 0;
    }
    /* Der Blob bietet kein EGL_KHR_surfaceless_context, deshalb ein
       winziger Pbuffer als Kontextziel. Gerendert wird ins FBO. */
    surf = eglCreatePbufferSurface(dpy, cfg, pbAttr);
    if (!surf) { printf("Pbuffer fehlgeschlagen 0x%x\n", eglGetError()); return 0; }
    ctx = eglCreateContext(dpy, cfg, EGL_NO_CONTEXT, ctxAttr);
    if (!ctx) { printf("Kontext fehlgeschlagen 0x%x\n", eglGetError()); return 0; }
    if (!eglMakeCurrent(dpy, surf, surf, ctx)) {
        printf("MakeCurrent fehlgeschlagen 0x%x\n", eglGetError()); return 0;
    }
    return 1;
}

/* --- Socket ------------------------------------------------------- */

static int send_desc(int s, EGLint stride, int ni, int* ints, int nf, int* fds)
{
    int head[3] = { stride, ni, nf };
    char cbuf[CMSG_SPACE(16 * sizeof(int))];
    struct iovec iov[2];
    struct msghdr msg;
    struct cmsghdr* cm;
    memset(cbuf, 0, sizeof cbuf);
    iov[0].iov_base = head;  iov[0].iov_len = sizeof head;
    iov[1].iov_base = ints;  iov[1].iov_len = ni * sizeof(int);
    memset(&msg, 0, sizeof msg);
    msg.msg_iov = iov;  msg.msg_iovlen = 2;
    msg.msg_control = cbuf;
    msg.msg_controllen = CMSG_SPACE(nf * sizeof(int));
    cm = CMSG_FIRSTHDR(&msg);
    cm->cmsg_level = SOL_SOCKET;
    cm->cmsg_type  = SCM_RIGHTS;
    cm->cmsg_len   = CMSG_LEN(nf * sizeof(int));
    memcpy(CMSG_DATA(cm), fds, nf * sizeof(int));
    return sendmsg(s, &msg, 0) > 0;
}

static int recv_desc(int s, EGLint* stride, int* ni, int* ints,
                     int* nf, int* fds)
{
    int head[3];
    char cbuf[CMSG_SPACE(16 * sizeof(int))];
    struct iovec iov[2];
    struct msghdr msg;
    struct cmsghdr* cm;
    iov[0].iov_base = head;  iov[0].iov_len = sizeof head;
    iov[1].iov_base = ints;  iov[1].iov_len = 128 * sizeof(int);
    memset(&msg, 0, sizeof msg);
    msg.msg_iov = iov;  msg.msg_iovlen = 2;
    msg.msg_control = cbuf;
    msg.msg_controllen = sizeof cbuf;
    if (recvmsg(s, &msg, 0) <= 0) return 0;
    *stride = head[0];  *ni = head[1];  *nf = head[2];
    cm = CMSG_FIRSTHDR(&msg);
    if (!cm || cm->cmsg_type != SCM_RIGHTS) return 0;
    memcpy(fds, CMSG_DATA(cm), *nf * sizeof(int));
    return 1;
}

/* --- Server: legt an, liest per CPU nach ------------------------- */

static int run_server(void)
{
    EGLint stride = 0;
    EGLClientBuffer buf = 0;
    int ni = 0, nf = 0, ints[128], fds[16];
    int ls, cs;
    struct sockaddr_un sa;
    void* va = 0;

    if (!p_create(W, H, USAGE, FMT_RGBA8888, &stride, &buf)) {
        puts("Server: CreateNativeBuffer fehlgeschlagen"); return 1;
    }
    printf("Server: Puffer %dx%d, stride=%d\n", W, H, stride);
    p_info(buf, &ni, &nf);
    if (ni > 128 || nf > 16) { puts("Server: zu gross"); return 1; }
    p_ser(buf, ints, fds);

    unlink(SOCK_PATH);
    ls = socket(AF_UNIX, SOCK_STREAM, 0);
    memset(&sa, 0, sizeof sa);
    sa.sun_family = AF_UNIX;
    strncpy(sa.sun_path, SOCK_PATH, sizeof(sa.sun_path) - 1);
    if (bind(ls, (struct sockaddr*)&sa, sizeof sa) < 0) { perror("bind"); return 1; }
    listen(ls, 1);
    puts("Server: warte auf Client ...");
    cs = accept(ls, 0, 0);
    if (cs < 0) { perror("accept"); return 1; }
    if (!send_desc(cs, stride, ni, ints, nf, fds)) {
        puts("Server: senden fehlgeschlagen"); return 1;
    }
    puts("Server: Beschreibung gesendet, warte auf die GPU ...");
    { char ack; if (read(cs, &ack, 1) != 1) { puts("Server: keine Antwort"); return 1; } }

    if (!p_lock(buf, USE_SW_READ_OFTEN, 0, 0, W, H, &va) || !va) {
        puts("Server: Lock fehlgeschlagen"); return 1;
    }
    {
        unsigned* px = (unsigned*)va;
        unsigned ecke  = px[0];
        unsigned mitte = px[(H / 2) * stride + (W / 2)];
        printf("Server: Ecke = 0x%08x, Mitte = 0x%08x\n", ecke, mitte);
        /* Client faerbt alles blau und ein Quadrat in der Mitte gruen.
           RGBA im Speicher: blau = 0xFFFF0000, gruen = 0xFF00FF00. */
        if (ecke == 0xFFFF0000u && mitte == 0xFF00FF00u)
            puts("\n  ERFOLG: die GPU hat in den geteilten Puffer gezeichnet.\n");
        else
            puts("\n  Muster stimmt nicht - die GPU schreibt woanders hin.\n");
    }
    p_unlock(buf);
    close(cs); close(ls); unlink(SOCK_PATH);
    return 0;
}

/* --- Client: stellt wieder her, zeichnet mit der GPU -------------- */

static int run_client(void)
{
    EGLint stride = 0;
    int ni = 0, nf = 0, ints[128], fds[16];
    EGLClientBuffer buf = 0;
    EGLImageKHR img;
    GLuint tex = 0, fbo = 0;
    GLenum st;
    int s;
    struct sockaddr_un sa;

    s = socket(AF_UNIX, SOCK_STREAM, 0);
    memset(&sa, 0, sizeof sa);
    sa.sun_family = AF_UNIX;
    strncpy(sa.sun_path, SOCK_PATH, sizeof(sa.sun_path) - 1);
    if (connect(s, (struct sockaddr*)&sa, sizeof sa) < 0) { perror("connect"); return 1; }
    if (!recv_desc(s, &stride, &ni, ints, &nf, fds)) {
        puts("Client: empfangen fehlgeschlagen"); return 1;
    }
    printf("Client: stride=%d, %d ints, %d fds\n", stride, ni, nf);

    if (!p_remote(W, H, USAGE, FMT_RGBA8888, stride,
                  ni, ints, nf, fds, &buf) || !buf) {
        puts("Client: CreateRemoteBuffer fehlgeschlagen"); return 1;
    }
    puts("Client: Puffer wiederhergestellt");

    if (!make_context()) return 1;
    puts("Client: EGL-Kontext steht");

    img = p_image(dpy, EGL_NO_CONTEXT, EGL_NATIVE_BUFFER_HYBRIS, buf, 0);
    if (!img) { printf("Client: EGLImage fehlgeschlagen 0x%x\n", eglGetError()); return 1; }
    puts("Client: EGLImage angelegt");

    glGenTextures(1, &tex);
    glBindTexture(GL_TEXTURE_2D, tex);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    p_target(GL_TEXTURE_2D, img);

    glGenFramebuffers(1, &fbo);
    glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                           GL_TEXTURE_2D, tex, 0);
    st = glCheckFramebufferStatus(GL_FRAMEBUFFER);
    if (st != GL_FRAMEBUFFER_COMPLETE) {
        printf("Client: FBO unvollstaendig 0x%x\n", st); return 1;
    }
    puts("Client: FBO mit geteiltem Puffer als Farbattachment");

    glViewport(0, 0, W, H);
    glClearColor(0.0f, 0.0f, 1.0f, 1.0f);      /* blau */
    glClear(GL_COLOR_BUFFER_BIT);
    glEnable(GL_SCISSOR_TEST);
    glScissor(W / 2 - 8, H / 2 - 8, 16, 16);
    glClearColor(0.0f, 1.0f, 0.0f, 1.0f);      /* gruenes Quadrat */
    glClear(GL_COLOR_BUFFER_BIT);
    glDisable(GL_SCISSOR_TEST);
    glFinish();
    puts("Client: gezeichnet");

    { char ack = 'k'; write(s, &ack, 1); }
    sleep(1);
    close(s);
    return 0;
}

int main(int argc, char** argv)
{
    if (argc < 2) { puts("Aufruf: hybgl server | client"); return 1; }
    if (!load_procs()) return 1;
    if (!strcmp(argv[1], "server")) return run_server();
    if (!strcmp(argv[1], "client")) return run_client();
    puts("Aufruf: hybgl server | client");
    return 1;
}

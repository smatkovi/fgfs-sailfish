/* hybshare.c - teilt einen hybris-Nativpuffer zwischen zwei Prozessen
 *
 * EGL_HYBRIS_native_buffer2 erlaubt es, einen Puffer anzulegen, seine
 * Beschreibung zu serialisieren und ihn in einem anderen Prozess
 * wiederherzustellen. Wenn das traegt, koennen Simulator und App
 * denselben Speicher benutzen - ohne memcpy, ohne glReadPixels und
 * ohne den dmabuf-Import, den hybris-EGL nicht anbietet.
 *
 * Ablauf:
 *   Server legt den Puffer an, serialisiert ihn, schickt Ints und
 *   Deskriptoren ueber einen Unix-Socket und wartet.
 *   Client stellt ihn wieder her, schreibt ein Muster hinein.
 *   Server liest und prueft.
 *
 * Uebersetzen:
 *   gcc hybshare.c -o hybshare /usr/lib64/libEGL.so.1
 * Aufruf:
 *   ./hybshare server &   ./hybshare client
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>

#define SOCK_PATH "/tmp/hybshare.sock"
#define W 256
#define H 128

typedef void*    EGLDisplay;
typedef void*    EGLClientBuffer;
typedef int      EGLint;
typedef unsigned EGLBoolean;
typedef void   (*fn)(void);

extern EGLDisplay eglGetDisplay(void*);
extern EGLBoolean eglInitialize(EGLDisplay, EGLint*, EGLint*);
extern fn         eglGetProcAddress(const char*);

typedef EGLBoolean (*PFNCREATE)(EGLint, EGLint, EGLint, EGLint,
                                EGLint*, EGLClientBuffer*);
typedef void       (*PFNINFO)(EGLClientBuffer, int*, int*);
typedef void       (*PFNSER)(EGLClientBuffer, int*, int*);
typedef EGLBoolean (*PFNREMOTE)(EGLint, EGLint, EGLint, EGLint, EGLint,
                                int, int*, int, int*, EGLClientBuffer*);
typedef EGLBoolean (*PFNLOCK)(EGLClientBuffer, EGLint, EGLint, EGLint,
                              EGLint, EGLint, void**);
typedef EGLBoolean (*PFNUNLOCK)(EGLClientBuffer);

/* Android-Gralloc-Konstanten */
#define FMT_RGBA8888       1
#define USE_SW_READ_OFTEN  0x00000003
#define USE_SW_WRITE_OFTEN 0x00000030
#define USE_HW_TEXTURE     0x00000100
#define USE_HW_RENDER      0x00000200
#define USAGE (USE_HW_TEXTURE | USE_HW_RENDER | \
               USE_SW_READ_OFTEN | USE_SW_WRITE_OFTEN)

static PFNCREATE p_create;
static PFNINFO   p_info;
static PFNSER    p_ser;
static PFNREMOTE p_remote;
static PFNLOCK   p_lock;
static PFNUNLOCK p_unlock;

static int load_procs(void)
{
    EGLDisplay d = eglGetDisplay((void*)0);
    EGLint a, b;
    if (!eglInitialize(d, &a, &b)) { puts("EGL-Init fehlgeschlagen"); return 0; }
    p_create = (PFNCREATE)eglGetProcAddress("eglHybrisCreateNativeBuffer");
    p_info   = (PFNINFO)  eglGetProcAddress("eglHybrisGetNativeBufferInfo");
    p_ser    = (PFNSER)   eglGetProcAddress("eglHybrisSerializeNativeBuffer");
    p_remote = (PFNREMOTE)eglGetProcAddress("eglHybrisCreateRemoteBuffer");
    p_lock   = (PFNLOCK)  eglGetProcAddress("eglHybrisLockNativeBuffer");
    p_unlock = (PFNUNLOCK)eglGetProcAddress("eglHybrisUnlockNativeBuffer");
    if (!p_create || !p_info || !p_ser || !p_remote || !p_lock || !p_unlock) {
        puts("Funktionen fehlen"); return 0;
    }
    return 1;
}

/* --- Socket: Ints als Nutzlast, Deskriptoren als Beipack ---------- */

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
    ssize_t n;

    iov[0].iov_base = head;  iov[0].iov_len = sizeof head;
    iov[1].iov_base = ints;  iov[1].iov_len = 128 * sizeof(int);

    memset(&msg, 0, sizeof msg);
    msg.msg_iov = iov;  msg.msg_iovlen = 2;
    msg.msg_control = cbuf;
    msg.msg_controllen = sizeof cbuf;

    n = recvmsg(s, &msg, 0);
    if (n <= 0) return 0;

    *stride = head[0];  *ni = head[1];  *nf = head[2];
    cm = CMSG_FIRSTHDR(&msg);
    if (!cm || cm->cmsg_type != SCM_RIGHTS) return 0;
    memcpy(fds, CMSG_DATA(cm), *nf * sizeof(int));
    return 1;
}

/* --- Server ------------------------------------------------------- */

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
    printf("Server: %d ints, %d fds\n", ni, nf);
    if (ni > 128 || nf > 16) { puts("Server: zu gross"); return 1; }
    p_ser(buf, ints, fds);

    unlink(SOCK_PATH);
    ls = socket(AF_UNIX, SOCK_STREAM, 0);
    memset(&sa, 0, sizeof sa);
    sa.sun_family = AF_UNIX;
    strncpy(sa.sun_path, SOCK_PATH, sizeof(sa.sun_path) - 1);
    if (bind(ls, (struct sockaddr*)&sa, sizeof sa) < 0) {
        perror("bind"); return 1;
    }
    listen(ls, 1);
    puts("Server: warte auf Client ...");
    cs = accept(ls, 0, 0);
    if (cs < 0) { perror("accept"); return 1; }

    if (!send_desc(cs, stride, ni, ints, nf, fds)) {
        puts("Server: senden fehlgeschlagen"); return 1;
    }
    puts("Server: Beschreibung gesendet, warte auf Antwort ...");

    { char ack; read(cs, &ack, 1); }

    if (!p_lock(buf, USE_SW_READ_OFTEN, 0, 0, W, H, &va) || !va) {
        puts("Server: Lock fehlgeschlagen"); return 1;
    }
    {
        unsigned* px = (unsigned*)va;
        unsigned a = px[0];
        unsigned b = px[(H / 2) * stride + (W / 2)];
        printf("Server: erstes Pixel = 0x%08x, Mitte = 0x%08x\n", a, b);
        if (a == 0xFF0000FFu && b == 0xFF00FF00u)
            puts("\n  ERFOLG: der Client hat in denselben Speicher geschrieben.\n");
        else
            puts("\n  Muster stimmt nicht - der Puffer wird nicht geteilt.\n");
    }
    p_unlock(buf);
    close(cs); close(ls); unlink(SOCK_PATH);
    return 0;
}

/* --- Client ------------------------------------------------------- */

static int run_client(void)
{
    EGLint stride = 0;
    int ni = 0, nf = 0, ints[128], fds[16];
    EGLClientBuffer buf = 0;
    int s;
    struct sockaddr_un sa;
    void* va = 0;

    s = socket(AF_UNIX, SOCK_STREAM, 0);
    memset(&sa, 0, sizeof sa);
    sa.sun_family = AF_UNIX;
    strncpy(sa.sun_path, SOCK_PATH, sizeof(sa.sun_path) - 1);
    if (connect(s, (struct sockaddr*)&sa, sizeof sa) < 0) {
        perror("connect"); return 1;
    }
    if (!recv_desc(s, &stride, &ni, ints, &nf, fds)) {
        puts("Client: empfangen fehlgeschlagen"); return 1;
    }
    printf("Client: stride=%d, %d ints, %d fds\n", stride, ni, nf);

    if (!p_remote(W, H, USAGE, FMT_RGBA8888, stride,
                  ni, ints, nf, fds, &buf) || !buf) {
        puts("Client: CreateRemoteBuffer fehlgeschlagen"); return 1;
    }
    puts("Client: Puffer wiederhergestellt");

    if (!p_lock(buf, USE_SW_WRITE_OFTEN, 0, 0, W, H, &va) || !va) {
        puts("Client: Lock fehlgeschlagen"); return 1;
    }
    {
        unsigned* px = (unsigned*)va;
        int x, y;
        for (y = 0; y < H; ++y)
            for (x = 0; x < W; ++x)
                px[y * stride + x] = 0xFF0000FFu;      /* rot */
        px[(H / 2) * stride + (W / 2)] = 0xFF00FF00u;  /* gruen in der Mitte */
    }
    p_unlock(buf);
    puts("Client: Muster geschrieben");

    { char ack = 'k'; write(s, &ack, 1); }
    sleep(1);
    close(s);
    return 0;
}

int main(int argc, char** argv)
{
    if (argc < 2) { puts("Aufruf: hybshare server | client"); return 1; }
    if (!load_procs()) return 1;
    if (!strcmp(argv[1], "server")) return run_server();
    if (!strcmp(argv[1], "client")) return run_client();
    puts("Aufruf: hybshare server | client");
    return 1;
}

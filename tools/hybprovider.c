/* hybprovider.c - stellt einen hybris-Nativpuffer bereit
 *
 * Ersetzt fuers Erste die App: legt den Puffer an, haelt seine
 * Beschreibung auf einem Socket bereit und schreibt in Abstaenden
 * ein PPM, damit man sieht, was der Simulator hineingezeichnet hat.
 *
 * Uebersetzen:
 *   gcc hybprovider.c -o hybprovider /usr/lib64/libEGL.so.1
 * Aufruf:
 *   ./hybprovider [breite hoehe]
 * Der Simulator wird dann mit FGFS_HYB_SOCKET=/tmp/fgfs-hybbuf.sock
 * gestartet.
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <signal.h>
#include <fcntl.h>
#include <sys/select.h>
#include <sys/time.h>
#include <sys/socket.h>
#include <sys/un.h>

#define SOCK_PATH "/tmp/fgfs-hybbuf.sock"

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
typedef EGLBoolean (*PFNLOCK)(EGLClientBuffer, EGLint, EGLint, EGLint,
                              EGLint, EGLint, void**);
typedef EGLBoolean (*PFNUNLOCK)(EGLClientBuffer);

#define FMT_RGBA8888       1
#define USE_SW_READ_OFTEN  0x00000003
#define USE_SW_WRITE_OFTEN 0x00000030
#define USE_HW_TEXTURE     0x00000100
#define USE_HW_RENDER      0x00000200
#define USAGE (USE_HW_TEXTURE | USE_HW_RENDER | \
               USE_SW_READ_OFTEN | USE_SW_WRITE_OFTEN)

static volatile int running = 1;
static void on_int(int sig) { (void)sig; running = 0; }

int main(int argc, char** argv)
{
    const int W = (argc > 2) ? atoi(argv[1]) : 1024;
    const int H = (argc > 2) ? atoi(argv[2]) : 768;

    EGLDisplay d = eglGetDisplay((void*)0);
    EGLint a, b;
    if (!eglInitialize(d, &a, &b)) { puts("EGL-Init fehlgeschlagen"); return 1; }

    PFNCREATE create = (PFNCREATE)eglGetProcAddress("eglHybrisCreateNativeBuffer");
    PFNINFO   info   = (PFNINFO)  eglGetProcAddress("eglHybrisGetNativeBufferInfo");
    PFNSER    ser    = (PFNSER)   eglGetProcAddress("eglHybrisSerializeNativeBuffer");
    PFNLOCK   lock   = (PFNLOCK)  eglGetProcAddress("eglHybrisLockNativeBuffer");
    PFNUNLOCK unlock = (PFNUNLOCK)eglGetProcAddress("eglHybrisUnlockNativeBuffer");
    if (!create || !info || !ser || !lock || !unlock) {
        puts("Funktionen fehlen"); return 1;
    }

    EGLint stride = 0;
    EGLClientBuffer buf = 0;
    if (!create(W, H, USAGE, FMT_RGBA8888, &stride, &buf)) {
        puts("CreateNativeBuffer fehlgeschlagen"); return 1;
    }
    printf("Puffer %dx%d, stride=%d\n", W, H, stride);

    int ni = 0, nf = 0, ints[128], fds[16];
    info(buf, &ni, &nf);
    if (ni > 128 || nf > 16) { puts("Beschreibung zu gross"); return 1; }
    ser(buf, ints, fds);
    printf("Beschreibung: %d ints, %d fds\n", ni, nf);

    unlink(SOCK_PATH);
    int ls = socket(AF_UNIX, SOCK_STREAM, 0);
    struct sockaddr_un sa;
    memset(&sa, 0, sizeof sa);
    sa.sun_family = AF_UNIX;
    strncpy(sa.sun_path, SOCK_PATH, sizeof(sa.sun_path) - 1);
    if (bind(ls, (struct sockaddr*)&sa, sizeof sa) < 0) { perror("bind"); return 1; }
    listen(ls, 4);
    printf("bereit auf %s - Simulator mit FGFS_HYB_SOCKET=%s starten\n",
           SOCK_PATH, SOCK_PATH);

    signal(SIGINT, on_int);

    /* Anfragen im Hintergrund bedienen, dazwischen nachsehen */
    int seen = 0;
    while (running) {
        struct timeval tv = { 1, 0 };
        fd_set rf;
        FD_ZERO(&rf); FD_SET(ls, &rf);
        if (select(ls + 1, &rf, 0, 0, &tv) > 0) {
            int cs = accept(ls, 0, 0);
            if (cs >= 0) {
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
                if (sendmsg(cs, &msg, 0) > 0)
                    puts("Beschreibung an Simulator uebergeben");
                /* offen lassen: schliesst der Simulator, merken wir es */
                if (seen) close(seen);
                seen = cs;
            }
        }

        /* nachsehen, was drinsteht */
        void* va = 0;
        if (lock(buf, USE_SW_READ_OFTEN, 0, 0, W, H, &va) && va) {
            unsigned* px = (unsigned*)va;
            printf("  Mitte = 0x%08x   Ecke = 0x%08x\n",
                   px[(H / 2) * stride + (W / 2)], px[0]);
            static int dumped = 0;
            if (!dumped && px[(H / 2) * stride + (W / 2)] != 0) {
                FILE* f = fopen("/tmp/hybframe.ppm", "wb");
                if (f) {
                    fprintf(f, "P6\n%d %d\n255\n", W, H);
                    for (int y = 0; y < H; ++y)
                        for (int x = 0; x < W; ++x) {
                            unsigned p = px[y * stride + x];
                            fputc( p        & 0xFF, f);
                            fputc((p >>  8) & 0xFF, f);
                            fputc((p >> 16) & 0xFF, f);
                        }
                    fclose(f);
                    puts("  -> /tmp/hybframe.ppm geschrieben");
                    dumped = 1;
                }
            }
            unlock(buf);
        }
    }

    close(ls); unlink(SOCK_PATH);
    puts("beendet");
    return 0;
}

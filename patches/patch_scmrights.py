#!/usr/bin/env python3
"""
Deskriptor-Uebergabe per SCM_RIGHTS.

Der Kernel lehnt das Wiederoeffnen eines dmabuf ueber /proc/<pid>/fd/
mit ENXIO ab - hinter dem Pfad steht kein echtes Dateisystemobjekt.
Der vorgesehene Weg ist die Uebergabe ueber einen Unix-Socket mit
SCM_RIGHTS.

Simulator-Seite: ein Socket unter /tmp/fgfs-frame.sock, bedient von
einem eigenen Thread. Jeder Verbindung wird der dmabuf-Deskriptor
geschickt, danach wird die Verbindung geschlossen. Der Puffer bleibt
ueber die gesamte Laufzeit derselbe, die Uebertragung passiert also
einmal pro Presenter, nicht pro Frame.
"""

import sys

GW = '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5/src/osgViewer/GraphicsWindowEGL.cpp'

INC_OLD = '#include <linux/types.h>'
INC_NEW = '''#include <linux/types.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <pthread.h>'''

# ---- Server-Thread --------------------------------------------------
SERVER = '''
/* ------------------------------------------------------------------ *
 *  Uebergabe des dmabuf-Deskriptors per SCM_RIGHTS
 *
 *  /proc/<pid>/fd/<n> laesst sich fuer anonyme Inodes nicht erneut
 *  oeffnen (ENXIO), deshalb dieser Weg. Der Deskriptor wandert einmal
 *  pro Presenter ueber den Socket, nicht pro Frame.
 * ------------------------------------------------------------------ */
namespace {

struct FdServer {
    int listenFd = -1;
    int payloadFd = -1;
    pthread_t thread;
    bool running = false;

    static void* loop(void* arg)
    {
        FdServer* self = static_cast<FdServer*>(arg);
        while (self->running) {
            int c = ::accept(self->listenFd, nullptr, nullptr);
            if (c < 0) {
                if (errno == EINTR) continue;
                break;
            }
            self->sendFd(c);
            ::close(c);
        }
        return nullptr;
    }

    void sendFd(int conn)
    {
        char dummy = 'F';
        struct iovec iov;
        iov.iov_base = &dummy;
        iov.iov_len = 1;

        char cbuf[CMSG_SPACE(sizeof(int))];
        memset(cbuf, 0, sizeof cbuf);

        struct msghdr msg;
        memset(&msg, 0, sizeof msg);
        msg.msg_iov = &iov;
        msg.msg_iovlen = 1;
        msg.msg_control = cbuf;
        msg.msg_controllen = sizeof cbuf;

        struct cmsghdr* cm = CMSG_FIRSTHDR(&msg);
        cm->cmsg_level = SOL_SOCKET;
        cm->cmsg_type = SCM_RIGHTS;
        cm->cmsg_len = CMSG_LEN(sizeof(int));
        memcpy(CMSG_DATA(cm), &payloadFd, sizeof(int));

        if (::sendmsg(conn, &msg, 0) < 0)
            OSG_WARN << "FdServer: sendmsg fehlgeschlagen" << std::endl;
    }

    bool start(int fd, const char* path)
    {
        payloadFd = fd;

        listenFd = ::socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
        if (listenFd < 0) return false;

        ::unlink(path);

        struct sockaddr_un addr;
        memset(&addr, 0, sizeof addr);
        addr.sun_family = AF_UNIX;
        strncpy(addr.sun_path, path, sizeof(addr.sun_path) - 1);

        if (::bind(listenFd, (struct sockaddr*)&addr, sizeof addr) < 0) {
            OSG_WARN << "FdServer: bind auf " << path
                     << " fehlgeschlagen" << std::endl;
            ::close(listenFd); listenFd = -1;
            return false;
        }
        ::chmod(path, 0666);

        if (::listen(listenFd, 4) < 0) {
            ::close(listenFd); listenFd = -1;
            return false;
        }

        running = true;
        if (::pthread_create(&thread, nullptr, &FdServer::loop, this) != 0) {
            running = false;
            ::close(listenFd); listenFd = -1;
            return false;
        }
        OSG_WARN << "FdServer: uebergibt dmabuf ueber " << path << std::endl;
        return true;
    }
};

FdServer g_fdServer;

} // anonymous namespace
'''

ANCHOR = 'namespace osgViewer {'

# ---- Server beim Import starten -------------------------------------
START_OLD = '''                    shared = true;
                    OSG_WARN << "GraphicsWindowEGL: Zero-Copy aktiv, dmabuf fd="
                             << _dmabufFd << " pid=" << getpid()
                             << " stride=" << (w * 4) << std::endl;'''

START_NEW = '''                    shared = true;
                    OSG_WARN << "GraphicsWindowEGL: Zero-Copy aktiv, dmabuf fd="
                             << _dmabufFd << " pid=" << getpid()
                             << " stride=" << (w * 4) << std::endl;

                    const char* sp = ::getenv("FGFS_FD_SOCKET");
                    if (!sp || !*sp) sp = "/tmp/fgfs-frame.sock";
                    g_fdServer.start(_dmabufFd, sp);'''


def main():
    try:
        s = open(GW).read()
    except FileNotFoundError:
        print("nicht gefunden - im Container ausfuehren:", GW)
        return 1

    if 'FdServer' in s:
        print("bereits gepatcht")
        return 0

    for old, new, label in (
        (INC_OLD,   INC_NEW,            "Includes"),
        (ANCHOR,    SERVER + '\n' + ANCHOR, "FdServer eingefuegt"),
        (START_OLD, START_NEW,          "Server-Start"),
    ):
        if old not in s:
            print("FEHLER: Muster nicht gefunden:", label)
            return 1
        s = s.replace(old, new, 1)
        print("gepatcht:", label)

    open(GW, 'w').write(s)
    print("\nfertig - OSG neu bauen")
    return 0


if __name__ == '__main__':
    sys.exit(main())

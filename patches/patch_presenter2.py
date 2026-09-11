#!/usr/bin/env python3
"""
Presenter empfaengt den dmabuf-Deskriptor per SCM_RIGHTS.

Ersetzt das gescheiterte Oeffnen ueber /proc/<pid>/fd/ durch eine
Verbindung zum Unix-Socket des Simulators.
"""

import sys

P = '/home/mersdk/harbour-fgview/src/harbour-fgview.cpp'

INC_OLD = '#include <cstring>'
INC_NEW = '''#include <cstring>
#include <sys/socket.h>
#include <sys/un.h>'''

OLD_FN_START = '''    /* Der Deskriptor gehoert dem Simulatorprozess; ueber procfs
       laesst er sich erneut oeffnen, solange beide demselben Benutzer
       gehoeren. */
    bool openDmabuf(quint32 pid, quint32 fd, size_t bytes)'''

NEW_FN = '''    /* Der Deskriptor kommt ueber einen Unix-Socket mit SCM_RIGHTS.
       Ueber /proc/<pid>/fd/ ginge es nicht: fuer anonyme Inodes wie
       dmabuf lehnt der Kernel das Wiederoeffnen mit ENXIO ab. */
    static int receiveFd(const char* path)
    {
        int s = ::socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0);
        if (s < 0) return -1;

        struct sockaddr_un addr;
        memset(&addr, 0, sizeof addr);
        addr.sun_family = AF_UNIX;
        strncpy(addr.sun_path, path, sizeof(addr.sun_path) - 1);

        if (::connect(s, (struct sockaddr*)&addr, sizeof addr) < 0) {
            ::close(s);
            return -1;
        }

        char dummy = 0;
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

        const ssize_t n = ::recvmsg(s, &msg, 0);
        int fd = -1;
        if (n > 0) {
            for (struct cmsghdr* cm = CMSG_FIRSTHDR(&msg); cm;
                 cm = CMSG_NXTHDR(&msg, cm)) {
                if (cm->cmsg_level == SOL_SOCKET &&
                    cm->cmsg_type == SCM_RIGHTS) {
                    memcpy(&fd, CMSG_DATA(cm), sizeof(int));
                    break;
                }
            }
        }
        ::close(s);
        return fd;
    }

    bool openDmabuf(quint32 pid, quint32 fd, size_t bytes)'''

BODY_OLD = '''        const QString path = QString("/proc/%1/fd/%2").arg(pid).arg(fd);
        int d = ::open(path.toUtf8().constData(), O_RDONLY | O_CLOEXEC);
        if (d < 0) {
            qWarning("FGVIEW: %s nicht zu oeffnen", qPrintable(path));
            return false;
        }
        void* p = ::mmap(nullptr, bytes, PROT_READ, MAP_SHARED, d, 0);
        ::close(d);'''

BODY_NEW = '''        const QByteArray sock =
            qEnvironmentVariableIsSet("FGFS_FD_SOCKET")
                ? qgetenv("FGFS_FD_SOCKET")
                : QByteArray("/tmp/fgfs-frame.sock");

        int d = receiveFd(sock.constData());
        if (d < 0) {
            qWarning("FGVIEW: kein Deskriptor ueber %s", sock.constData());
            return false;
        }
        void* p = ::mmap(nullptr, bytes, PROT_READ, MAP_SHARED, d, 0);
        ::close(d);'''


def main():
    try:
        s = open(P).read()
    except FileNotFoundError:
        print("nicht gefunden - im Container ausfuehren:", P)
        return 1

    if 'receiveFd' in s:
        print("bereits gepatcht")
        return 0

    for old, new, label in (
        (INC_OLD,      INC_NEW,  "Socket-Includes"),
        (OLD_FN_START, NEW_FN,   "receiveFd"),
        (BODY_OLD,     BODY_NEW, "Uebergabe statt procfs"),
    ):
        if old not in s:
            print("FEHLER: Muster nicht gefunden:", label)
            return 1
        s = s.replace(old, new, 1)
        print("gepatcht:", label)

    open(P, 'w').write(s)
    print("\nfertig - App neu bauen")
    return 0


if __name__ == '__main__':
    sys.exit(main())

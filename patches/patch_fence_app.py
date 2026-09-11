#!/usr/bin/env python3
"""
Presenter wartet auf den Fence.

Holt vor jedem Frame den aktuellen Fence-Deskriptor ueber den
Unix-Socket und wartet mit poll() darauf, dass die GPU fertig ist.
Das kostet den Presenter Zeit, nicht den Simulator - genau umgekehrt
zu glFinish.

Bleibt der Fence aus (alte Simulator-Version, fehlende Extension),
wird ohne Warten gelesen wie bisher.
"""

import sys

P = '/home/mersdk/harbour-fgview/src/harbour-fgview.cpp'

INC_OLD = '#include <sys/un.h>'
INC_NEW = '#include <sys/un.h>\n#include <poll.h>'

# receiveFd liefert jetzt auch den Typ mit
RECV_OLD = '''    static int receiveFd(const char* path)
    {'''
RECV_NEW = '''    /* kind: 'F' = dmabuf, 'S' = Fence. */
    static int receiveFd(const char* path, char* kind = nullptr)
    {'''

RECV_BODY_OLD = '''        const ssize_t n = ::recvmsg(s, &msg, 0);
        int fd = -1;
        if (n > 0) {'''
RECV_BODY_NEW = '''        const ssize_t n = ::recvmsg(s, &msg, 0);
        int fd = -1;
        if (n > 0 && kind) *kind = dummy;
        if (n > 0) {'''

# Warten vor dem Kopieren
WAIT_OLD = '''        /* Ein Durchgang statt 768 Einzelkopien.'''
WAIT_NEW = '''        /* Auf den Fence warten, falls der Simulator einen liefert.
           Das haelt uns auf, nicht den Simulator - dessen Pipeline
           bleibt gefuellt. */
        waitForFence();

        /* Ein Durchgang statt 768 Einzelkopien.'''

HELPER_OLD = '''    void closeDmabuf()'''
HELPER_NEW = '''    void waitForFence()
    {
        if (!_fenceAvailable) return;

        const QByteArray sock =
            qEnvironmentVariableIsSet("FGFS_FD_SOCKET")
                ? qgetenv("FGFS_FD_SOCKET")
                : QByteArray("/tmp/fgfs-frame.sock");

        char kind = 0;
        const int f = receiveFd(sock.constData(), &kind);
        if (f < 0 || kind != 'S') {
            if (f >= 0) ::close(f);
            _fenceMisses++;
            if (_fenceMisses > 30) {
                _fenceAvailable = false;   /* Simulator liefert keine */
                qWarning("FGVIEW: kein Fence, lese ungesynct");
            }
            return;
        }
        _fenceMisses = 0;

        struct pollfd pfd;
        pfd.fd = f;
        pfd.events = POLLIN;
        ::poll(&pfd, 1, 100);              /* hoechstens 100 ms */
        ::close(f);
    }

    void closeDmabuf()'''

MEM_OLD = '''    uchar*  _dmabuf = nullptr;'''
MEM_NEW = '''    uchar*  _dmabuf = nullptr;
    bool    _fenceAvailable = true;
    int     _fenceMisses = 0;'''


def main():
    try:
        s = open(P).read()
    except FileNotFoundError:
        print("nicht gefunden - im Container ausfuehren:", P)
        return 1

    if 'waitForFence' in s:
        print("bereits gepatcht")
        return 0

    for old, new, label in (
        (INC_OLD,        INC_NEW,        "poll.h"),
        (MEM_OLD,        MEM_NEW,        "Member"),
        (RECV_OLD,       RECV_NEW,       "receiveFd mit Typ"),
        (RECV_BODY_OLD,  RECV_BODY_NEW,  "Typ auslesen"),
        (HELPER_OLD,     HELPER_NEW,     "waitForFence"),
        (WAIT_OLD,       WAIT_NEW,       "Aufruf vor dem Kopieren"),
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

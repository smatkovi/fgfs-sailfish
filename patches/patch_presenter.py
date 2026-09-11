#!/usr/bin/env python3
"""
Presenter-Seite fuer Zero-Copy.

FrameItem liest bisher die Bilddaten aus dem Shared-Memory-Segment.
Steht im Header ein dmabuf-Verweis (dmabufPid != 0), oeffnet es
stattdessen /proc/<pid>/fd/<fd> und mappt den Puffer direkt - dieselben
Bytes, in die die GPU rendert, ohne Kopie und ohne Readback.

Der Fallback auf das Segment bleibt erhalten: laeuft fgfs ohne
dmabuf, aendert sich nichts.
"""

import sys

P = '/home/mersdk/harbour-fgview/src/harbour-fgview.cpp'

# ---- Header an die Simulator-Seite angleichen -----------------------
HDR_OLD = '''#pragma pack(push, 1)
struct FgFrameHeader {
    quint32 magic;
    quint32 width;
    quint32 height;
    quint32 bpp;
    quint64 sequence;
    quint32 activeSlot;
    quint32 reserved;
};
#pragma pack(pop)'''

HDR_NEW = '''#pragma pack(push, 1)
struct FgFrameHeader {
    quint32 magic;
    quint32 width;
    quint32 height;
    quint32 bpp;
    quint64 sequence;
    quint32 activeSlot;
    quint32 reserved;
    /* Zero-Copy: Verweis auf den dmabuf, in den die GPU rendert.
       dmabufPid == 0 bedeutet klassischer Readback. */
    quint32 dmabufPid;
    quint32 dmabufFd;
    quint32 dmabufStride;
    quint32 dmabufFourcc;
};
#pragma pack(pop)'''

SIZE_OLD = 'static const int     FGFR_HDR   = 32;'
SIZE_NEW = 'static const int     FGFR_HDR   = 48;'

# ---- poll(): dmabuf bevorzugen --------------------------------------
POLL_OLD = '''        const int w = int(hdr->width);
        const int h = int(hdr->height);
        const int slot = int(hdr->activeSlot);
        const size_t bytes = size_t(w) * size_t(h) * 4u;

        if (_image.width() != w || _image.height() != h)
            _image = QImage(w, h, QImage::Format_RGBA8888);

        const uchar* src = _base + FGFR_HDR + size_t(slot) * bytes;'''

POLL_NEW = '''        const int w = int(hdr->width);
        const int h = int(hdr->height);
        const int slot = int(hdr->activeSlot);
        const size_t bytes = size_t(w) * size_t(h) * 4u;

        if (_image.width() != w || _image.height() != h)
            _image = QImage(w, h, QImage::Format_RGBA8888);

        /* Zero-Copy: der Simulator rendert direkt in einen dmabuf,
           den wir ueber /proc/<pid>/fd/<fd> oeffnen und mappen. */
        const uchar* src = nullptr;
        if (hdr->dmabufPid != 0) {
            if (!_dmabuf && !openDmabuf(hdr->dmabufPid, hdr->dmabufFd, bytes))
                return;                      /* nicht erreichbar */
            src = _dmabuf;
        } else {
            src = _base + FGFR_HDR + size_t(slot) * bytes;
        }'''

# ---- Mapping-Helfer -------------------------------------------------
HELPER_OLD = '''    bool openShm()'''
HELPER_NEW = '''    /* Der Deskriptor gehoert dem Simulatorprozess; ueber procfs
       laesst er sich erneut oeffnen, solange beide demselben Benutzer
       gehoeren. */
    bool openDmabuf(quint32 pid, quint32 fd, size_t bytes)
    {
        if (_dmabufTried == QPair<quint32,quint32>(pid, fd))
            return _dmabuf != nullptr;
        _dmabufTried = QPair<quint32,quint32>(pid, fd);

        closeDmabuf();

        const QString path = QString("/proc/%1/fd/%2").arg(pid).arg(fd);
        int d = ::open(path.toUtf8().constData(), O_RDONLY | O_CLOEXEC);
        if (d < 0) {
            qWarning("FGVIEW: %s nicht zu oeffnen", qPrintable(path));
            return false;
        }
        void* p = ::mmap(nullptr, bytes, PROT_READ, MAP_SHARED, d, 0);
        ::close(d);
        if (p == MAP_FAILED) {
            qWarning("FGVIEW: mmap des dmabuf fehlgeschlagen");
            return false;
        }
        _dmabuf = static_cast<uchar*>(p);
        _dmabufBytes = bytes;
        qWarning("FGVIEW: Zero-Copy aktiv, %zu KiB gemappt", bytes / 1024);
        return true;
    }

    void closeDmabuf()
    {
        if (_dmabuf) { ::munmap(_dmabuf, _dmabufBytes); _dmabuf = nullptr; }
        _dmabufBytes = 0;
    }

    bool openShm()'''

CLOSE_OLD = '''    void closeShm()
    {
        if (_base) { ::munmap(_base, _mapped); _base = nullptr; }'''
CLOSE_NEW = '''    void closeShm()
    {
        closeDmabuf();
        if (_base) { ::munmap(_base, _mapped); _base = nullptr; }'''

MEM_OLD = '''    uchar*  _base = nullptr;
    size_t  _mapped = 0;'''
MEM_NEW = '''    uchar*  _base = nullptr;
    size_t  _mapped = 0;
    uchar*  _dmabuf = nullptr;
    size_t  _dmabufBytes = 0;
    QPair<quint32,quint32> _dmabufTried = qMakePair(0u, 0u);'''


def main():
    try:
        s = open(P).read()
    except FileNotFoundError:
        print("nicht gefunden - im Container ausfuehren:", P)
        return 1

    if 'openDmabuf' in s:
        print("bereits gepatcht")
        return 0

    steps = (
        (HDR_OLD,    HDR_NEW,    "Header erweitert"),
        (SIZE_OLD,   SIZE_NEW,   "Headergroesse 48"),
        (MEM_OLD,    MEM_NEW,    "Member"),
        (HELPER_OLD, HELPER_NEW, "openDmabuf/closeDmabuf"),
        (POLL_OLD,   POLL_NEW,   "poll bevorzugt dmabuf"),
        (CLOSE_OLD,  CLOSE_NEW,  "Aufraeumen"),
    )

    for old, new, label in steps:
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

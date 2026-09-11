#!/usr/bin/env python3
"""
Ersetzt den PPM-Dump in GraphicsWindowEGL durch einen shm-Transport.

Layout von /dev/shm/fgfs-frame:

    offset 0   uint32  magic   'FGFR' = 0x46474652
    offset 4   uint32  width
    offset 8   uint32  height
    offset 12  uint32  bytesPerPixel (immer 4, RGBA)
    offset 16  uint64  sequence   (ungerade = Schreibvorgang laeuft)
    offset 24  uint32  activeSlot (0 oder 1)
    offset 28  uint32  reserved
    offset 32  slot 0  w*h*4 bytes
    offset 32+ slot 1  w*h*4 bytes

Der Leser prueft sequence vor und nach dem Kopieren; sind beide Werte
gleich und gerade, war der Frame konsistent (seqlock).

Steuerung:
    FGFS_SHM_NAME  Default /fgfs-frame
    FGFS_SHM       1 = an (Default aus)
"""

import sys

P = '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5/src/osgViewer/GraphicsWindowEGL.cpp'

INC_OLD = '''#include <cstdio>
#include <vector>'''

INC_NEW = '''#include <cstdio>
#include <vector>
#include <string>
#include <atomic>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/stat.h>'''


SHM_HELPER = '''
/* ------------------------------------------------------------------ *
 *  Shared-Memory-Transport fuer den Presenter
 * ------------------------------------------------------------------ */
namespace {

struct FgFrameHeader {
    uint32_t magic;
    uint32_t width;
    uint32_t height;
    uint32_t bpp;
    uint64_t sequence;
    uint32_t activeSlot;
    uint32_t reserved;
};

static const uint32_t FGFR_MAGIC = 0x46474652u;   /* 'FGFR' */
static const size_t   FGFR_HDR   = 32;

class ShmFrameWriter
{
public:
    bool open(int w, int h)
    {
        if (_base) return true;

        const char* nm = ::getenv("FGFS_SHM_NAME");
        _name = (nm && *nm) ? nm : "/fgfs-frame";

        _w = w; _h = h;
        _slotBytes = size_t(w) * size_t(h) * 4u;
        _total = FGFR_HDR + 2 * _slotBytes;

        int fd = ::shm_open(_name.c_str(), O_CREAT | O_RDWR, 0666);
        if (fd < 0) {
            OSG_WARN << "ShmFrameWriter: shm_open('" << _name
                     << "') fehlgeschlagen" << std::endl;
            return false;
        }
        if (::ftruncate(fd, off_t(_total)) != 0) {
            OSG_WARN << "ShmFrameWriter: ftruncate fehlgeschlagen" << std::endl;
            ::close(fd);
            return false;
        }
        void* p = ::mmap(nullptr, _total, PROT_READ | PROT_WRITE,
                         MAP_SHARED, fd, 0);
        ::close(fd);
        if (p == MAP_FAILED) {
            OSG_WARN << "ShmFrameWriter: mmap fehlgeschlagen" << std::endl;
            return false;
        }

        _base = static_cast<unsigned char*>(p);
        FgFrameHeader* hdr = reinterpret_cast<FgFrameHeader*>(_base);
        hdr->magic      = FGFR_MAGIC;
        hdr->width      = uint32_t(w);
        hdr->height     = uint32_t(h);
        hdr->bpp        = 4;
        hdr->sequence   = 0;
        hdr->activeSlot = 0;
        hdr->reserved   = 0;

        OSG_NOTICE << "ShmFrameWriter: " << _name << " bereit, "
                   << w << "x" << h << ", " << (_total / 1024) << " KiB"
                   << std::endl;
        return true;
    }

    unsigned char* slotPtr(int slot)
    {
        return _base + FGFR_HDR + size_t(slot) * _slotBytes;
    }

    /* seqlock: ungerade waehrend des Schreibens */
    void beginWrite(int slot)
    {
        FgFrameHeader* hdr = reinterpret_cast<FgFrameHeader*>(_base);
        __atomic_add_fetch(&hdr->sequence, 1, __ATOMIC_ACQ_REL);
        (void)slot;
    }

    void endWrite(int slot)
    {
        FgFrameHeader* hdr = reinterpret_cast<FgFrameHeader*>(_base);
        hdr->activeSlot = uint32_t(slot);
        __atomic_add_fetch(&hdr->sequence, 1, __ATOMIC_ACQ_REL);
    }

    bool ready() const { return _base != nullptr; }
    size_t slotBytes() const { return _slotBytes; }

    void close()
    {
        if (_base) {
            ::munmap(_base, _total);
            _base = nullptr;
        }
    }

private:
    unsigned char* _base = nullptr;
    std::string _name;
    size_t _slotBytes = 0;
    size_t _total = 0;
    int _w = 0, _h = 0;
};

ShmFrameWriter g_shm;

} // anonymous namespace
'''


DUMP_OLD_HEAD = '    void dumpFrameIfRequested()\n    {'

DUMP_NEW = '''    void publishToShm()
    {
        static int enabled = -1;
        if (enabled < 0) {
            const char* e = ::getenv("FGFS_SHM");
            enabled = (e && *e && *e != '0') ? 1 : 0;
        }
        if (!enabled) return;

        const int w = _traits.valid() ? _traits->width  : 1024;
        const int h = _traits.valid() ? _traits->height : 768;

        if (!g_shm.ready() && !g_shm.open(w, h)) {
            enabled = 0;
            return;
        }

        const int slot = int(_frameCount & 1u);
        ++_frameCount;

        glPixelStorei(GL_PACK_ALIGNMENT, 1);

        g_shm.beginWrite(slot);
        glReadPixels(0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE,
                     g_shm.slotPtr(slot));
        g_shm.endWrite(slot);
    }

    void dumpFrameIfRequested()
    {'''


SWAP_OLD = '''        dumpFrameIfRequested();
    }'''

SWAP_NEW = '''        publishToShm();
        dumpFrameIfRequested();
    }'''


def main():
    try:
        s = open(P).read()
    except FileNotFoundError:
        print("Datei nicht gefunden - im Container ausfuehren:", P)
        return 1

    if 'ShmFrameWriter' in s:
        print("bereits gepatcht")
        return 0

    if INC_OLD not in s:
        print("FEHLER: Include-Block nicht gefunden")
        return 1
    s = s.replace(INC_OLD, INC_NEW, 1)
    print("gepatcht: Includes")

    marker = 'namespace osgViewer {'
    if marker not in s:
        print("FEHLER: namespace osgViewer nicht gefunden")
        return 1
    s = s.replace(marker, SHM_HELPER + '\n' + marker, 1)
    print("gepatcht: ShmFrameWriter eingefuegt")

    if DUMP_OLD_HEAD not in s:
        print("FEHLER: dumpFrameIfRequested nicht gefunden")
        return 1
    s = s.replace(DUMP_OLD_HEAD, DUMP_NEW, 1)
    print("gepatcht: publishToShm")

    if SWAP_OLD not in s:
        print("FEHLER: swapBuffers-Aufrufstelle nicht gefunden")
        return 1
    s = s.replace(SWAP_OLD, SWAP_NEW, 1)
    print("gepatcht: Aufruf in swapBuffersImplementation")

    open(P, 'w').write(s)
    print("fertig")
    return 0


if __name__ == '__main__':
    sys.exit(main())

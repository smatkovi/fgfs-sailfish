#!/usr/bin/env python3
"""
Zero-Copy fuer GraphicsWindowEGL.

Statt die FBO-Farbtextur mit glTexImage2D anzulegen und danach per
glReadPixels auszulesen, wird ein dmabuf vom Kernel-Heap alloziert,
per EGL_EXT_image_dma_buf_import als Textur importiert und ans FBO
gehaengt. Die GPU rendert dann direkt in Speicher, den ein zweiter
Prozess ohne Kopie lesen kann.

Der Shared-Memory-Bereich enthaelt danach nur noch Metadaten: PID
und Deskriptornummer, ueber die der Presenter den Puffer per
/proc/<pid>/fd/<n> oeffnet.

Faellt irgendein Schritt aus, bleibt der bisherige Readback aktiv -
die Datei behaelt beide Pfade.
"""

import sys

P = '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5/src/osgViewer/GraphicsWindowEGL.cpp'

# ---- Includes und Konstanten ---------------------------------------
INC_OLD = '#include <sys/stat.h>'
INC_NEW = '''#include <sys/stat.h>
#include <sys/ioctl.h>
#include <linux/types.h>

/* dma-heap: der Kernel alloziert, beide Seiten importieren.
   Der Mali-Treiber meldet exportable=0, importable=1 - deshalb
   dieser Umweg statt eines Exports aus Vulkan heraus. */
struct dma_heap_allocation_data {
    __u64 len;
    __u32 fd;
    __u32 fd_flags;
    __u64 heap_flags;
};
#ifndef DMA_HEAP_IOCTL_ALLOC
#define DMA_HEAP_IOCTL_ALLOC _IOWR('H', 0, struct dma_heap_allocation_data)
#endif'''

# ---- Header des Shared-Memory-Bereichs erweitern -------------------
HDR_OLD = '''struct FgFrameHeader {
    uint32_t magic;
    uint32_t width;
    uint32_t height;
    uint32_t bpp;
    uint64_t sequence;
    uint32_t activeSlot;
    uint32_t reserved;
};'''

HDR_NEW = '''struct FgFrameHeader {
    uint32_t magic;
    uint32_t width;
    uint32_t height;
    uint32_t bpp;
    uint64_t sequence;
    uint32_t activeSlot;
    uint32_t reserved;
    /* Zero-Copy: statt Bilddaten nur der Verweis auf den dmabuf.
       Der Presenter oeffnet ihn ueber /proc/<pid>/fd/<fd>. */
    uint32_t dmabufPid;      /* 0 = kein dmabuf, klassischer Readback */
    uint32_t dmabufFd;
    uint32_t dmabufStride;
    uint32_t dmabufFourcc;
};'''

# ---- Allokation und Import statt glTexImage2D ----------------------
TEX_OLD = '''        p_GenTextures(1, &_texColor);
        p_BindTexture(GL_TEXTURE_2D, _texColor);
        p_TexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, w, h, 0,
                     GL_RGBA, GL_UNSIGNED_BYTE, nullptr);'''

TEX_NEW = '''        p_GenTextures(1, &_texColor);
        p_BindTexture(GL_TEXTURE_2D, _texColor);

        /* Erst den geteilten Weg versuchen: Puffer vom Kernel-Heap,
           als EGLImage importiert. Klappt das, rendert die GPU direkt
           in Speicher, den der Presenter ohne Kopie liest. */
        _dmabufFd = allocDmaHeap(size_t(w) * size_t(h) * 4u);
        bool shared = false;

        if (_dmabufFd >= 0) {
            PFNEGLCREATEIMAGEKHRPROC CreateImage =
                (PFNEGLCREATEIMAGEKHRPROC)eglGetProcAddress("eglCreateImageKHR");
            typedef void (*PFN_ImgTarget)(unsigned, void*);
            PFN_ImgTarget ImgTarget =
                (PFN_ImgTarget)eglGetProcAddress("glEGLImageTargetTexture2DOES");

            if (CreateImage && ImgTarget) {
                const EGLint iattr[] = {
                    EGL_WIDTH,  w,
                    EGL_HEIGHT, h,
                    EGL_LINUX_DRM_FOURCC_EXT, 0x34324241,   /* AB24 */
                    EGL_DMA_BUF_PLANE0_FD_EXT,     _dmabufFd,
                    EGL_DMA_BUF_PLANE0_OFFSET_EXT, 0,
                    EGL_DMA_BUF_PLANE0_PITCH_EXT,  w * 4,
                    EGL_DMA_BUF_PLANE0_MODIFIER_LO_EXT, 0,  /* LINEAR */
                    EGL_DMA_BUF_PLANE0_MODIFIER_HI_EXT, 0,
                    EGL_NONE
                };
                _dmabufImage = CreateImage(_display, EGL_NO_CONTEXT,
                                           EGL_LINUX_DMA_BUF_EXT,
                                           nullptr, iattr);
                if (_dmabufImage != EGL_NO_IMAGE_KHR) {
                    ImgTarget(GL_TEXTURE_2D, _dmabufImage);
                    shared = true;
                    OSG_WARN << "GraphicsWindowEGL: Zero-Copy aktiv, dmabuf fd="
                             << _dmabufFd << " pid=" << getpid()
                             << " stride=" << (w * 4) << std::endl;
                } else {
                    OSG_WARN << "GraphicsWindowEGL: dmabuf-Import fehlgeschlagen 0x"
                             << std::hex << eglGetError() << std::dec
                             << ", falle auf Readback zurueck" << std::endl;
                }
            }
        }

        if (!shared) {
            if (_dmabufFd >= 0) { ::close(_dmabufFd); _dmabufFd = -1; }
            p_TexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, w, h, 0,
                         GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
        }'''

# ---- Hilfsfunktion -------------------------------------------------
HELPER_ANCHOR = '    void init()\n    {'
HELPER_NEW = '''    /* Puffer vom Kernel-Heap. Lesezugriff auf das Geraet genuegt,
       die ioctl braucht kein O_RDWR. */
    static int allocDmaHeap(size_t len)
    {
        const char* dev = ::getenv("FGFS_DMA_HEAP");
        if (!dev || !*dev) dev = "/dev/dma_heap/system";

        int h = ::open(dev, O_RDWR | O_CLOEXEC);
        if (h < 0) h = ::open(dev, O_RDONLY | O_CLOEXEC);
        if (h < 0) {
            OSG_WARN << "GraphicsWindowEGL: " << dev
                     << " nicht verfuegbar" << std::endl;
            return -1;
        }

        struct dma_heap_allocation_data d;
        memset(&d, 0, sizeof d);
        d.len = len;
        d.fd_flags = O_RDWR | O_CLOEXEC;

        if (::ioctl(h, DMA_HEAP_IOCTL_ALLOC, &d) < 0) {
            OSG_WARN << "GraphicsWindowEGL: dma-heap alloc fehlgeschlagen"
                     << std::endl;
            ::close(h);
            return -1;
        }
        ::close(h);
        return int(d.fd);
    }

    void init()
    {'''

# ---- publishToShm: nur noch Metadaten ------------------------------
PUB_ANCHOR = '''        const size_t bytes = size_t(w) * size_t(h) * 4u;'''
PUB_NEW = '''        /* Zero-Copy: die GPU hat bereits in den geteilten Puffer
           gerendert. Es bleibt nur, den Frame als fertig zu melden. */
        if (_dmabufFd >= 0) {
            if (!g_shm.ready() && !g_shm.open(w, h)) return;
            glFinish();
            g_shm.publishDmabuf(getpid(), _dmabufFd, w * 4, 0x34324241);
            ++_frameCount;
            return;
        }

        const size_t bytes = size_t(w) * size_t(h) * 4u;'''

# ---- ShmFrameWriter erweitern --------------------------------------
SHM_OLD = '''    bool ready() const { return _base != nullptr; }'''
SHM_NEW = '''    /* Beim Zero-Copy stehen im Segment nur Metadaten. Die
       Sequenznummer bleibt als Fertig-Signal erhalten. */
    void publishDmabuf(int pid, int fd, uint32_t stride, uint32_t fourcc)
    {
        FgFrameHeader* hdr = reinterpret_cast<FgFrameHeader*>(_base);
        __atomic_add_fetch(&hdr->sequence, 1, __ATOMIC_ACQ_REL);
        hdr->dmabufPid    = uint32_t(pid);
        hdr->dmabufFd     = uint32_t(fd);
        hdr->dmabufStride = stride;
        hdr->dmabufFourcc = fourcc;
        __atomic_add_fetch(&hdr->sequence, 1, __ATOMIC_ACQ_REL);
    }

    bool ready() const { return _base != nullptr; }'''

# beim Zero-Copy reicht ein winziges Segment
OPEN_OLD = '''        _slotBytes = size_t(w) * size_t(h) * 4u;
        _total = FGFR_HDR + 2 * _slotBytes;'''
OPEN_NEW = '''        _slotBytes = size_t(w) * size_t(h) * 4u;
        /* Auch beim Zero-Copy die volle Groesse anlegen: faellt der
           Import spaeter aus, ist der Readback-Pfad sofort nutzbar. */
        _total = FGFR_HDR + 2 * _slotBytes;'''

HDRINIT_OLD = '''        hdr->reserved   = 0;'''
HDRINIT_NEW = '''        hdr->reserved   = 0;
        hdr->dmabufPid  = 0;
        hdr->dmabufFd   = 0;
        hdr->dmabufStride = 0;
        hdr->dmabufFourcc = 0;'''

MEM_OLD = '''    unsigned _texColor = 0;'''
MEM_NEW = '''    unsigned _texColor = 0;
    int _dmabufFd = -1;
    EGLImageKHR _dmabufImage = EGL_NO_IMAGE_KHR;'''

# Headergroesse anpassen (4 neue uint32 = 16 bytes)
SIZE_OLD = 'static const size_t   FGFR_HDR   = 32;'
SIZE_NEW = 'static const size_t   FGFR_HDR   = 48;'


def main():
    try:
        s = open(P).read()
    except FileNotFoundError:
        print("nicht gefunden - im Container ausfuehren:", P)
        return 1

    if '_dmabufImage' in s:
        print("bereits gepatcht")
        return 0

    steps = (
        (INC_OLD,       INC_NEW,       "Includes und dma-heap-ioctl"),
        (HDR_OLD,       HDR_NEW,       "Header erweitert"),
        (SIZE_OLD,      SIZE_NEW,      "Headergroesse 48"),
        (HDRINIT_OLD,   HDRINIT_NEW,   "Header-Initialisierung"),
        (SHM_OLD,       SHM_NEW,       "publishDmabuf"),
        (OPEN_OLD,      OPEN_NEW,      "Kommentar zur Segmentgroesse"),
        (MEM_OLD,       MEM_NEW,       "Member"),
        (HELPER_ANCHOR, HELPER_NEW,    "allocDmaHeap"),
        (TEX_OLD,       TEX_NEW,       "Textur aus dmabuf"),
        (PUB_ANCHOR,    PUB_NEW,       "publishToShm ohne Readback"),
    )

    for old, new, label in steps:
        if old not in s:
            print("FEHLER: Muster nicht gefunden:", label)
            return 1
        s = s.replace(old, new, 1)
        print("gepatcht:", label)

    open(P, 'w').write(s)
    print("\nfertig. OSG neu bauen, dann Laufzeitpaket.")
    print("Abschalten zur Laufzeit: FGFS_DMA_HEAP=/dev/null")
    return 0


if __name__ == '__main__':
    sys.exit(main())

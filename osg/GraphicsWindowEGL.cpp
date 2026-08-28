/* GraphicsWindowEGL.cpp
 *
 * Offscreen-GraphicsWindow fuer OpenSceneGraph 3.6.5 auf EGL.
 * Zielplattform: SailfishOS / libhybris / Mesa-Zink (Desktop-GL ueber Vulkan).
 *
 * Rendert in ein Pbuffer bzw. FBO; die Praesentation uebernimmt ein
 * separater Prozess (Readback in Shared Memory -> Silica-App).
 *
 * Ablage: src/osgViewer/GraphicsWindowEGL.cpp
 */

#include <osgViewer/GraphicsWindow>
#include <osg/GraphicsContext>
#include <osg/Notify>

#include <EGL/egl.h>
#include <EGL/eglext.h>

#include <cstdlib>
#include <cstring>
#include <cstdio>
#include <vector>
#include <string>
#include <atomic>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/ioctl.h>
#include <linux/types.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <pthread.h>

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
#endif

/* GL-Konstanten und -Prototypen ohne GL/gl.h, damit wir nicht gegen
   glvnd-Header linken muessen - die Symbole kommen aus libOpenGL. */
#ifndef GL_RGBA
#define GL_RGBA           0x1908
#define GL_UNSIGNED_BYTE  0x1401
#define GL_PACK_ALIGNMENT 0x0D05
#endif
/* Unter GLES2 fehlen einige Desktop-Konstanten; die Zahlenwerte
   sind identisch. */
#ifndef GL_DEPTH24_STENCIL8
#define GL_DEPTH24_STENCIL8         0x88F0
#endif
#ifndef GL_DEPTH_STENCIL_ATTACHMENT
#define GL_DEPTH_STENCIL_ATTACHMENT 0x821A
#endif
#ifndef GL_READ_ONLY
#define GL_READ_ONLY                0x88B8
#endif

#ifndef GL_TEXTURE_2D
#define GL_TEXTURE_2D               0x0DE1
#define GL_TEXTURE_MIN_FILTER       0x2801
#define GL_TEXTURE_MAG_FILTER       0x2800
#define GL_NEAREST                  0x2600
#define GL_CLAMP_TO_EDGE            0x812F
#define GL_TEXTURE_WRAP_S           0x2802
#define GL_TEXTURE_WRAP_T           0x2803
#endif

#ifndef GL_PIXEL_PACK_BUFFER
#define GL_PIXEL_PACK_BUFFER        0x88EB
#define GL_STREAM_READ              0x88E1
#define GL_READ_ONLY                0x88B8
#endif

#ifndef GL_FRAMEBUFFER
#define GL_FRAMEBUFFER              0x8D40
#define GL_RENDERBUFFER             0x8D41
#define GL_COLOR_ATTACHMENT0        0x8CE0
#define GL_DEPTH24_STENCIL8         0x88F0
#define GL_DEPTH_STENCIL_ATTACHMENT 0x821A
#define GL_RGBA8                    0x8058
#define GL_FRAMEBUFFER_COMPLETE     0x8CD5
#endif

extern "C" {
    void glReadPixels(int, int, int, int, unsigned, unsigned, void*);
    void glPixelStorei(unsigned, int);
    void glFinish(void);
    void glViewport(int, int, int, int);
}

namespace {
    typedef void (*PFN_v_ip)(int, unsigned*);
    typedef void (*PFN_v_uu)(unsigned, unsigned);
    typedef void (*PFN_v_uuii)(unsigned, unsigned, int, int);
    typedef void (*PFN_v_uuuu)(unsigned, unsigned, unsigned, unsigned);
    typedef unsigned (*PFN_u_u)(unsigned);
    typedef void (*PFN_v_icp)(int, const unsigned*);

    PFN_v_ip    p_GenFramebuffers = nullptr;
    PFN_v_uu    p_BindFramebuffer = nullptr;
    PFN_v_ip    p_GenRenderbuffers = nullptr;
    PFN_v_uu    p_BindRenderbuffer = nullptr;
    PFN_v_uuii  p_RenderbufferStorage = nullptr;
    PFN_v_uuuu  p_FramebufferRenderbuffer = nullptr;
    PFN_u_u     p_CheckFramebufferStatus = nullptr;
    PFN_v_icp   p_DeleteFramebuffers = nullptr;
    PFN_v_icp   p_DeleteRenderbuffers = nullptr;

    typedef void  (*PFN_v_ip2)(int, unsigned*);
    typedef void  (*PFN_v_uu2)(unsigned, unsigned);
    typedef void  (*PFN_v_uxpu)(unsigned, long, const void*, unsigned);
    typedef void* (*PFN_p_uu)(unsigned, unsigned);
    typedef unsigned char (*PFN_b_u)(unsigned);

    PFN_v_ip2   p_GenBuffers = nullptr;
    PFN_v_uu2   p_BindBuffer = nullptr;
    PFN_v_uxpu  p_BufferData = nullptr;
    PFN_p_uu    p_MapBuffer = nullptr;
    PFN_b_u     p_UnmapBuffer = nullptr;
    PFN_v_icp   p_DeleteBuffers = nullptr;

    typedef void (*PFN_tex_img)(unsigned, int, int, int, int, int,
                                unsigned, unsigned, const void*);
    typedef void (*PFN_tex_par)(unsigned, unsigned, int);
    typedef void (*PFN_fb_tex)(unsigned, unsigned, unsigned, unsigned, int);

    PFN_v_ip     p_GenTextures = nullptr;
    PFN_v_uu     p_BindTexture = nullptr;
    PFN_tex_img  p_TexImage2D = nullptr;
    PFN_tex_par  p_TexParameteri = nullptr;
    PFN_fb_tex   p_FramebufferTexture2D = nullptr;
    PFN_v_icp    p_DeleteTextures = nullptr;

    bool loadTexEntryPoints()
    {
        if (p_GenTextures) return true;
        p_GenTextures   = (PFN_v_ip)    eglGetProcAddress("glGenTextures");
        p_BindTexture   = (PFN_v_uu)    eglGetProcAddress("glBindTexture");
        p_TexImage2D    = (PFN_tex_img) eglGetProcAddress("glTexImage2D");
        p_TexParameteri = (PFN_tex_par) eglGetProcAddress("glTexParameteri");
        p_FramebufferTexture2D =
            (PFN_fb_tex) eglGetProcAddress("glFramebufferTexture2D");
        p_DeleteTextures = (PFN_v_icp)  eglGetProcAddress("glDeleteTextures");
        return p_GenTextures && p_BindTexture && p_TexImage2D
            && p_TexParameteri && p_FramebufferTexture2D;
    }

    bool loadPboEntryPoints()
    {
        if (p_GenBuffers) return true;
        p_GenBuffers    = (PFN_v_ip2) eglGetProcAddress("glGenBuffers");
        p_BindBuffer    = (PFN_v_uu2) eglGetProcAddress("glBindBuffer");
        p_BufferData    = (PFN_v_uxpu)eglGetProcAddress("glBufferData");
        p_MapBuffer     = (PFN_p_uu)  eglGetProcAddress("glMapBuffer");
        p_UnmapBuffer   = (PFN_b_u)   eglGetProcAddress("glUnmapBuffer");
        p_DeleteBuffers = (PFN_v_icp) eglGetProcAddress("glDeleteBuffers");
        return p_GenBuffers && p_BindBuffer && p_BufferData
            && p_MapBuffer && p_UnmapBuffer;
    }

    bool loadFboEntryPoints()
    {
        if (p_GenFramebuffers) return true;
        p_GenFramebuffers        = (PFN_v_ip)  eglGetProcAddress("glGenFramebuffers");
        p_BindFramebuffer        = (PFN_v_uu)  eglGetProcAddress("glBindFramebuffer");
        p_GenRenderbuffers       = (PFN_v_ip)  eglGetProcAddress("glGenRenderbuffers");
        p_BindRenderbuffer       = (PFN_v_uu)  eglGetProcAddress("glBindRenderbuffer");
        p_RenderbufferStorage    = (PFN_v_uuii)eglGetProcAddress("glRenderbufferStorage");
        p_FramebufferRenderbuffer= (PFN_v_uuuu)eglGetProcAddress("glFramebufferRenderbuffer");
        p_CheckFramebufferStatus = (PFN_u_u)   eglGetProcAddress("glCheckFramebufferStatus");
        p_DeleteFramebuffers     = (PFN_v_icp) eglGetProcAddress("glDeleteFramebuffers");
        p_DeleteRenderbuffers    = (PFN_v_icp) eglGetProcAddress("glDeleteRenderbuffers");
        return p_GenFramebuffers && p_BindFramebuffer && p_GenRenderbuffers &&
               p_BindRenderbuffer && p_RenderbufferStorage &&
               p_FramebufferRenderbuffer && p_CheckFramebufferStatus;
    }
}


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
    /* Zero-Copy: statt Bilddaten nur der Verweis auf den dmabuf.
       Der Presenter oeffnet ihn ueber /proc/<pid>/fd/<fd>. */
    uint32_t dmabufPid;      /* 0 = kein dmabuf, klassischer Readback */
    uint32_t dmabufFd;
    uint32_t dmabufStride;
    uint32_t dmabufFourcc;
};

static const uint32_t FGFR_MAGIC = 0x46474652u;   /* 'FGFR' */
static const size_t   FGFR_HDR   = 48;

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
        /* Auch beim Zero-Copy die volle Groesse anlegen: faellt der
           Import spaeter aus, ist der Readback-Pfad sofort nutzbar. */
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
        hdr->dmabufPid  = 0;
        hdr->dmabufFd   = 0;
        hdr->dmabufStride = 0;
        hdr->dmabufFourcc = 0;

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

    /* Beim Zero-Copy stehen im Segment nur Metadaten. Die
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
    int fenceFd = -1;
    bool handedOutBuffer = false;
    pthread_mutex_t fenceLock = PTHREAD_MUTEX_INITIALIZER;
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

    /* Der Fence wechselt pro Frame. Der jeweils juengste wird
       vorgehalten; der vorige wird geschlossen. */
    void setFence(int fd)
    {
        pthread_mutex_lock(&fenceLock);
        if (fenceFd >= 0) ::close(fenceFd);
        fenceFd = fd;
        pthread_mutex_unlock(&fenceLock);
    }

    int takeFence()
    {
        pthread_mutex_lock(&fenceLock);
        const int fd = fenceFd;
        fenceFd = -1;
        pthread_mutex_unlock(&fenceLock);
        return fd;
    }

    void sendFd(int conn)
    {
        char dummy = 'F';
        struct iovec iov;
        iov.iov_base = &dummy;
        iov.iov_len = 1;

        /* Erste Anfrage bekommt den dmabuf, jede weitere den
           aktuellen Fence. Der Presenter unterscheidet am Byte. */
        int fence = takeFence();
        int toSend = payloadFd;
        if (handedOutBuffer && fence >= 0) {
            toSend = fence;
            dummy = 'S';                /* Sync statt Buffer */
        } else {
            handedOutBuffer = true;
        }

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
        memcpy(CMSG_DATA(cm), &toSend, sizeof(int));

        if (::sendmsg(conn, &msg, 0) < 0)
            OSG_WARN << "FdServer: sendmsg fehlgeschlagen" << std::endl;

        if (toSend == fence) ::close(fence);
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

/* Desktop-GL oder GLES2 - der Rest des Codes ist identisch. */
#if defined(OSG_GLES2_AVAILABLE) || defined(OSG_GLES3_AVAILABLE)
#  define FGFS_EGL_API        EGL_OPENGL_ES_API
#  define FGFS_EGL_RENDERABLE EGL_OPENGL_ES2_BIT
#  define FGFS_EGL_CTX_ATTR   EGL_CONTEXT_CLIENT_VERSION
#  define FGFS_EGL_CTX_VER    2
#else
#  define FGFS_EGL_API        EGL_OPENGL_API
#  define FGFS_EGL_RENDERABLE EGL_OPENGL_BIT
#  define FGFS_EGL_CTX_ATTR   EGL_CONTEXT_MAJOR_VERSION
#  define FGFS_EGL_CTX_VER    3
#endif

namespace osgViewer {

class GraphicsWindowEGL : public osgViewer::GraphicsWindow
{
public:
    explicit GraphicsWindowEGL(osg::GraphicsContext::Traits* traits)
        : _display(EGL_NO_DISPLAY)
        , _surface(EGL_NO_SURFACE)
        , _context(EGL_NO_CONTEXT)
        , _config(nullptr)
        , _valid(false)
        , _realized(false)
        , _initialized(false)
    {
        _traits = traits;
        init();
        if (valid()) {
            setState(new osg::State);
            getState()->setGraphicsContext(this);
            if (_traits.valid() && _traits->sharedContext.valid()) {
                getState()->setContextID(
                    _traits->sharedContext->getState()->getContextID());
                incrementContextIDUsageCount(getState()->getContextID());
            } else {
                getState()->setContextID(osg::GraphicsContext::createNewContextID());
            }
        }
    }

    // ---- osg::GraphicsContext ----------------------------------------

    bool valid() const override { return _valid; }

    bool realizeImplementation() override
    {
        if (_realized) return true;
        if (!_initialized) init();
        if (!_valid) return false;

        const EGLint w = _traits.valid() ? _traits->width  : 960;
        const EGLint h = _traits.valid() ? _traits->height : 540;

        const EGLint pbAttr[] = {
            EGL_WIDTH,  w,
            EGL_HEIGHT, h,
            EGL_NONE
        };

        /* Der Mali-Blob bietet kein EGL_KHR_surfaceless_context;
           eglMakeCurrent mit EGL_NO_SURFACE stuerzt dort ab. Eine
           Pbuffer-Surface gibt dem Kontext ein Ziel - gerendert wird
           trotzdem ins FBO. Unter Mesa/Zink funktioniert beides. */
        _surface = eglCreatePbufferSurface(_display, _config, pbAttr);
        if (_surface == EGL_NO_SURFACE) {
            OSG_WARN << "GraphicsWindowEGL: kein Pbuffer (0x"
                     << std::hex << eglGetError() << std::dec
                     << "), versuche surfaceless" << std::endl;
        } else {
            OSG_WARN << "GraphicsWindowEGL: Pbuffer " << w << "x" << h
                     << " als Kontextziel" << std::endl;
        }

        if (!eglMakeCurrent(_display, _surface, _surface, _context)) {
            OSG_WARN << "GraphicsWindowEGL: makeCurrent fuer FBO-Setup fehlgeschlagen 0x"
                     << std::hex << eglGetError() << std::dec << std::endl;
            return false;
        }
        if (!loadFboEntryPoints()) {
            OSG_WARN << "GraphicsWindowEGL: FBO-Einsprungpunkte fehlen" << std::endl;
            return false;
        }

        p_GenFramebuffers(1, &_fbo);
        p_BindFramebuffer(GL_FRAMEBUFFER, _fbo);

        /* Farbziel als Textur statt Renderbuffer - siehe Kommentar
           oben zur Tile-Aufloesung. */
        if (!loadTexEntryPoints()) {
            OSG_WARN << "GraphicsWindowEGL: Textur-Entrypoints fehlen"
                     << std::endl;
            return false;
        }
        p_GenTextures(1, &_texColor);
        p_BindTexture(GL_TEXTURE_2D, _texColor);

        bool shared = false;

        /* Zuerst der Weg ueber einen Puffer, den der Presenter
           bereitstellt. Der funktioniert unter allen Backends, weil er
           ohne EGL_EXT_image_dma_buf_import auskommt. */
        if (tryHybrisBuffer(w, h)) shared = true;

        /* Sonst ein Puffer vom Kernel-Heap. Den kann nur Mesa
           importieren, also nur unter Zink. */
        if (!shared) _dmabufFd = allocDmaHeap(size_t(w) * size_t(h) * 4u);

        if (!shared && _dmabufFd >= 0) {
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

                    const char* sp = ::getenv("FGFS_FD_SOCKET");
                    if (!sp || !*sp) sp = "/tmp/fgfs-frame.sock";
                    g_fdServer.start(_dmabufFd, sp);
                } else {
                    OSG_WARN << "GraphicsWindowEGL: dmabuf-Import fehlgeschlagen 0x"
                             << std::hex << eglGetError() << std::dec
                             << ", falle auf Readback zurueck" << std::endl;
                }
            }
        }

        if (!shared) {
            /* NICHT schliessen: EGL hat den Deskriptor beim Import
               moeglicherweise bereits uebernommen, und ein zweites
               close() trifft dann einen fremden fd - der Mali-Treiber
               verliert dabei seinen eventfd (EBADF). */
            _dmabufFd = -1;
#if defined(OSG_GLES2_AVAILABLE) || defined(OSG_GLES3_AVAILABLE)
            /* GLES2 kennt kein sized internal format wie GL_RGBA8. */
            p_TexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0,
                         GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
#else
            p_TexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, w, h, 0,
                         GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
#endif
        }
        p_TexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        p_TexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
        p_TexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
        p_TexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
        p_FramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                               GL_TEXTURE_2D, _texColor, 0);

        p_GenRenderbuffers(1, &_rbDepth);
        p_BindRenderbuffer(GL_RENDERBUFFER, _rbDepth);
#if defined(OSG_GLES2_AVAILABLE) || defined(OSG_GLES3_AVAILABLE)
        /* GLES2 kennt kein kombiniertes Depth-Stencil-Format ohne
           OES_packed_depth_stencil. Nur Tiefe, kein Stencil - das
           genuegt fuer FlightGears Renderpfad. */
        p_RenderbufferStorage(GL_RENDERBUFFER, 0x81A5 /* DEPTH_COMPONENT16 */, w, h);
#else
        p_RenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH24_STENCIL8, w, h);
#endif
        p_FramebufferRenderbuffer(GL_FRAMEBUFFER,
#if defined(OSG_GLES2_AVAILABLE) || defined(OSG_GLES3_AVAILABLE)
                                  0x8D00 /* GL_DEPTH_ATTACHMENT */,
#else
                                  GL_DEPTH_STENCIL_ATTACHMENT,
#endif
                                  GL_RENDERBUFFER, _rbDepth);

        {
            unsigned st = p_CheckFramebufferStatus(GL_FRAMEBUFFER);
            if (st != GL_FRAMEBUFFER_COMPLETE) {
                OSG_WARN << "GraphicsWindowEGL: FBO unvollstaendig 0x"
                         << std::hex << st << std::dec
                         << " (" << w << "x" << h << ")" << std::endl;
                return false;
            }
        }


        glViewport(0, 0, w, h);
        setDefaultFboId(_fbo);
        OSG_WARN << "GraphicsWindowEGL: FBO " << _fbo
                 << " mit Textur-Attachment " << _texColor
                 << ", " << w << "x" << h << std::endl;

        if (false) {
            /* Surfaceless-Fallback: EGL_KHR_surfaceless_context ist auf
               diesem Stack vorhanden, dann rendert OSG direkt in ein FBO. */
            _surface = EGL_NO_SURFACE;
        }

        OSG_WARN << "GraphicsWindowEGL: realize fertig" << std::endl;
        _realized = true;
        return true;
    }

    bool isRealizedImplementation() const override { return _realized; }

    void closeImplementation() override
    {
        if (_display != EGL_NO_DISPLAY) {
            eglMakeCurrent(_display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
            if (_context != EGL_NO_CONTEXT) eglDestroyContext(_display, _context);
            if (_surface != EGL_NO_SURFACE) eglDestroySurface(_display, _surface);
            eglTerminate(_display);
        }
        _display = EGL_NO_DISPLAY;
        _surface = EGL_NO_SURFACE;
        _context = EGL_NO_CONTEXT;
        _realized = false;
        _valid = false;
    }

    bool makeCurrentImplementation() override
    {
        if (!_realized) {
            OSG_WARN << "GraphicsWindowEGL: makeCurrent auf nicht realisiertem Fenster"
                     << std::endl;
            return false;
        }
        if (!eglMakeCurrent(_display, _surface, _surface, _context)) {
            OSG_WARN << "GraphicsWindowEGL: eglMakeCurrent failed 0x"
                     << std::hex << eglGetError() << std::dec << std::endl;
            return false;
        }
        if (_fbo && p_BindFramebuffer) p_BindFramebuffer(GL_FRAMEBUFFER, _fbo);
        static int n = 0;
        if (n < 3) { OSG_WARN << "GraphicsWindowEGL: makeCurrent " << ++n
                              << " thread=" << (unsigned long)pthread_self()
                              << std::endl; }
        return true;
    }

    bool makeContextCurrentImplementation(osg::GraphicsContext* /*readCtx*/) override
    {
        return makeCurrentImplementation();
    }

    bool releaseContextImplementation() override
    {
        if (_display == EGL_NO_DISPLAY) return false;
        return eglMakeCurrent(_display, EGL_NO_SURFACE,
                              EGL_NO_SURFACE, EGL_NO_CONTEXT) == EGL_TRUE;
    }

    void bindPBufferToTextureImplementation(GLenum) override
    {
        OSG_NOTICE << "GraphicsWindowEGL: bindPBufferToTexture nicht implementiert"
                   << std::endl;
    }

    void swapBuffersImplementation() override
    {
        if (_surface != EGL_NO_SURFACE) {
            eglSwapBuffers(_display, _surface);
        }
        publishToShm();
        dumpFrameIfRequested();
    }


    /* --- Geteilter hybris-Nativpuffer ----------------------------
     *
     * Der Presenter legt den Puffer an und haelt seine Beschreibung
     * auf einem Unix-Socket bereit: drei Ints (stride, Anzahl Ints,
     * Anzahl Deskriptoren), dann die Ints, die Deskriptoren als
     * Beipack. Wir stellen den Puffer daraus wieder her.
     */
    bool tryHybrisBuffer(int w, int h)
    {
        const char* sp = ::getenv("FGFS_HYB_SOCKET");
        if (!sp || !*sp) return false;

        typedef unsigned (*PFN_Remote)(EGLint, EGLint, EGLint, EGLint,
                                       EGLint, int, int*, int, int*,
                                       void**);
        typedef void* (*PFN_Image)(EGLDisplay, EGLContext, EGLenum,
                                   void*, const EGLint*);
        typedef void  (*PFN_Target)(unsigned, void*);

        PFN_Remote Remote = (PFN_Remote)
            eglGetProcAddress("eglHybrisCreateRemoteBuffer");
        PFN_Image  Image  = (PFN_Image)
            eglGetProcAddress("eglCreateImageKHR");
        PFN_Target Target = (PFN_Target)
            eglGetProcAddress("glEGLImageTargetTexture2DOES");
        if (!Remote || !Image || !Target) {
            OSG_WARN << "GraphicsWindowEGL: hybris-Puffer nicht "
                        "verfuegbar" << std::endl;
            return false;
        }

        int s = ::socket(AF_UNIX, SOCK_STREAM, 0);
        if (s < 0) return false;

        struct sockaddr_un sa;
        memset(&sa, 0, sizeof sa);
        sa.sun_family = AF_UNIX;
        ::strncpy(sa.sun_path, sp, sizeof(sa.sun_path) - 1);
        if (::connect(s, (struct sockaddr*)&sa, sizeof sa) < 0) {
            OSG_WARN << "GraphicsWindowEGL: kein Presenter auf " << sp
                     << std::endl;
            ::close(s);
            return false;
        }

        int head[3] = { 0, 0, 0 };
        int ints[128];
        int fds[16];
        char cbuf[CMSG_SPACE(16 * sizeof(int))];
        struct iovec iov[2];
        struct msghdr msg;

        iov[0].iov_base = head;  iov[0].iov_len = sizeof head;
        iov[1].iov_base = ints;  iov[1].iov_len = sizeof ints;
        memset(&msg, 0, sizeof msg);
        msg.msg_iov = iov;  msg.msg_iovlen = 2;
        msg.msg_control = cbuf;
        msg.msg_controllen = sizeof cbuf;

        if (::recvmsg(s, &msg, 0) <= 0) { ::close(s); return false; }

        struct cmsghdr* cm = CMSG_FIRSTHDR(&msg);
        if (!cm || cm->cmsg_type != SCM_RIGHTS) { ::close(s); return false; }

        const int stride = head[0];
        const int nints  = head[1];
        const int nfds   = head[2];
        if (nints <= 0 || nints > 128 || nfds <= 0 || nfds > 16) {
            ::close(s); return false;
        }
        memcpy(fds, CMSG_DATA(cm), nfds * sizeof(int));

        /* Android-Gralloc: RGBA8888, von GPU beschreibbar, von der
           CPU lesbar (der Presenter darf notfalls direkt hineinsehen). */
        const EGLint usage = 0x00000100 | 0x00000200
                           | 0x00000003 | 0x00000030;

        void* buf = nullptr;
        if (!Remote(w, h, usage, 1 /* RGBA8888 */, stride,
                    nints, ints, nfds, fds, &buf) || !buf) {
            OSG_WARN << "GraphicsWindowEGL: CreateRemoteBuffer "
                        "fehlgeschlagen" << std::endl;
            ::close(s);
            return false;
        }

        void* img = Image(_display, EGL_NO_CONTEXT,
                          0x3140 /* EGL_NATIVE_BUFFER_HYBRIS */,
                          buf, nullptr);
        if (!img) {
            OSG_WARN << "GraphicsWindowEGL: EGLImage aus hybris-Puffer "
                        "fehlgeschlagen 0x" << std::hex << eglGetError()
                     << std::dec << std::endl;
            ::close(s);
            return false;
        }

        Target(GL_TEXTURE_2D, img);

        _hybSocket = s;          /* offen halten, sonst faellt der
                                    Puffer beim Presenter weg */
        _hybShared = true;
        _hybStride = stride;
        OSG_WARN << "GraphicsWindowEGL: geteilter hybris-Puffer, "
                 << w << "x" << h << ", stride=" << stride << std::endl;
        return true;
    }

    void publishToShm()
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

        /* Der Presenter besitzt den Puffer und hat ihn selbst als
           Textur - wir melden nur, dass der Frame fertig ist. */
        if (_hybShared) {
            glFlush();
            g_shm.publishDmabuf(getpid(), 0, uint32_t(_hybStride) * 4u,
                                0x48594252 /* HYBR */);
            ++_frameCount;
            return;
        }

        /* Zero-Copy: die GPU hat bereits in den geteilten Puffer
           gerendert. Es bleibt nur, den Frame als fertig zu melden. */
        if (_dmabufFd >= 0) {
            {
                static int m = 0;
                if (m < 3) { OSG_WARN << "GraphicsWindowEGL: publish "
                                      << ++m << " thread="
                                      << (unsigned long)pthread_self()
                                      << std::endl; }
            }
            if (!g_shm.ready() && !g_shm.open(w, h)) return;

            /* Statt glFinish - das den Simulator bis zur Fertigstellung
               saemtlicher GPU-Arbeit anhaelt - ein Fence: die Pipeline
               laeuft weiter, und der Presenter wartet selbst darauf,
               bis der Frame vollstaendig ist. */
#if defined(OSG_GLES2_AVAILABLE) || defined(OSG_GLES3_AVAILABLE)
            /* GLES2: kein Fence - EGL_ANDROID_native_fence_sync
               verhaelt sich hier anders, und die Renderschleife
               bleibt sonst nach wenigen Frames stehen. */
            _useFence = false;
#endif
            if (::getenv("FGFS_NO_SYNC")) _useFence = false;
            if (_useFence) {
                if (!_pCreateSync) {
                    _pCreateSync = (PFN_CreateSyncKHR)
                        eglGetProcAddress("eglCreateSyncKHR");
                    _pDupFence = (PFN_DupNativeFence)
                        eglGetProcAddress("eglDupNativeFenceFDANDROID");
                    _pDestroySync = (PFN_DestroySyncKHR)
                        eglGetProcAddress("eglDestroySyncKHR");
                    if (!_pCreateSync || !_pDupFence || !_pDestroySync) {
                        OSG_WARN << "GraphicsWindowEGL: kein "
                                    "native_fence_sync, nutze glFinish"
                                 << std::endl;
                        _useFence = false;
                    }
                }
            }

            if (_useFence) {
                EGLSyncKHR sync = _pCreateSync(
                    _display, 0x3144 /* EGL_SYNC_NATIVE_FENCE_ANDROID */,
                    nullptr);
                glFlush();                 /* Fence in die Queue schieben */
                if (sync != EGL_NO_SYNC_KHR) {
                    const int ffd = _pDupFence(_display, sync);
                    _pDestroySync(_display, sync);
                    g_fdServer.setFence(ffd);   /* uebernimmt den fd */
                } else {
                    glFinish();               /* Notnagel */
                }
            } else if (::getenv("FGFS_NO_SYNC")) {
                /* Ohne jede Synchronisation - die Pipeline laeuft
                   durch, der Presenter kann ein halbfertiges Bild
                   sehen. Zum Vergleichsmessen. */
                glFlush();
            } else {
#if defined(OSG_GLES2_AVAILABLE) || defined(OSG_GLES3_AVAILABLE)
                /* Der Mali-Blob bietet keine Sync-Erweiterungen, und
                   glFinish haelt die Pipeline bei jedem Frame an.
                   glFlush schiebt die Arbeit nur an - der Presenter
                   kann dadurch ein halbfertiges Bild sehen. */
                glFlush();
#else
                glFinish();
#endif
            }
            g_shm.publishDmabuf(getpid(), _dmabufFd, w * 4, 0x34324241);
            ++_frameCount;
            return;
        }

        const size_t bytes = size_t(w) * size_t(h) * 4u;

        /* PBOs beim ersten Aufruf anlegen */
        if (!_pbo[0]) {
#if defined(OSG_GLES2_AVAILABLE) || defined(OSG_GLES3_AVAILABLE)
            if (true) {   /* GLES2 hat keine Pixel-Buffer-Objects */
#else
            if (!loadPboEntryPoints()) {
#endif
                OSG_WARN << "GraphicsWindowEGL: keine PBO-Unterstuetzung, "
                            "falle auf blockierenden Readback zurueck"
                         << std::endl;
                _pboUnavailable = true;
            } else {
                p_GenBuffers(2, _pbo);
                for (int i = 0; i < 2; ++i) {
                    p_BindBuffer(GL_PIXEL_PACK_BUFFER, _pbo[i]);
                    p_BufferData(GL_PIXEL_PACK_BUFFER, long(bytes),
                                 nullptr, GL_STREAM_READ);
                }
                p_BindBuffer(GL_PIXEL_PACK_BUFFER, 0);
                OSG_NOTICE << "GraphicsWindowEGL: PBO-Readback aktiv ("
                           << (2 * bytes / 1024) << " KiB)" << std::endl;
            }
        }

        glPixelStorei(GL_PACK_ALIGNMENT, 1);

        if (_pboUnavailable) {
            const int slot = int(_frameCount & 1u);
            ++_frameCount;
            g_shm.beginWrite(slot);
            glReadPixels(0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE,
                         g_shm.slotPtr(slot));
            g_shm.endWrite(slot);
            return;
        }

        const int cur  = int(_frameCount & 1u);
        const int prev = 1 - cur;

        /* Transfer fuer diesen Frame anstossen - kehrt sofort zurueck,
           weil das Ziel ein Puffer im GPU-Speicher ist. */
        p_BindBuffer(GL_PIXEL_PACK_BUFFER, _pbo[cur]);
        glReadPixels(0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);

        /* Ergebnis des Vorframes abholen. Erst ab dem zweiten Frame,
           vorher enthaelt der andere Puffer nichts. */
        if (_frameCount > 0) {
            p_BindBuffer(GL_PIXEL_PACK_BUFFER, _pbo[prev]);
            void* src = p_MapBuffer(GL_PIXEL_PACK_BUFFER, GL_READ_ONLY);
            if (src) {
                const int slot = int(_frameCount & 1u);
                g_shm.beginWrite(slot);
                memcpy(g_shm.slotPtr(slot), src, bytes);
                g_shm.endWrite(slot);
                p_UnmapBuffer(GL_PIXEL_PACK_BUFFER);
            }
        }

        p_BindBuffer(GL_PIXEL_PACK_BUFFER, 0);
        ++_frameCount;
    }

    void dumpFrameIfRequested()
    {
        static int every = -1;
        static const char* path = nullptr;
        if (every < 0) {
            const char* e = ::getenv("FGFS_DUMP_EVERY");
            every = (e && *e) ? ::atoi(e) : 0;
            path  = ::getenv("FGFS_DUMP_PATH");
            if (!path || !*path) path = "/tmp/fgfs-frame.ppm";
            if (every > 0) {
                OSG_NOTICE << "GraphicsWindowEGL: Frame-Dump alle " << every
                           << " Frames nach " << path << std::endl;
            }
        }
        if (every <= 0) return;

        if ((++_frameCount % every) != 0) return;

        const int w = _traits.valid() ? _traits->width  : 960;
        const int h = _traits.valid() ? _traits->height : 540;

        if (_pixels.size() != size_t(w) * size_t(h) * 4u) {
            _pixels.resize(size_t(w) * size_t(h) * 4u);
        }

        glFinish();
        glPixelStorei(GL_PACK_ALIGNMENT, 1);
        glReadPixels(0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, _pixels.data());

        /* PPM ist verlustfrei und braucht keine Bibliothek.
           Erst in eine Temp-Datei, dann umbenennen - so sieht ein
           mitlesender Prozess nie ein halbes Bild. */
        std::string tmp = std::string(path) + ".tmp";
        FILE* f = ::fopen(tmp.c_str(), "wb");
        if (!f) return;

        ::fprintf(f, "P6\n%d %d\n255\n", w, h);
        /* GL liefert von unten nach oben, PPM will von oben nach unten */
        for (int y = h - 1; y >= 0; --y) {
            const unsigned char* row = _pixels.data() + size_t(y) * size_t(w) * 4u;
            for (int x = 0; x < w; ++x) {
                ::fputc(row[x * 4 + 0], f);
                ::fputc(row[x * 4 + 1], f);
                ::fputc(row[x * 4 + 2], f);
            }
        }
        ::fclose(f);
        ::rename(tmp.c_str(), path);
    }

    // ---- osgViewer::GraphicsWindow ------------------------------------

    void grabFocus() override {}
    void grabFocusIfPointerInWindow() override {}

    bool setWindowRectangleImplementation(int, int, int, int) override
    {
        return false;   // feste Groesse
    }

    void setWindowName(const std::string&) override {}
    void useCursor(bool) override {}
    void setCursor(MouseCursor) override {}

    bool checkEvents() override { return false; }

    // ---- Zugriff fuer den Presenter -----------------------------------

    EGLDisplay eglDisplay() const { return _display; }
    EGLSurface eglSurface() const { return _surface; }
    EGLContext eglContext() const { return _context; }

protected:
    ~GraphicsWindowEGL() override { closeImplementation(); }

private:
    /* Puffer vom Kernel-Heap. Lesezugriff auf das Geraet genuegt,
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
    {
        if (_initialized) return;
        _initialized = true;

        _display = eglGetDisplay(EGL_DEFAULT_DISPLAY);
        if (_display == EGL_NO_DISPLAY) {
            OSG_WARN << "GraphicsWindowEGL: eglGetDisplay failed" << std::endl;
            return;
        }

        EGLint major = 0, minor = 0;
        if (!eglInitialize(_display, &major, &minor)) {
            OSG_WARN << "GraphicsWindowEGL: eglInitialize failed 0x"
                     << std::hex << eglGetError() << std::dec << std::endl;
            return;
        }
        OSG_INFO << "GraphicsWindowEGL: EGL " << major << "." << minor
                 << " vendor=" << eglQueryString(_display, EGL_VENDOR) << std::endl;

        /* Desktop-GL, nicht GLES - das ist der ganze Sinn des Zink-Stacks. */
        if (!eglBindAPI(FGFS_EGL_API)) {
            OSG_WARN << "GraphicsWindowEGL: eglBindAPI(EGL_OPENGL_API) failed"
                     << std::endl;
            return;
        }

        const EGLint red   = _traits.valid() ? _traits->red   : 8;
        const EGLint green = _traits.valid() ? _traits->green : 8;
        const EGLint blue  = _traits.valid() ? _traits->blue  : 8;
        const EGLint alpha = _traits.valid() ? _traits->alpha : 8;
        const EGLint depth = _traits.valid() ? _traits->depth : 24;
        const EGLint stenc = _traits.valid() ? _traits->stencil : 8;

        const EGLint cfgAttr[] = {
            EGL_SURFACE_TYPE,    EGL_WINDOW_BIT,
            EGL_RENDERABLE_TYPE, FGFS_EGL_RENDERABLE,
            EGL_RED_SIZE,        red,
            EGL_GREEN_SIZE,      green,
            EGL_BLUE_SIZE,       blue,
            EGL_ALPHA_SIZE,      alpha,
            EGL_DEPTH_SIZE,      depth,
            EGL_STENCIL_SIZE,    stenc,
            EGL_NONE
        };

        EGLint num = 0;
        if (!eglChooseConfig(_display, cfgAttr, &_config, 1, &num) || num < 1) {
            OSG_WARN << "GraphicsWindowEGL: keine passende EGLConfig "
                        "(OPENGL_BIT + PBUFFER_BIT)" << std::endl;
            return;
        }

        EGLContext shared = EGL_NO_CONTEXT;
        if (_traits.valid() && _traits->sharedContext.valid()) {
            GraphicsWindowEGL* other =
                dynamic_cast<GraphicsWindowEGL*>(_traits->sharedContext.get());
            if (other) shared = other->_context;
        }

        /* 3.x reicht: Zink meldet auf Mali-G610 GL 3.2 Compatibility,
           begrenzt durch fehlendes shaderClipDistance. */
        const EGLint ctxAttr[] = {
            FGFS_EGL_CTX_ATTR, FGFS_EGL_CTX_VER,
            EGL_NONE
        };

        _context = eglCreateContext(_display, _config, shared, ctxAttr);
        if (_context == EGL_NO_CONTEXT) {
            OSG_WARN << "GraphicsWindowEGL: eglCreateContext failed 0x"
                     << std::hex << eglGetError() << std::dec << std::endl;
            return;
        }

        _valid = true;
    }

    unsigned long _frameCount = 0;
    std::vector<unsigned char> _pixels;

    unsigned _fbo = 0;
    unsigned _rbColor = 0;
    unsigned _texColor = 0;

    typedef EGLSyncKHR (*PFN_CreateSyncKHR)(EGLDisplay, EGLenum, const EGLint*);
    typedef EGLint     (*PFN_DupNativeFence)(EGLDisplay, EGLSyncKHR);
    typedef EGLBoolean (*PFN_DestroySyncKHR)(EGLDisplay, EGLSyncKHR);

    PFN_CreateSyncKHR  _pCreateSync = nullptr;
    PFN_DupNativeFence _pDupFence = nullptr;
    PFN_DestroySyncKHR _pDestroySync = nullptr;
    bool _useFence = true;
    int  _dmabufFd = -1;
    bool _hybShared = false;
    int  _hybSocket = -1;
    int  _hybStride = 0;
    EGLImageKHR _dmabufImage = EGL_NO_IMAGE_KHR;
    unsigned _rbDepth = 0;
    unsigned _pbo[2] = { 0, 0 };
    bool _pboUnavailable = false;

    EGLDisplay _display;
    EGLSurface _surface;
    EGLContext _context;
    EGLConfig  _config;
    bool _valid;
    bool _realized;
    bool _initialized;
};


class EGLWindowingSystemInterface
    : public osg::GraphicsContext::WindowingSystemInterface
{
public:
    EGLWindowingSystemInterface()
    {
        setName("EGL");
    }

    unsigned int getNumScreens(
        const osg::GraphicsContext::ScreenIdentifier&) override
    {
        return 1;
    }

    void getScreenSettings(const osg::GraphicsContext::ScreenIdentifier&,
                           osg::GraphicsContext::ScreenSettings& res) override
    {
        res.width       = envInt("FGFS_EGL_WIDTH",  960);
        res.height      = envInt("FGFS_EGL_HEIGHT", 540);
        res.refreshRate = 60;
        res.colorDepth  = 24;
    }

    void enumerateScreenSettings(
        const osg::GraphicsContext::ScreenIdentifier& si,
        osg::GraphicsContext::ScreenSettingsList& list) override
    {
        list.clear();
        osg::GraphicsContext::ScreenSettings s;
        getScreenSettings(si, s);
        list.push_back(s);
    }

    osg::GraphicsContext* createGraphicsContext(
        osg::GraphicsContext::Traits* traits) override
    {
        osg::ref_ptr<GraphicsWindowEGL> win = new GraphicsWindowEGL(traits);
        if (win->valid()) return win.release();
        OSG_WARN << "EGLWindowingSystemInterface: Kontext-Erzeugung fehlgeschlagen"
                 << std::endl;
        return nullptr;
    }

private:
    static int envInt(const char* name, int fallback)
    {
        const char* v = ::getenv(name);
        if (!v || !*v) return fallback;
        int n = ::atoi(v);
        return n > 0 ? n : fallback;
    }
};

REGISTER_WINDOWINGSYSTEMINTERFACE(EGL, EGLWindowingSystemInterface)

} // namespace osgViewer

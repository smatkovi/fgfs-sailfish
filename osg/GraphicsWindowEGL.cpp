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

/* GL-Konstanten und -Prototypen ohne GL/gl.h, damit wir nicht gegen
   glvnd-Header linken muessen - die Symbole kommen aus libOpenGL. */
#ifndef GL_RGBA
#define GL_RGBA           0x1908
#define GL_UNSIGNED_BYTE  0x1401
#define GL_PACK_ALIGNMENT 0x0D05
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

        (void)pbAttr;
        _surface = EGL_NO_SURFACE;

        if (!eglMakeCurrent(_display, EGL_NO_SURFACE, EGL_NO_SURFACE, _context)) {
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

        p_GenRenderbuffers(1, &_rbColor);
        p_BindRenderbuffer(GL_RENDERBUFFER, _rbColor);
        p_RenderbufferStorage(GL_RENDERBUFFER, GL_RGBA8, w, h);
        p_FramebufferRenderbuffer(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                                  GL_RENDERBUFFER, _rbColor);

        p_GenRenderbuffers(1, &_rbDepth);
        p_BindRenderbuffer(GL_RENDERBUFFER, _rbDepth);
        p_RenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH24_STENCIL8, w, h);
        p_FramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT,
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
        OSG_NOTICE << "GraphicsWindowEGL: FBO " << _fbo << " angelegt, "
                   << w << "x" << h << std::endl;

        if (false) {
            /* Surfaceless-Fallback: EGL_KHR_surfaceless_context ist auf
               diesem Stack vorhanden, dann rendert OSG direkt in ein FBO. */
            _surface = EGL_NO_SURFACE;
        }

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

        const int slot = int(_frameCount & 1u);
        ++_frameCount;

        glPixelStorei(GL_PACK_ALIGNMENT, 1);

        g_shm.beginWrite(slot);
        glReadPixels(0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE,
                     g_shm.slotPtr(slot));
        g_shm.endWrite(slot);
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
        if (!eglBindAPI(EGL_OPENGL_API)) {
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
            EGL_RENDERABLE_TYPE, EGL_OPENGL_BIT,
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
            EGL_CONTEXT_MAJOR_VERSION, 3,
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
    unsigned _rbDepth = 0;

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

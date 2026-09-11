/* osg-model-test - draw one model with the GLES build of OSG, nothing else.
 *
 * FlightGear's c172p instrument faces sample texture coordinate (0,0) on the
 * device although the model, the geometry, the attribute slot, the bound
 * texture and the program all check out.  Too many layers sit between the
 * model file and the draw call to tell where it goes wrong, so this program
 * removes all of them: no FlightGear, no SimGear loader policy, no effects,
 * no compositor.  Just osgDB reading the file and osgViewer drawing it into
 * an offscreen buffer.
 *
 *   osg-model-test <model.ac> <out.ppm> [mode]
 *
 *     tex   (default) draw the model as it comes
 *     tc    draw fract(texcoord) instead of the colour
 *     solid draw one flat colour through our own program - answers
 *           "does this geometry rasterise at all", with no texture and no
 *           texture coordinate involved
 *     quad  ignore the model; draw a hand-built quad with known texture
 *           coordinates through the tc readout.  This is the control case:
 *           it must show a red/green gradient.  If it does not, OSG's
 *           attribute path is broken for everything and the model is
 *           irrelevant; if it does, the fault is specific to the loaded
 *           geometry.
 *
 * The earlier version of this program never set a camera.  With no
 * manipulator the view matrix stays identity, so the camera sat inside the
 * model and every render came out as pure clear colour - which read as
 * "flat texture coordinates" and nearly produced a false confirmation.
 * See BEFUNDE.md, B3.  The camera is now framed from the model's bounding
 * box, looking down its *thinnest* axis: a dial is a flat disc, so its
 * thin axis is its normal, which is the one view guaranteed not to catch
 * the thing edge-on.
 *
 * Build (in the SDK container):
 *   sb2 -t SailfishOS-5.2.0.15-aarch64 g++ -std=c++11 -O1 osg-model-test.cpp \
 *       -I/opt/osg-gles3/include -L/opt/osg-gles3/lib \
 *       -losg -losgDB -losgUtil -losgGA -losgViewer -lOpenThreads \
 *       -o osg-model-test
 */
#include <osg/ArgumentParser>
#include <osg/ComputeBoundsVisitor>
#include <osg/Geode>
#include <osg/Geometry>
#include <osg/Image>
#include <osg/Program>
#include <osg/Shader>
#include <osg/Texture2D>
#include <osgDB/ReadFile>
#include <osgViewer/Viewer>

#include <cstdio>
#include <iostream>
#include <string>

namespace
{

/* Walk the model and say what the drawables carry - the same numbers the
   probe on the device printed, but here we know which file they came from. */
class Report : public osg::NodeVisitor
{
public:
    Report() : osg::NodeVisitor(TRAVERSE_ALL_CHILDREN), _n(0) {}

    void apply(osg::Geode& geode) override
    {
        for (unsigned int i = 0; i < geode.getNumDrawables(); ++i)
        {
            const osg::Geometry* g = geode.getDrawable(i)->asGeometry();
            if (!g) continue;
            ++_n;

            std::string tex;
            const osg::StateSet* ss = g->getStateSet()
                                      ? g->getStateSet() : geode.getStateSet();
            if (ss)
            {
                const osg::Texture2D* t = dynamic_cast<const osg::Texture2D*>(
                    ss->getTextureAttribute(0, osg::StateAttribute::TEXTURE));
                if (t && t->getImage()) tex = t->getImage()->getFileName();
            }
            std::string::size_type sl = tex.find_last_of('/');
            if (sl != std::string::npos) tex = tex.substr(sl + 1);

            const osg::Array* tc = g->getNumTexCoordArrays() > 0
                                   ? g->getTexCoordArray(0) : 0;
            const osg::Vec2Array* v2 = dynamic_cast<const osg::Vec2Array*>(tc);

            std::printf("  geode[%s] drawable %u: verts=%u texcoords=%u prims=%u",
                        geode.getName().c_str(), i,
                        g->getVertexArray() ? (unsigned)g->getVertexArray()->getNumElements() : 0u,
                        tc ? (unsigned)tc->getNumElements() : 0u,
                        (unsigned)g->getNumPrimitiveSets());
            if (v2 && v2->size() >= 2)
                std::printf(" first=(%.4f,%.4f) (%.4f,%.4f)",
                            (*v2)[0].x(), (*v2)[0].y(), (*v2)[1].x(), (*v2)[1].y());
            std::printf(" vbo=%d tex=[%s]",
                        g->getUseVertexBufferObjects() ? 1 : 0, tex.c_str());

            /* Which primitive modes, by name. GL_QUADS and GL_POLYGON do not
               exist under GLES; if the loader emits them, the driver draws
               nothing and says nothing. */
            for (unsigned int p = 0; p < g->getNumPrimitiveSets(); ++p)
            {
                const osg::PrimitiveSet* ps = g->getPrimitiveSet(p);
                const GLenum mo = ps->getMode();
                const char* name;
                switch (mo)
                {
                case GL_POINTS:         name = "POINTS"; break;
                case GL_LINES:          name = "LINES"; break;
                case GL_LINE_STRIP:     name = "LINE_STRIP"; break;
                case GL_LINE_LOOP:      name = "LINE_LOOP"; break;
                case GL_TRIANGLES:      name = "TRIANGLES"; break;
                case GL_TRIANGLE_STRIP: name = "TRIANGLE_STRIP"; break;
                case GL_TRIANGLE_FAN:   name = "TRIANGLE_FAN"; break;
                case 0x0007:            name = "QUADS !! not in GLES"; break;
                case 0x0008:            name = "QUAD_STRIP !! not in GLES"; break;
                case 0x0009:            name = "POLYGON !! not in GLES"; break;
                default:                name = "?"; break;
                }
                std::printf(" [prim%u mode=0x%04x %s n=%u]",
                            p, (unsigned)mo, name,
                            (unsigned)ps->getNumIndices());
            }
            std::printf("\n");
        }
        traverse(geode);
    }

    unsigned int count() const { return _n; }

private:
    unsigned int _n;
};

/* The texture coordinate readout, as a program of its own.  Written against
   OSG's aliases so it works with vertex attribute aliasing, which is what
   the GLES build uses. */
osg::Program* texCoordProgram()
{
    const char* vs =
        "attribute vec4 osg_Vertex;\n"
        "attribute vec4 osg_MultiTexCoord0;\n"
        "uniform mat4 osg_ModelViewProjectionMatrix;\n"
        "varying vec2 tc;\n"
        "void main() {\n"
        "  gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;\n"
        "  tc = osg_MultiTexCoord0.st;\n"
        "}\n";
    const char* fs =
        "precision mediump float;\n"
        "varying vec2 tc;\n"
        "void main() { gl_FragColor = vec4(fract(tc), 0.0, 1.0); }\n";

    osg::Program* p = new osg::Program;
    p->setName("texcoord_readout");
    p->addShader(new osg::Shader(osg::Shader::VERTEX, vs));
    p->addShader(new osg::Shader(osg::Shader::FRAGMENT, fs));
    return p;
}

/* Flat colour, touching no texture and no texture coordinate.  Whatever
   this does not paint was never rasterised, so it separates "geometry
   missing" from "geometry drawn with bad coordinates" - the distinction the
   old harness could not make. */
osg::Program* solidProgram()
{
    const char* vs =
        "attribute vec4 osg_Vertex;\n"
        "uniform mat4 osg_ModelViewProjectionMatrix;\n"
        "void main() { gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex; }\n";
    const char* fs =
        "precision mediump float;\n"
        "void main() { gl_FragColor = vec4(0.0, 1.0, 0.0, 1.0); }\n";

    osg::Program* p = new osg::Program;
    p->setName("solid_green");
    p->addShader(new osg::Shader(osg::Shader::VERTEX, vs));
    p->addShader(new osg::Shader(osg::Shader::FRAGMENT, fs));
    return p;
}

/* The control case: geometry we built ourselves, with texture coordinates we
   know are right, drawn through the same readout.  GL_QUADS does not exist
   under ES, so this is a triangle fan. */
osg::Node* makeQuad()
{
    osg::Geometry* g = new osg::Geometry;

    osg::Vec3Array* v = new osg::Vec3Array;
    v->push_back(osg::Vec3(-1.0f, 0.0f, -1.0f));
    v->push_back(osg::Vec3( 1.0f, 0.0f, -1.0f));
    v->push_back(osg::Vec3( 1.0f, 0.0f,  1.0f));
    v->push_back(osg::Vec3(-1.0f, 0.0f,  1.0f));
    g->setVertexArray(v);

    osg::Vec2Array* t = new osg::Vec2Array;
    t->push_back(osg::Vec2(0.0f, 0.0f));
    t->push_back(osg::Vec2(1.0f, 0.0f));
    t->push_back(osg::Vec2(1.0f, 1.0f));
    t->push_back(osg::Vec2(0.0f, 1.0f));
    g->setTexCoordArray(0, t);

    g->addPrimitiveSet(new osg::DrawArrays(GL_TRIANGLE_FAN, 0, 4));

    osg::Geode* geode = new osg::Geode;
    geode->setName("control_quad");
    geode->addDrawable(g);
    return geode;
}

bool writePPM(const char* path, const osg::Image& img)
{
    FILE* f = std::fopen(path, "wb");
    if (!f) return false;
    std::fprintf(f, "P6\n%d %d\n255\n", img.s(), img.t());
    /* OSG hands the image back bottom-up */
    for (int y = img.t() - 1; y >= 0; --y)
    {
        const unsigned char* row = img.data(0, y);
        for (int x = 0; x < img.s(); ++x)
            std::fwrite(row + x * 4, 1, 3, f);
    }
    std::fclose(f);
    return true;
}

} // namespace

int main(int argc, char** argv)
{
    if (argc < 3)
    {
        std::cerr << "usage: " << argv[0]
                  << " <model> <out.ppm> [tex|tc|solid|quad]\n";
        return 2;
    }
    const std::string modelPath = argv[1];
    const std::string outPath = argv[2];
    const std::string mode = (argc > 3) ? argv[3] : "tex";

    osg::ref_ptr<osg::Node> model;
    if (mode == "quad")
    {
        model = makeQuad();
        std::printf("== control quad, model file ignored\n");
    }
    else
    {
        model = osgDB::readNodeFile(modelPath);
        if (!model)
        {
            std::cerr << "cannot read " << modelPath << "\n";
            return 1;
        }
    }

    std::printf("== what the loader produced:\n");
    Report report;
    model->accept(report);
    std::printf("   %u drawables\n", report.count());

    /* Extents first: without them a blank image is unreadable, because
       "nothing drawn" and "drawn off-screen" look identical. */
    osg::ComputeBoundsVisitor cbv;
    model->accept(cbv);
    const osg::BoundingBox bb = cbv.getBoundingBox();
    if (!bb.valid())
    {
        std::cerr << "bounding box is invalid - there is no geometry to draw\n";
        return 1;
    }
    const osg::Vec3 centre = bb.center();
    const osg::Vec3 size(bb.xMax() - bb.xMin(),
                         bb.yMax() - bb.yMin(),
                         bb.zMax() - bb.zMin());
    std::printf("== bounds: centre (%.4f, %.4f, %.4f) size (%.4f, %.4f, %.4f)\n",
                centre.x(), centre.y(), centre.z(),
                size.x(), size.y(), size.z());

    /* Look down the thinnest axis: a dial is a flat disc, and its thin axis
       is its normal, so this is the one direction that cannot show it
       edge-on. */
    int thin = 0;
    if (size.y() < size[thin]) thin = 1;
    if (size.z() < size[thin]) thin = 2;
    osg::Vec3 eyeDir(0.0f, 0.0f, 0.0f);
    eyeDir[thin] = 1.0f;
    osg::Vec3 up(0.0f, 0.0f, 1.0f);
    if (thin == 2) up.set(0.0f, 1.0f, 0.0f);
    std::printf("== viewing along axis %c\n", "xyz"[thin]);

    float radius = size.length() * 0.5f;
    if (radius <= 0.0f) radius = 1.0f;

    if (mode == "tc" || mode == "quad")
    {
        model->getOrCreateStateSet()->setAttributeAndModes(
            texCoordProgram(), osg::StateAttribute::ON | osg::StateAttribute::OVERRIDE);
        std::printf("== drawing fract(texcoord)\n");
    }
    else if (mode == "solid")
    {
        model->getOrCreateStateSet()->setAttributeAndModes(
            solidProgram(), osg::StateAttribute::ON | osg::StateAttribute::OVERRIDE);
        std::printf("== drawing flat green\n");
    }
    else
    {
        std::printf("== drawing the model as it is\n");
    }

    /* Two-sided: the dial may well face away from the axis we picked, and a
       back-facing disc would be culled into another blank image. */
    if (mode != "tex")
        model->getOrCreateStateSet()->setMode(
            GL_CULL_FACE, osg::StateAttribute::OFF | osg::StateAttribute::OVERRIDE);

    const int width = 512, height = 512;

    osg::ref_ptr<osg::GraphicsContext::Traits> traits = new osg::GraphicsContext::Traits;
    traits->x = 0; traits->y = 0;
    traits->width = width; traits->height = height;
    traits->windowDecoration = false;
    traits->doubleBuffer = true;
    traits->pbuffer = true;          /* offscreen; the EGL window falls back
                                        to surfaceless where pbuffers are
                                        unavailable */
    traits->sharedContext = 0;

    osg::ref_ptr<osg::GraphicsContext> gc = osg::GraphicsContext::createGraphicsContext(traits.get());
    if (!gc)
    {
        std::cerr << "no graphics context\n";
        return 1;
    }

    osgViewer::Viewer viewer;
    viewer.setThreadingModel(osgViewer::ViewerBase::SingleThreaded);
    viewer.setSceneData(model.get());
    viewer.getCamera()->setGraphicsContext(gc.get());
    viewer.getCamera()->setViewport(new osg::Viewport(0, 0, width, height));
    viewer.getCamera()->setClearColor(osg::Vec4(0.15f, 0.15f, 0.2f, 1.0f));

    osg::ref_ptr<osg::Image> shot = new osg::Image;
    shot->allocateImage(width, height, 1, GL_RGBA, GL_UNSIGNED_BYTE);
    viewer.getCamera()->attach(osg::Camera::COLOR_BUFFER, shot.get());

    viewer.realize();

    /* Set after realize() so nothing in realisation overwrites it.  There is
       no manipulator, so these matrices survive every frame.  Orthographic,
       framed slightly wider than the box, removes any question of
       perspective or near/far clipping hiding the model. */
    const float m = radius * 1.2f;
    viewer.getCamera()->setComputeNearFarMode(osg::CullSettings::DO_NOT_COMPUTE_NEAR_FAR);
    viewer.getCamera()->setProjectionMatrixAsOrtho(-m, m, -m, m,
                                                   -radius * 10.0f, radius * 10.0f);
    viewer.getCamera()->setViewMatrixAsLookAt(centre + eyeDir * radius * 3.0f,
                                              centre, up);

    /* a few frames, so anything lazy has run */
    for (int i = 0; i < 5; ++i) viewer.frame();

    if (!writePPM(outPath.c_str(), *shot))
    {
        std::cerr << "cannot write " << outPath << "\n";
        return 1;
    }
    std::printf("== wrote %s\n", outPath.c_str());
    return 0;
}

#!/usr/bin/env python3
"""SimGear: the VASI/PAPI approach lights draw under GLES.

SGVasiDrawable paints one GL_POINT per light in immediate mode.  Neither
exists under GLES2/3, so the port turned those calls into no-ops and the
approach lights were simply missing.

Drawing them from inside the drawable does not work either: with vertex
array objects - which this port asks for - the arrays of a geometry drawn
from another drawable's drawImplementation are never bound, and nothing
reaches the raster (measured: correct colours in the arrays, no GL error,
not a pixel on screen).

So under GLES the lights become what every other runway light already is:
an ordinary osg::Geometry in the scene graph, triangles with a bright
centre vertex and two transparent ones, drawn by the same approach light
effect.  What the drawable did per frame - red below the glide path, white
above, nothing when seen from behind - now happens in a cull callback,
which knows the eye point and can write the colours before the draw.

Idempotent.  python3 sg_vasi_gles.py [simgear-source-root]"""
import os, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/simgear-2020.3.19'
pt = os.path.join(ROOT, 'simgear/scene/tgdb/pt_lights.cxx')

# ---- the old drawable still has to compile -----------------------------
# Its immediate mode member is built on every platform; under GLES those
# calls have to turn into nothing.  Unused there - the lights below are
# geometry - but the compiler sees it.
cxx = os.path.join(ROOT, 'simgear/scene/tgdb/SGVasiDrawable.cxx')
t = open(cxx).read()
if 'SG_GLES2' not in t:
    a = '#include <simgear/scene/util/OsgMath.hxx>\n'
    assert t.count(a) == 1, 'vasi drawable include anchor'
    t = t.replace(a, a + """
/* Under GLES2 there is no immediate mode.  LightData::draw() is not used
   there - SGLightFactory::getVasi hands out geometry instead - but it is
   still compiled. */
#ifdef SG_GLES2
#  define glBegin(a)        ((void)0)
#  define glEnd()           ((void)0)
#  define glColor4fv(a)     ((void)0)
#  define glNormal3fv(a)    ((void)0)
#  define glVertex3fv(a)    ((void)0)
#  ifndef GL_POINTS
#    define GL_POINTS       0
#  endif
#endif
""")
    open(cxx, 'w').write(t)
    print('sg_vasi_gles: GLES stubs for the old drawable added')

# ---- the tile builder puts the lights under the approach light effect ---
# Under GLES that effect's techniques are written for point sprites; a
# triangle drawn with them does not reach the raster (measured: the cull
# callback fills the arrays, the colours are right, nothing appears).  The
# geometry carries everything it needs, so there it goes into a plain geode
# with the ground light state (fog) and the port's fallback shader.
tile = os.path.join(ROOT, 'simgear/scene/tgdb/SGTileDetailsCallback.hxx')
t = open(tile).read()
if 'SGVasiGles' not in t:
    old = """      if (! vasiLights.empty()) {
        EffectGeode* vasiGeode = new EffectGeode;        
        Effect* vasiEffect = getLightEffect(24, osg::Vec3(1, 0.0001, 0.000001), 1, 24, true, _options);
        vasiGeode->setEffect(vasiEffect);"""
    assert t.count(old) == 1, 'vasi geode anchor'
    new = """      if (! vasiLights.empty()) {
#ifdef SG_GLES2
        /* SGVasiGles: no effect - see SGLightFactory::getVasi */
        osg::Geode* vasiGeode = new osg::Geode;
#else
        EffectGeode* vasiGeode = new EffectGeode;        
        Effect* vasiEffect = getLightEffect(24, osg::Vec3(1, 0.0001, 0.000001), 1, 24, true, _options);
        vasiGeode->setEffect(vasiEffect);
#endif"""
    t = t.replace(old, new)
    open(tile, 'w').write(t)
    print('sg_vasi_gles: tile builder patched')
else:
    print('sg_vasi_gles: tile builder already patched')

s = open(pt).read()
if 'SGVasiGles' in s:
    print('sg_vasi_gles: already patched')
    raise SystemExit(0)

# ---- the geometry and its cull callback, in front of buildVasi ----------
anchor = '''static SGVasiDrawable*
buildVasi(const SGDirectionalLightBin& lights, const SGVec3f& up,
       const SGVec4f& red, const SGVec4f& white)
{'''
assert s.count(anchor) == 1, 'buildVasi anchor'

block = '''#ifdef SG_GLES2
/* SGVasiGles: the approach lights as geometry.

   One triangle per light, like SGLightFactory's directional lights: the
   light's position carries the colour, the two other corners the same
   colour with alpha 0.  The colour itself belongs to the moment - red
   below the glide path, white above, nothing at all when the light is
   seen from behind - so a cull callback writes it before every draw, from
   the eye point the cull visitor carries. */
namespace {

struct VasiLight {
  VasiLight(const SGVec3f& p, const SGVec3f& n, const SGVec3f& u) :
    position(p),
    normal(n),
    horizontal(normalize(cross(u, n))),
    normalCrossHorizontal(normalize(cross(n, normalize(cross(u, n)))))
  { }
  SGVec3f position, normal, horizontal, normalCrossHorizontal;
};

class SGVasiGlesCallback : public osg::Drawable::CullCallback {
public:
  SGVasiGlesCallback(const std::vector<VasiLight>& lights,
                     const SGVec4f& red, const SGVec4f& white,
                     osg::Vec3Array* vertices, osg::Vec4Array* colors,
                     osg::Vec2Array* texcoords) :
    _lights(lights), _red(red), _white(white),
    _vertices(vertices), _colors(colors), _texcoords(texcoords)
  { }

  virtual bool cull(osg::NodeVisitor* nv, osg::Drawable*, osg::RenderInfo*) const
  {
    osgUtil::CullVisitor* cv = dynamic_cast<osgUtil::CullVisitor*>(nv);
    if (!cv)
      return false;
    const SGVec3f eye(toSG(osg::Vec3(cv->getEyeLocal())));

    /* How large a light has to be in the world to stay the same size on
       screen.  A light is a metre wide at most in reality and would be
       less than a pixel from a mile out, where an approach light is
       precisely what one wants to see; the desktop gets this from the
       point size, which GLES does not have. */
    osg::Vec3 up(cv->getUpLocal());
    osg::Vec3 look(cv->getLookVectorLocal());
    osg::Vec3 right(look ^ up);
    if (right.length2() < 1e-6)
      return false;
    right.normalize();
    up = right ^ look;
    up.normalize();
    double p11 = cv->getProjectionMatrix() ? (*cv->getProjectionMatrix())(1, 1) : 1.0;
    if (p11 <= 0.0)
      p11 = 1.0;
    double viewportHeight = cv->getViewport() ? cv->getViewport()->height() : 720.0;
    static double pixels = -1.0;
    if (pixels < 0.0) {
      const char* env = ::getenv("SG_VASI_PIXELS");
      pixels = env ? ::atof(env) : 4.0;
      if (pixels <= 0.0) pixels = 12.0;
    }
    const double perMetre = 2.0*pixels/(p11*viewportHeight);

    for (unsigned i = 0; i < _lights.size(); ++i) {
      const VasiLight& light = _lights[i];
      osg::Vec4 color(0, 0, 0, 0);
      SGVec3f lightToEye = eye - light.position;
      if (SGLimitsf::min() <= dot(lightToEye, light.normal)) {
        SGVec3f projLightToEye = lightToEye
          - light.horizontal*dot(lightToEye, light.horizontal);
        float sqrLen = dot(projLightToEye, projLightToEye);
        if (1e-3*1e-3 < sqrLen) {
          float sinAngle = dot(projLightToEye, light.normalCrossHorizontal)/sqrt(sqrLen);
          if (sinAngle < -1) sinAngle = -1;
          if (1 < sinAngle) sinAngle = 1;
          const float angleDeg = SGMiscf::rad2deg(asin(sinAngle));
          /* the same transition as the drawable had: half a tenth of a
             degree of white and red mixed, so the change is not a jump */
          const float transDeg = 0.05f;
          SGVec4f c;
          if (angleDeg < -transDeg)
            c = _red;
          else if (angleDeg < transDeg)
            c = _red + (angleDeg*0.5f/transDeg + 0.5f)*(_white - _red);
          else
            c = _white;
          color.set(c[0], c[1], c[2], c[3]);
        }
      }
      /* a square facing the eye, two triangles, the light's colour all
         over it: a glow fading to the rim came out as a haze of a few
         percent and was not to be seen */
      const osg::Vec3 centre = toOsg(light.position);
      /* Never smaller on screen than a few pixels - a light is a point
         source and stays visible from miles out - but never smaller than
         the thing itself either, so from close up the four units stand
         apart instead of merging into one bar. */
      float size = float(norm(lightToEye)*perMetre);
      const float realSize = 1.2f;
      if (size < realSize)
        size = realSize;
      const osg::Vec3 dx = right*(0.5f*size), dy = up*(0.5f*size);
      const osg::Vec3 corner[4] = { centre - dx - dy, centre + dx - dy,
                                    centre + dx + dy, centre - dx + dy };
      const unsigned order[6] = { 0, 1, 2, 0, 2, 3 };
      const osg::Vec2 uv[4] = { osg::Vec2(0, 0), osg::Vec2(1, 0),
                                osg::Vec2(1, 1), osg::Vec2(0, 1) };
      for (unsigned k = 0; k < 6; ++k) {
        (*_vertices)[i*6 + k] = corner[order[k]];
        (*_colors)[i*6 + k] = color;
        (*_texcoords)[i*6 + k] = uv[order[k]];
      }
    }
    _vertices->dirty();
    _colors->dirty();
    _texcoords->dirty();

    /* SG_VASI_PROBE=1: does this callback run, and with what? */
    static int probe = -1;
    if (probe < 0)
      probe = (::getenv("SG_VASI_PROBE") != 0) ? 1 : 0;
    if (probe) {
      const double now = SGTimeStamp::now().toSecs();
      if (now - _probeLast > 2.0) {
        _probeLast = now;
        const osg::Vec4& c = (*_colors)[0];
        SG_LOG(SG_TERRAIN, SG_ALERT, "VASIGLES " << this << ": " << _lights.size()
               << " lights, " << norm(eye - _lights[0].position) << " m away, size "
               << float(norm(eye - _lights[0].position)*perMetre) << " m, colour "
               << c[0] << "/" << c[1] << "/" << c[2] << " alpha " << c[3]);
      }
    }
    return false;
  }

private:
  std::vector<VasiLight> _lights;
  SGVec4f _red, _white;
  mutable double _probeLast = 0.0;
  osg::ref_ptr<osg::Vec3Array> _vertices;
  osg::ref_ptr<osg::Vec4Array> _colors;
  osg::ref_ptr<osg::Vec2Array> _texcoords;
};

/* The counterpart of buildVasi: the same light arrangement, as geometry. */
osg::Drawable* buildVasiGles(const SGDirectionalLightBin& lights,
                             const SGVec3f& up, const SGVec4f& red,
                             const SGVec4f& white)
{
  const unsigned count = lights.getNumLights();
  std::vector<VasiLight> vasiLights;
  const float papi[4] = { 3.5f, 3.167f, 2.833f, 2.5f };
  for (unsigned i = 0; i < count; ++i) {
    float azimutDeg;
    if (count == 4)
      azimutDeg = papi[i];                       /* PAPI */
    else if (count == 6)
      azimutDeg = (i < 3) ? 2.5f : 3.0f;         /* VASI, three a bar */
    else if (count == 12)
      azimutDeg = (i < 6) ? 2.5f : 3.0f;         /* VASI, six a bar */
    else
      return 0;                                  /* unknown arrangement */
    const SGVec3f position = lights.getLight(i).position;
    const SGVec3f normal = lights.getLight(i).normal;
    SGVec3f horizontal(normalize(cross(up, normal)));
    SGVec3f zeroGlideSlope = normalize(cross(horizontal, up));
    SGQuatf rotation = SGQuatf::fromAngleAxisDeg(azimutDeg, horizontal);
    vasiLights.push_back(VasiLight(position, rotation.transform(zeroGlideSlope), up));
  }
  if (vasiLights.empty())
    return 0;

  /* six vertices a light: a square of two triangles, filled in by the
     cull callback, which is the only place that knows where the eye is */
  osg::Vec3Array* vertices = new osg::Vec3Array(vasiLights.size()*6);
  osg::Vec4Array* colors = new osg::Vec4Array(vasiLights.size()*6);
  osg::Vec2Array* texcoords = new osg::Vec2Array(vasiLights.size()*6);
  for (unsigned i = 0; i < vasiLights.size(); ++i)
    for (unsigned k = 0; k < 6; ++k) {
      (*vertices)[i*6 + k] = toOsg(vasiLights[i].position);
      (*colors)[i*6 + k] = osg::Vec4(0, 0, 0, 0);
    }

  osg::Geometry* geometry = new osg::Geometry;
  geometry->setDataVariance(osg::Object::DYNAMIC);
  geometry->setUseDisplayList(false);
  geometry->setVertexArray(vertices);
  geometry->setNormalBinding(osg::Geometry::BIND_OFF);
  geometry->setColorArray(colors, osg::Array::BIND_PER_VERTEX);
  geometry->setTexCoordArray(0, texcoords, osg::Array::BIND_PER_VERTEX);

  /* A round light, not a square: a small texture with a soft edge, the
     same thing the point sprite gave the desktop.  Built once and shared;
     the fallback shader of the GLES port multiplies it with the vertex
     colour. */
  {
    static osg::ref_ptr<osg::Texture2D> sprite;
    if (!sprite.valid()) {
      const int n = 32;
      osg::Image* image = new osg::Image;
      image->allocateImage(n, n, 1, GL_RGBA, GL_UNSIGNED_BYTE);
      unsigned char* p = image->data();
      for (int y = 0; y < n; ++y) {
        for (int x = 0; x < n; ++x) {
          const double dx = (x + 0.5)/n - 0.5, dy = (y + 0.5)/n - 0.5;
          const double r = 2.0*sqrt(dx*dx + dy*dy);       /* 0 centre, 1 rim */
          double a = 1.0 - (r - 0.55)/0.45;               /* solid core, soft edge */
          if (a > 1.0) a = 1.0;
          if (a < 0.0) a = 0.0;
          *p++ = 255; *p++ = 255; *p++ = 255;
          *p++ = (unsigned char)(255.0*a);
        }
      }
      sprite = new osg::Texture2D(image);
      sprite->setFilter(osg::Texture::MIN_FILTER, osg::Texture::LINEAR);
      sprite->setFilter(osg::Texture::MAG_FILTER, osg::Texture::LINEAR);
      sprite->setWrap(osg::Texture::WRAP_S, osg::Texture::CLAMP_TO_EDGE);
      sprite->setWrap(osg::Texture::WRAP_T, osg::Texture::CLAMP_TO_EDGE);
    }
    osg::StateSet* ss = geometry->getOrCreateStateSet();
    ss->setTextureAttributeAndModes(0, sprite.get(), osg::StateAttribute::ON);
    ss->setMode(GL_BLEND, osg::StateAttribute::ON);
    ss->setAttributeAndModes(new osg::BlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA));
    ss->setAttributeAndModes(new osg::Depth(osg::Depth::LESS, 0.0, 1.0, false));
    ss->setRenderBinDetails(POINT_LIGHTS_BIN, "DepthSortedBin");
  }
  geometry->setComputeBoundingBoxCallback(new SGEnlargeBoundingBox(1));
  geometry->addPrimitiveSet(new osg::DrawArrays(osg::PrimitiveSet::TRIANGLES,
                                                0, vertices->size()));
  geometry->setCullCallback(new SGVasiGlesCallback(vasiLights, red, white,
                                                   vertices, colors, texcoords));
  return geometry;
}

}  // namespace
#endif

'''
s = s.replace(anchor, block + anchor)

# ---- getVasi hands out the geometry under GLES -------------------------
old = '''  SGVasiDrawable* drawable = buildVasi(lights, up, red, white);
  if (!drawable)
    return 0;

  osg::StateSet* stateSet = drawable->getOrCreateStateSet();'''
new = '''#ifdef SG_GLES2
  osg::Drawable* drawable = buildVasiGles(lights, up, red, white);
  if (!drawable) {
    SG_LOG(SG_TERRAIN, SG_ALERT,
           "unknown vasi/papi configuration, count = " << lights.getNumLights());
    return 0;
  }
#else
  SGVasiDrawable* drawable = buildVasi(lights, up, red, white);
  if (!drawable)
    return 0;
#endif

  osg::StateSet* stateSet = drawable->getOrCreateStateSet();'''
assert s.count(old) == 1, 'getVasi anchor'
s = s.replace(old, new)

# ---- the includes the callback needs -----------------------------------
old = '#include "SGVasiDrawable.hxx"'
assert s.count(old) == 1, 'include anchor'
s = s.replace(old, old + '''
#ifdef SG_GLES2
#include <osgUtil/CullVisitor>
#include <osg/Texture2D>
#include <osg/Image>
#include <osg/BlendFunc>
#include <osg/Depth>
#include <simgear/scene/util/SGEnlargeBoundingBox.hxx>
#include <simgear/timing/timestamp.hxx>
#endif''')

open(pt, 'w').write(s)
print('sg_vasi_gles: pt_lights.cxx patched')

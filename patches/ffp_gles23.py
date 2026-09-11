#!/usr/bin/env python3
"""Twenty-third round (FlightGear GLES port): find a drawable by its texture.

The bigGeom probe logs the first twelve drawables above a vertex count, which
under a running FlightGear are always terrain tiles - the c172p's instrument
faces never showed up.  It now also prints the texture bound to unit 0 and
can be limited to drawables whose texture name contains a string:

  OSG_GLES_DEBUG_TEXNAME=AI.png   only drawables using that texture
  OSG_GLES_DEBUG_MAXLOG=40        how many lines to write (default 12)

That answers the open question about the black instrument faces directly:
whether those drawables carry texture coordinates at all.

Run after ffp_gles.py .. ffp_gles22.py: python3 ffp_gles23.py [osg-source-root]"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'

p = os.path.join(ROOT, 'src/osg/Geometry.cpp')
s = open(p).read()

if 'draw time - the effect puts' in s:
    print('  schon aktuell')
    raise SystemExit

# eine ältere Fassung dieser Sonde ersetzen, falls vorhanden
if 'OSG_GLES_DEBUG_TEXNAME' in s:
    i = s.index('        /* Which texture is on unit 0?')
    j = s.index('if (wanted && *wanted', i)
    j = s.index('\n', j) + 1
    s = s[:i] + s[j:]
    s = s.replace('<< " name=[" << getName() << "]"\n               << " tex=[" << texName << "]";',
                  '<< " name=[" << getName() << "]";')
    s = s.replace('if (logged < maxLog', 'if (logged < 12')
    print('alte Fassung entfernt')

old = '''            const char* a = getenv("OSG_GLES_DEBUG_AFTER");
            const char* m = getenv("OSG_GLES_DEBUG_MINVERTS");
            after = (a && *a) ? atof(a) : 0.0;
            minVerts = (m && *m) ? atoi(m) : 500;
        }
'''
new = '''            const char* a = getenv("OSG_GLES_DEBUG_AFTER");
            const char* m = getenv("OSG_GLES_DEBUG_MINVERTS");
            after = (a && *a) ? atof(a) : 0.0;
            minVerts = (m && *m) ? atoi(m) : 500;
        }
        /* Which texture is on unit 0?  Lets the probe find a particular
           drawable - the instrument faces are small and drawn among
           thousands of others. */
        std::string texName;
        {
            /* What is actually bound on unit 0 at draw time - the effect puts
               the texture on the pass state set, not on the drawable. */
            const osg::StateAttribute* sa =
                state.getLastAppliedTextureAttribute(0, osg::StateAttribute::TEXTURE);
            const osg::Texture* t = dynamic_cast<const osg::Texture*>(sa);
            const osg::Image* img = t ? t->getImage(0) : 0;
            if (img) texName = img->getFileName();
            std::string::size_type sl = texName.find_last_of('/');
            if (sl != std::string::npos) texName = texName.substr(sl + 1);
        }
        static const char* wanted = getenv("OSG_GLES_DEBUG_TEXNAME");
        static const int maxLog = (getenv("OSG_GLES_DEBUG_MAXLOG") && *getenv("OSG_GLES_DEBUG_MAXLOG"))
                                  ? atoi(getenv("OSG_GLES_DEBUG_MAXLOG")) : 12;
        if (wanted && *wanted && texName.find(wanted) == std::string::npos) return;
'''
assert s.count(old) == 1, 'Anker Sondenkopf'
s = s.replace(old, new)

old2 = '''        if (logged < 12 && numVerts >= minVerts &&
'''
new2 = '''        if (logged < maxLog && numVerts >= minVerts &&
'''
assert s.count(old2) == 1, 'Anker Zaehler'
s = s.replace(old2, new2)

old3 = '''            os << "bigGeom verts=" << numVerts << " name=[" << getName() << "]";
'''
new3 = '''            os << "bigGeom verts=" << numVerts << " name=[" << getName() << "]"
               << " tex=[" << texName << "]";
'''
assert s.count(old3) == 1, 'Anker Ausgabe'
s = s.replace(old3, new3)
open(p, 'w').write(s)
print('geaendert src/osg/Geometry.cpp')
print('fertig')

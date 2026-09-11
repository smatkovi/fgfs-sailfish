#!/usr/bin/env python3
"""Twenty-seventh round: write the converted shaders out.

The instrument faces have their texture, their coordinates and an enabled
attribute - GL confirms slot 3 is on - so what turns them black happens
inside the fragment shader.  With OSG_GLES_DUMP_SHADERS set to a directory,
every shader that goes through the GLES conversion is written there, before
and after, so the code that actually runs on the device can be read.

Files are named by a hash of the source, so a shader is written once.

Run after ffp_gles.py .. ffp_gles26.py: python3 ffp_gles27.py [osg-source-root]"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 else '/home/mersdk/OpenSceneGraph-OpenSceneGraph-3.6.5'

p = os.path.join(ROOT, 'src/osg/State.cpp')
s = open(p).read()

if 'OSG_GLES_DUMP_SHADERS' in s:
    print('  schon aktuell')
    raise SystemExit

old = '''    source = osg_gles::convert(source, type == Shader::VERTEX, aliases, es3);
    return true;
}
'''
new = '''    const std::string before = source;
    source = osg_gles::convert(source, type == Shader::VERTEX, aliases, es3);

    /* FlightGear GLES port: OSG_GLES_DUMP_SHADERS=<dir> writes what goes in
       and what comes out, so the code running on the device can be read. */
    {
        static const char* dir = ::getenv("OSG_GLES_DUMP_SHADERS");
        if (dir && *dir)
        {
            const char* ext = (type == Shader::VERTEX) ? "vert" : "frag";
            unsigned long h = 5381;
            for (std::string::size_type i = 0; i < before.size(); ++i)
                h = ((h << 5) + h) + (unsigned char)before[i];
            char name[512];
            snprintf(name, sizeof name, "%s/%08lx.%s", dir, h & 0xffffffffUL, ext);
            FILE* f = fopen(name, "wx");
            if (f)
            {
                fputs("/* ---- converted ---- */\\n", f);
                fputs(source.c_str(), f);
                fputs("\\n/* ---- original ---- */\\n", f);
                fputs(before.c_str(), f);
                fclose(f);
                OSG_WARN << "DUMPSHADER " << name << std::endl;
            }
        }
    }
    return true;
}
'''
assert s.count(old) == 1, 'Anker'
s = s.replace(old, new)
open(p, 'w').write(s)
print('geaendert src/osg/State.cpp')
print('fertig')

#!/usr/bin/env python3
"""SimGear probe: why does the effect fall back to the white texture?

makeParametersFromStateSet reads the model's texture out of the StateSet and
writes type="white" when texture->getImage() is null - that is what the
instrument faces get, as the OSG_GLES_DEBUG_TEXEL probe showed.  Log which
branch is taken, with what texture class and image, under
SG_TEXPARAM_PROBE=1.

  python3 sg_texparam_probe.py [simgear-source-root]
"""
import os
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/simgear-2020.3.19')
p = os.path.join(ROOT, 'simgear/scene/material/TextureBuilder.cxx')
s = open(p).read()

if 'TEXPARAM' in s:
    print('  schon aktuell')
    raise SystemExit

lines = s.split('\n')
# the branch that writes type="white"
k = next(i for i, l in enumerate(lines) if 'makeChild(texUnit, "type")->setValue("white")' in i and False) if False else None
k = next(i for i, l in enumerate(lines) if '"type")->setValue("white")' in l)
# find the enclosing "const Image* image = texture->getImage();"
g = max(i for i, l in enumerate(lines) if i < k and 'texture->getImage()' in l)
indent = ' ' * (len(lines[g]) - len(lines[g].lstrip()))
lines.insert(g + 1, indent + '''{
%(i)s    static const int probe = (::getenv("SG_TEXPARAM_PROBE") != 0) ? 1 : 0;
%(i)s    if (probe)
%(i)s        SG_LOG(SG_INPUT, SG_ALERT, "TEXPARAM unit=" << unit
%(i)s               << " class=" << (texture ? texture->className() : "none")
%(i)s               << " image=" << (image ? "yes" : "NULL")
%(i)s               << " file=[" << (image ? image->getFileName() : std::string()) << "]"
%(i)s               << " s=" << (image ? image->s() : -1)
%(i)s               << " data=" << (image && image->data() ? "yes" : "no"));
%(i)s}''' % {'i': indent})
s = '\n'.join(lines)
open(p, 'w').write(s)
print('geaendert TextureBuilder.cxx: Sonde an der weissen Ersatztextur')

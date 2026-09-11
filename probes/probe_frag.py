#!/usr/bin/env python3
"""Idempotently install a diagnostic probe into a GLSL fragment shader.

Purpose (see BEFUNDE.md, entry B1): the three recorded observations
"reads texcoord (0,0)", "texel at (0,0) is bright" and "the face is
black" cannot all be true at once. This script installs the probes that
separate them, one concern at a time:

  const     constant colour           -> does the fragment path run for
                                         this surface at all?
  tex05     sample at fixed vec2(0.5) -> does the *bound texture* return
                                         anything other than black,
                                         independent of any coordinate?
  texcoord  fract(texcoord) as colour -> only meaningful once the two
                                         above are answered.
  restore   put the original file back.

'const' and 'tex05' are the discriminating pair. If 'const' shows colour
but 'tex05' stays black, the texture is at fault and the coordinate
trail is a red herring. If 'tex05' shows the texel, the coordinate is
back in play. Running 'texcoord' first -- as was done before -- cannot
tell these apart, because fract() maps every integral coordinate onto 0
and so makes "no coordinate" look identical to "tiled coordinate".

The probe is written as a marked block immediately before the closing
brace of main(), so it overrides whatever the shader computed. Re-running
replaces the previous block rather than stacking a second one, and the
pristine file is kept as <file>.orig.

Usage:
    probe_frag.py <path-to-.frag> const|tex05|texcoord|restore
"""

import os
import re
import shutil
import sys

BEGIN = "// ---- BEGIN fgfs probe (probe_frag.py) ----"
END = "// ---- END fgfs probe (probe_frag.py) ----"

# Samplers whose name suggests the base colour map, most specific first.
SAMPLER_PREFERENCE = (
    "texture0", "baseTexture", "colorTexture", "diffuseTexture",
    "tex0", "texture", "tex",
)


def die(msg):
    sys.stderr.write("probe_frag: %s\n" % msg)
    raise SystemExit(1)


def find_main_close(src):
    """Return the index of the closing brace of main(), or None."""
    m = re.search(r"\bvoid\s+main\s*\([^)]*\)\s*\{", src)
    if not m:
        return None
    depth = 0
    i = m.end() - 1          # position of the opening brace
    while i < len(src):
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def find_output_var(src):
    """Name of the fragment output: gl_FragColor, or a declared out var."""
    if "gl_FragColor" in src:
        return "gl_FragColor"
    m = re.search(r"^\s*out\s+(?:highp\s+|mediump\s+|lowp\s+)?vec4\s+(\w+)\s*;",
                  src, re.M)
    if m:
        return m.group(1)
    return None


def find_sampler(src):
    """Name of the most likely base-colour sampler2D uniform."""
    names = re.findall(
        r"^\s*uniform\s+(?:highp\s+|mediump\s+|lowp\s+)?sampler2D\s+(\w+)\s*;",
        src, re.M)
    if not names:
        return None, names
    for want in SAMPLER_PREFERENCE:
        for n in names:
            if n == want:
                return n, names
    for want in SAMPLER_PREFERENCE:
        for n in names:
            if want.lower() in n.lower():
                return n, names
    return names[0], names


def sample_call(src, sampler, coord):
    """texture() in ES3/GLSL150, texture2D() in ES2 -- match the file."""
    if re.search(r"\btexture2D\s*\(", src):
        return "texture2D(%s, %s)" % (sampler, coord)
    return "texture(%s, %s)" % (sampler, coord)


def strip_probe(src):
    """Remove a previously installed block. This is what makes it idempotent."""
    pattern = re.compile(
        re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", re.S)
    return pattern.sub("", src)


def build_block(mode, src, outvar):
    lines = [BEGIN]
    if mode == "const":
        # Deliberately not red/black: must be unmistakable against both a
        # working dial and the black failure.
        lines.append("    %s = vec4(0.0, 1.0, 0.0, 1.0);" % outvar)
    elif mode == "tex05":
        sampler, all_names = find_sampler(src)
        if not sampler:
            die("no sampler2D uniform found -- cannot build the tex05 probe")
        sys.stderr.write("probe_frag: samplers seen: %s -> using '%s'\n"
                         % (", ".join(all_names), sampler))
        call = sample_call(src, sampler, "vec2(0.5, 0.5)")
        lines.append("    %s = vec4(%s.rgb, 1.0);" % (outvar, call))
    elif mode == "texcoord":
        # Kept for completeness; see the caveat in the module docstring.
        lines.append("    %s = vec4(fract(osg_TexCoord[0].st), 0.0, 1.0);"
                     % outvar)
    else:
        die("unknown mode '%s'" % mode)
    lines.append(END)
    return "\n".join(lines) + "\n"


def main(argv):
    if len(argv) != 3:
        die("usage: probe_frag.py <path-to-.frag> const|tex05|texcoord|restore")
    path, mode = argv[1], argv[2]
    if not os.path.isfile(path):
        die("no such file: %s" % path)
    orig = path + ".orig"

    # The pristine copy is made once, from a file that has never been
    # probed -- otherwise a probe would be frozen into the backup.
    if not os.path.exists(orig):
        with open(path, "r") as f:
            if BEGIN in f.read():
                die("%s already contains a probe but %s is missing; "
                    "restore that file by hand before continuing"
                    % (path, orig))
        shutil.copy2(path, orig)
        sys.stderr.write("probe_frag: saved pristine copy to %s\n" % orig)

    if mode == "restore":
        shutil.copy2(orig, path)
        sys.stderr.write("probe_frag: restored %s from %s\n" % (path, orig))
        return 0

    with open(path, "r") as f:
        src = f.read()

    src = strip_probe(src)

    outvar = find_output_var(src)
    if not outvar:
        die("could not determine the fragment output variable "
            "(neither gl_FragColor nor a declared 'out vec4')")

    close = find_main_close(src)
    if close is None:
        die("could not locate the closing brace of main()")

    block = build_block(mode, src, outvar)
    out = src[:close] + block + src[close:]

    with open(path, "w") as f:
        f.write(out)

    sys.stderr.write("probe_frag: installed '%s' probe in %s (output '%s')\n"
                     % (mode, path, outvar))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

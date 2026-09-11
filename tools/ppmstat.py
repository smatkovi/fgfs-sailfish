#!/usr/bin/env python3
"""Summarise a PPM as text, so a rendered image can be judged without viewing it.

Written for the black-dial investigation (BEFUNDE.md): the questions we
need answered about osg-model-test output are all statistical, not
visual --

  * is the surface a single flat colour, or does it vary?
      A flat colour is the signature of a *constant* vertex attribute;
      a gradient means the coordinate is being interpolated properly.
  * is it black, or merely dark?
      Distinguishes "texture returned nothing" from "lit to near-zero".
  * in 'tc' mode, does red/green vary across the image?
      Red carries u, green carries v. A channel that is constant while
      the other varies localises the fault to one coordinate.

Usage:
    ppmstat.py <file.ppm> [more.ppm ...]
"""

import collections
import sys


def die(msg):
    sys.stderr.write("ppmstat: %s\n" % msg)
    raise SystemExit(1)


def read_token(data, pos):
    """Read one whitespace-delimited PPM header token, skipping # comments."""
    while pos < len(data):
        c = data[pos:pos + 1]
        if c == b"#":
            while pos < len(data) and data[pos:pos + 1] not in (b"\n", b"\r"):
                pos += 1
        elif c.isspace():
            pos += 1
        else:
            break
    start = pos
    while pos < len(data) and not data[pos:pos + 1].isspace():
        pos += 1
    return data[start:pos], pos


def load_ppm(path):
    with open(path, "rb") as f:
        data = f.read()
    if len(data) < 2:
        die("%s: too short to be a PPM" % path)
    magic = data[:2]
    if magic not in (b"P6", b"P3"):
        die("%s: not a PPM (magic %r)" % (path, magic))

    pos = 2
    w, pos = read_token(data, pos)
    h, pos = read_token(data, pos)
    maxv, pos = read_token(data, pos)
    try:
        w, h, maxv = int(w), int(h), int(maxv)
    except ValueError:
        die("%s: unreadable header" % path)
    if maxv != 255:
        die("%s: only 8-bit PPMs supported (maxval %d)" % (path, maxv))

    if magic == b"P6":
        pos += 1                      # exactly one whitespace byte follows
        need = w * h * 3
        px = data[pos:pos + need]
        if len(px) < need:
            die("%s: truncated (%d of %d bytes)" % (path, len(px), need))
        return w, h, px

    vals = data[pos:].split()
    if len(vals) < w * h * 3:
        die("%s: truncated P3 data" % path)
    return w, h, bytes(int(v) for v in vals[:w * h * 3])


def pixel(px, w, x, y):
    i = (y * w + x) * 3
    return px[i], px[i + 1], px[i + 2]


def describe(path):
    w, h, px = load_ppm(path)
    n = w * h

    counts = collections.Counter()
    for i in range(0, n * 3, 3):
        counts[(px[i], px[i + 1], px[i + 2])] += 1

    print("== %s  (%dx%d, %d px)" % (path, w, h, n))

    # Flat or varying -- the single most important question.
    uniq = len(counts)
    top = counts.most_common(5)
    dominant, dom_n = top[0]
    print("   distinct colours : %d" % uniq)
    print("   dominant         : rgb%s  %.1f%% of image" % (dominant, 100.0 * dom_n / n))
    if uniq == 1:
        print("   -> COMPLETELY FLAT. Could be a constant vertex attribute --")
        print("      but could equally be the clear colour with nothing drawn.")
        print("      Compare against another render mode before concluding.")
    elif 100.0 * dom_n / n > 95.0:
        print("   -> effectively flat (>95%% one colour); the rest is probably background/edges")

    # Per-channel spread, ignoring pure background black if it dominates.
    for ch, name in ((0, "R (u)"), (1, "G (v)"), (2, "B    ")):
        vals = [px[i + ch] for i in range(0, n * 3, 3)]
        lo, hi = min(vals), max(vals)
        print("   %s range      : %3d..%3d  %s" % (
            name, lo, hi, "CONSTANT" if lo == hi else "varies"))

    print("   top colours      : %s" % ", ".join(
        "rgb%s x%d" % (c, k) for c, k in top))

    # Black vs merely dark -- separates "no texture" from "lit to zero".
    black = counts.get((0, 0, 0), 0)
    verydark = sum(k for c, k in counts.items() if max(c) <= 8 and c != (0, 0, 0))
    print("   pure black       : %.1f%%   near-black(<=8): %.1f%%"
          % (100.0 * black / n, 100.0 * verydark / n))

    # A coarse 5x5 probe grid gives a sense of layout without an image.
    print("   5x5 grid:")
    for gy in range(5):
        y = min(h - 1, (2 * gy + 1) * h // 10)
        row = []
        for gx in range(5):
            x = min(w - 1, (2 * gx + 1) * w // 10)
            row.append("%3d,%3d,%3d" % pixel(px, w, x, y))
        print("     " + " | ".join(row))
    print("")
    return {"path": path, "uniq": uniq, "dominant": dominant, "bytes": px}


def compare(reports):
    """Cross-check renders against each other.

    Two different fragment programs that produce byte-identical images
    have not drawn anything -- both are showing the clear colour. This
    check exists because the per-image summary alone reads as "flat, so
    the attribute must be constant", which is a trap: the flat case is
    far more often "nothing was drawn at all". See BEFUNDE.md, B3.
    """
    if len(reports) < 2:
        return
    print("================ CROSS-CHECK ================")
    first = reports[0]
    identical = [r for r in reports[1:] if r["bytes"] == first["bytes"]]
    if len(identical) == len(reports) - 1:
        print("!! ALL RENDERS ARE BYTE-IDENTICAL.")
        print("!! Different render modes cannot produce the same image if")
        print("!! geometry is being drawn. Nothing was rendered -- what you")
        print("!! are looking at is the clear colour rgb%s."
              % (first["dominant"],))
        print("!! Fix the harness before drawing any conclusion about")
        print("!! texture coordinates: this image says nothing about them.")
    else:
        print("Renders differ from each other -- geometry is being drawn,")
        print("so the per-image summaries above are meaningful.")
    print("")


def main(argv):
    if len(argv) < 2:
        die("usage: ppmstat.py <file.ppm> [more.ppm ...]")
    reports = [describe(p) for p in argv[1:]]
    compare(reports)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

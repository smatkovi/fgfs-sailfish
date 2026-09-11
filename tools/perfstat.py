#!/usr/bin/env python3
"""Summarise FGFS_GLES_TIMING output as medians.

The timing lines come in two shapes, because the instrumentation sits in two
places in Renderer.cpp:

  draw-thread path (DrawThreadPerContext):
    "... (draw thread): draw D ms, frame F ms (rest R ms outside draw)"
    cull runs on the other thread and is invisible here, so R covers the
    whole app-plus-cull pipeline.

  single-threaded path:
    "... : cull C ms, draw D ms, frame F ms (rest R ms outside cull and draw)"
    plus a second line with per-frame mode/attribute/drawable counts.

Medians, not means: scenery paging and shader compilation produce occasional
frames of several hundred milliseconds, and a mean over a window that
contains one of those says more about the outlier than about the steady
state. The spread is reported separately so the outliers stay visible
instead of being silently discarded.

Usage:
    perfstat.py <logfile> [more logs ...]
"""

import re
import sys

RE_DRAWTHREAD = re.compile(
    r"draw thread\):\s*draw\s+([0-9.eE+-]+)\s*ms,\s*frame\s+([0-9.eE+-]+)\s*ms"
    r"\s*\(rest\s+([0-9.eE+-]+)")
RE_SINGLE = re.compile(
    r"frames:\s*cull\s+([0-9.eE+-]+)\s*ms,\s*draw\s+([0-9.eE+-]+)\s*ms,"
    r"\s*frame\s+([0-9.eE+-]+)\s*ms\s*\(rest\s+([0-9.eE+-]+)")
RE_COUNTS = re.compile(
    r"per frame:\s*modes\s+(\d+),\s*attributes\s+(\d+),\s*drawables\s+(\d+)")


def median(v):
    if not v:
        return None
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def fmt(name, vals, width=9):
    if not vals:
        return None
    m = median(vals)
    return ("   %-7s %*.2f ms   (min %.2f, max %.2f, n=%d)"
            % (name, width, m, min(vals), max(vals), len(vals)))


def describe(path):
    cull, draw, frame, rest = [], [], [], []
    modes = attribs = drawables = None
    try:
        text = open(path, errors="replace").read()
    except OSError as e:
        print("   cannot read %s: %s" % (path, e))
        return

    for line in text.splitlines():
        m = RE_DRAWTHREAD.search(line)
        if m:
            draw.append(float(m.group(1)))
            frame.append(float(m.group(2)))
            rest.append(float(m.group(3)))
            continue
        m = RE_SINGLE.search(line)
        if m:
            cull.append(float(m.group(1)))
            draw.append(float(m.group(2)))
            frame.append(float(m.group(3)))
            rest.append(float(m.group(4)))
            continue
        m = RE_COUNTS.search(line)
        if m:
            modes, attribs, drawables = (int(m.group(1)), int(m.group(2)),
                                         int(m.group(3)))

    if not frame:
        print("   no timing lines found in %s" % path)
        print("   (FGFS_GLES_TIMING=1 set? did the window catch any output?)")
        return

    for name, vals in (("cull", cull), ("draw", draw),
                       ("rest", rest), ("frame", frame)):
        line = fmt(name, vals)
        if line:
            print(line)

    # The series matters as much as the median: a run that is 22 ms with
    # occasional 400 ms spikes is a different problem from one that is
    # uniformly 60 ms, and a median alone cannot tell them apart.
    print("   frame series: " + " ".join("%.0f" % v for v in frame))

    f = median(frame)
    if f and f > 0:
        print("   -> %.1f fps at the median frame" % (1000.0 / f))

    steady = [v for v in frame if v < 2.5 * f] if f else []
    if steady and len(steady) != len(frame):
        ms = median(steady)
        print("   steady state (spikes over 2.5x median dropped): %.2f ms"
              " -> %.1f fps, %d of %d samples"
              % (ms, 1000.0 / ms, len(steady), len(frame)))
    if modes is not None:
        print("   per frame: modes %d, attributes %d, drawables %d"
              % (modes, attribs, drawables))

    # Where the time actually is, as a share -- the number that decides what
    # is worth optimising.
    if f:
        parts = []
        if cull:
            parts.append("cull %.0f%%" % (100.0 * median(cull) / f))
        if draw:
            parts.append("draw %.0f%%" % (100.0 * median(draw) / f))
        if rest:
            parts.append("rest %.0f%%" % (100.0 * median(rest) / f))
        print("   share: " + ", ".join(parts))


def main(argv):
    if len(argv) < 2:
        sys.stderr.write("usage: perfstat.py <logfile> [more ...]\n")
        return 1
    for p in argv[1:]:
        if len(argv) > 2:
            print("== %s" % p)
        describe(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

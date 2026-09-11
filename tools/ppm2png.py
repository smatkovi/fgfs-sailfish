#!/usr/bin/env python3
"""Convert a PPM to PNG, optionally cropping and scaling.

There is no PIL on the phone, but a PNG is just zlib-deflated scanlines
with a filter byte in front of each, so the encoder fits in a few lines.
This exists so a rendered frame can actually be looked at rather than only
counted -- for the instrument panel, "is the dial black" is a question
about a small region of a large frame.

Usage:
    ppm2png.py <in.ppm> <out.png> [x,y,w,h] [scale]
"""

import struct
import sys
import zlib


def die(msg):
    sys.stderr.write("ppm2png: %s\n" % msg)
    raise SystemExit(1)


def read_token(data, pos):
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
    if data[:2] != b"P6":
        die("%s: only binary P6 PPM supported (magic %r)" % (path, data[:2]))
    pos = 2
    w, pos = read_token(data, pos)
    h, pos = read_token(data, pos)
    maxv, pos = read_token(data, pos)
    w, h, maxv = int(w), int(h), int(maxv)
    if maxv != 255:
        die("%s: maxval %d unsupported" % (path, maxv))
    pos += 1
    return w, h, data[pos:pos + w * h * 3]


def chunk(tag, payload):
    return (struct.pack(">I", len(payload)) + tag + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))


def write_png(path, w, h, rows):
    raw = b"".join(b"\x00" + r for r in rows)     # filter type 0 per scanline
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 6))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


def main(argv):
    if len(argv) < 3:
        die("usage: ppm2png.py <in.ppm> <out.png> [x,y,w,h] [scale]")
    src, dst = argv[1], argv[2]
    w, h, px = load_ppm(src)

    x0, y0, cw, ch = 0, 0, w, h
    if len(argv) > 3 and argv[3] != "-":
        try:
            x0, y0, cw, ch = [int(v) for v in argv[3].split(",")]
        except ValueError:
            die("crop must be x,y,w,h")
        x0 = max(0, min(x0, w - 1))
        y0 = max(0, min(y0, h - 1))
        cw = max(1, min(cw, w - x0))
        ch = max(1, min(ch, h - y0))

    scale = int(argv[4]) if len(argv) > 4 else 1
    if scale < 1:
        scale = 1

    rows = []
    for y in range(y0, y0 + ch):
        base = (y * w + x0) * 3
        line = px[base:base + cw * 3]
        if scale > 1:
            out = bytearray()
            for x in range(cw):
                out += line[x * 3:x * 3 + 3] * scale
            line = bytes(out)
        for _ in range(scale):
            rows.append(line)

    write_png(dst, cw * scale, ch * scale, rows)
    print("wrote %s (%dx%d from %dx%d at %d,%d)"
          % (dst, cw * scale, ch * scale, w, h, x0, y0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

#!/usr/bin/env python3
"""Region statistics of a PNG without PIL: mean colour and colourfulness per
cell of a grid, so two screenshots of the same view can be compared by
number.  python3 pngstat.py <file.png> [cols rows]"""
import sys, zlib, struct

def read_png(path):
    d = open(path, 'rb').read()
    assert d[:8] == b'\x89PNG\r\n\x1a\n', 'kein PNG'
    pos, idat, w, h, ct, bd = 8, b'', 0, 0, 0, 0
    while pos < len(d):
        n, = struct.unpack('>I', d[pos:pos+4]); typ = d[pos+4:pos+8]; body = d[pos+8:pos+8+n]
        if typ == b'IHDR': w, h, bd, ct = struct.unpack('>IIBB', body[:10])
        elif typ == b'IDAT': idat += body
        elif typ == b'IEND': break
        pos += 12 + n
    assert bd == 8 and ct in (2, 6), 'nur RGB/RGBA 8 bit (ct=%d bd=%d)' % (ct, bd)
    bpp = 3 if ct == 2 else 4
    raw = zlib.decompress(idat)
    stride = w * bpp
    rows, prev = [], bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]; line = bytearray(raw[p+1:p+1+stride]); p += 1 + stride
        if f == 1:
            for i in range(bpp, stride): line[i] = (line[i] + line[i-bpp]) & 255
        elif f == 2:
            for i in range(stride): line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride): line[i] = (line[i] + ((line[i-bpp] if i >= bpp else 0) + prev[i]) // 2) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i-bpp] if i >= bpp else 0; b = prev[i]; c = prev[i-bpp] if i >= bpp else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2*c)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        rows.append(line); prev = line
    return w, h, bpp, rows

def main():
    path = sys.argv[1]; cols = int(sys.argv[2]) if len(sys.argv) > 2 else 6; rws = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    w, h, bpp, rows = read_png(path)
    print('%s: %dx%d' % (path, w, h))
    for cy in range(rws):
        line = []
        for cx in range(cols):
            x0, x1 = w*cx//cols, w*(cx+1)//cols; y0, y1 = h*cy//rws, h*(cy+1)//rws
            n = sr = sg = sb = 0; sat = 0
            for y in range(y0, y1, 2):
                r = rows[y]
                for x in range(x0, x1, 2):
                    R, G, B = r[x*bpp], r[x*bpp+1], r[x*bpp+2]
                    sr += R; sg += G; sb += B; sat += max(R, G, B) - min(R, G, B); n += 1
            line.append('%3d,%3d,%3d s%3d' % (sr//n, sg//n, sb//n, sat//n))
        print('  ' + ' | '.join(line))

if __name__ == '__main__': main()

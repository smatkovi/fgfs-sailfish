#!/usr/bin/env python3
"""Dump the simulator's current frame from /dev/shm/fgfs-frame to a PNG,
the same way harbour-fgview reads it (48-byte header, two RGBA slots,
seqlock).  python3 shmdump.py out.png [--flip]"""
import sys, struct, zlib, mmap, os

out = sys.argv[1] if len(sys.argv) > 1 else '/tmp/frame.png'
flip = '--flip' in sys.argv
fd = os.open('/dev/shm/fgfs-frame', os.O_RDONLY)
mm = mmap.mmap(fd, 0, prot=mmap.PROT_READ)
magic, w, h, bpp, seq, slot = struct.unpack_from('<IIIIQI', mm, 0)
assert magic == 0x46474652, 'kein fgfs-frame'
n = w * h * 4
for attempt in range(5):
    s1 = struct.unpack_from('<Q', mm, 16)[0]
    slot = struct.unpack_from('<I', mm, 24)[0]
    data = bytes(mm[48 + slot * n: 48 + slot * n + n])
    s2 = struct.unpack_from('<Q', mm, 16)[0]
    if s1 == s2: break
rows = []
for y in range(h):
    yy = h - 1 - y if flip else y
    line = data[yy * w * 4:(yy + 1) * w * 4]
    rgb = bytearray(w * 3)
    rgb[0::3] = line[0::4]; rgb[1::3] = line[1::4]; rgb[2::3] = line[2::4]
    rows.append(b'\x00' + bytes(rgb))
def chunk(t, b): return struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b) & 0xffffffff)
png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(b''.join(rows), 6)) + chunk(b'IEND', b'')
open(out, 'wb').write(png)
print('%s: %dx%d bpp=%d seq=%d slot=%d' % (out, w, h, bpp, seq, slot))

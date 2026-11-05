"""Generate the project's original switch glyph without external image tools."""
from pathlib import Path
import math
import struct
import zlib

size = 64
pixels = bytearray(size * size * 4)
segments = [(15, 23, 49, 23), (41, 15, 49, 23), (41, 31, 49, 23),
            (49, 42, 15, 42), (23, 34, 15, 42), (23, 50, 15, 42)]


def distance(x, y, x1, y1, x2, y2):
    t = max(0, min(1, ((x-x1)*(x2-x1) + (y-y1)*(y2-y1)) / ((x2-x1)**2 + (y2-y1)**2)))
    return math.hypot(x-(x1+t*(x2-x1)), y-(y1+t*(y2-y1)))


for y in range(size):
    for x in range(size):
        inside = (12 <= x <= 51 or 12 <= y <= 51 or
                  math.hypot(x-(12 if x < 32 else 51), y-(12 if y < 32 else 51)) <= 12)
        color = (26, 39, 62, 255) if inside else (0, 0, 0, 0)
        if any(distance(x, y, *line) <= 2.3 for line in segments):
            color = (114, 168, 255, 255)
        offset = (y*size+x)*4
        pixels[offset:offset+4] = bytes(color)


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)


rows = b''.join(b'\0' + pixels[y*size*4:(y+1)*size*4] for y in range(size))
png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b'')
destination = Path(__file__).resolve().parents[1] / 'assets'
destination.mkdir(exist_ok=True)
(destination / 'codex-switch.ico').write_bytes(struct.pack('<HHH', 0, 1, 1) + struct.pack('<BBBBHHII', size, size, 0, 0, 1, 32, len(png), 22) + png)

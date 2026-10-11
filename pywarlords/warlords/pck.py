"""Decoder for Warlords (1990, SSG) .PCK picture files.

Format (reverse engineered by Ales Teska):
  header: u16 ?, u16 width (pixels), u16 height (pixels)
  body:   LZSS-like stream. Control byte b:
            b & 0x80 == 0  -> literal run of b+1 bytes
            otherwise      -> back reference: offset = ((b<<8)|next) - 0x10000 (negative),
                              length = following byte + 1
  The decompressed data is 4 EGA/VGA bit planes stored one after another,
  each plane (width/8)*height bytes, MSB = leftmost pixel.
The result is an IndexImage of 4-bit colour indices (one byte per pixel, row major).
"""
import struct


def decompress(data):
	src = memoryview(data)
	dst = bytearray()
	i = 0
	n = len(src)
	while i < n:
		b1 = src[i]
		i += 1
		if b1 < 0x80:
			cnt = b1 + 1
			dst += src[i:i + cnt]
			i += cnt
		else:
			if i + 2 > n:
				break
			off = ((b1 << 8) | src[i]) - 0x10000
			ln = src[i + 1] + 1
			i += 2
			p = len(dst) + off
			if p < 0:
				raise ValueError("PCK: back reference out of range")
			if -off >= ln:
				dst += dst[p:p + ln]
			else:
				for j in range(ln):
					dst.append(dst[p + j])
	return bytes(dst)


class IndexImage:
	"""A palette index image: width, height and one byte per pixel (row major)."""

	__slots__ = ('width', 'height', 'data')

	def __init__(self, width, height, data):
		self.width = width
		self.height = height
		self.data = bytes(data)

	@property
	def shape(self):
		return (self.height, self.width)

	def pixel(self, x, y):
		return self.data[y * self.width + x]

	def row(self, y, x0=0, x1=None):
		o = y * self.width
		return self.data[o + x0:o + (self.width if x1 is None else x1)]

	def crop(self, x0, y0, x1, y1):
		x1 = min(x1, self.width)
		y1 = min(y1, self.height)
		return IndexImage(x1 - x0, y1 - y0, b''.join(self.row(y, x0, x1) for y in range(y0, y1)))

	def map(self, table):
		"""Translate every pixel through a 256 byte table."""
		return IndexImage(self.width, self.height, self.data.translate(bytes(table)))


# _EXPAND[b] = the 8 bits of b (MSB first) as an int whose bytes are 0/1
_EXPAND = [int.from_bytes(bytes((b >> (7 - i)) & 1 for i in range(8)), 'big') for b in range(256)]


def planar_to_indices(raw, width, height):
	"""Convert 4 sequential bit planes into an index image.

	Each plane occupies (width // 8) * height bytes, but rows inside a plane
	are word aligned (stride rounded up to an even number of bytes). For
	widths that are a multiple of 16 the two agree; for others (WLC.PCK,
	408 px wide) the visible height is plane_size // stride.
	"""
	plane = (width // 8) * height
	stride = ((width + 15) // 16) * 2
	rows = plane // stride
	raw = bytes(raw)
	if len(raw) < plane * 4:
		raw = raw + bytes(plane * 4 - len(raw))
	E = _EXPAND
	out = bytearray()
	for y in range(rows):
		o = y * stride
		p0 = raw[o:o + stride]
		p1 = raw[plane + o:plane + o + stride]
		p2 = raw[2 * plane + o:2 * plane + o + stride]
		p3 = raw[3 * plane + o:3 * plane + o + stride]
		line = b''.join((E[a] | (E[b] << 1) | (E[c] << 2) | (E[d] << 3)).to_bytes(8, 'big')
			for a, b, c, d in zip(p0, p1, p2, p3))
		out += line[:width]
	return IndexImage(width, rows, out)


def load_pck(path):
	with open(path, 'rb') as f:
		data = f.read()
	_unk, width, height = struct.unpack_from('<HHH', data, 0)
	raw = decompress(data[6:])
	return planar_to_indices(raw, width, height)

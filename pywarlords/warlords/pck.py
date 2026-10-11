"""Decoder for Warlords (1990, SSG) .PCK picture files.

Format (reverse engineered by Ales Teska):
  header: u16 ?, u16 width (pixels), u16 height (pixels)
  body:   LZSS-like stream. Control byte b:
            b & 0x80 == 0  -> literal run of b+1 bytes
            otherwise      -> back reference: offset = ((b<<8)|next) - 0x10000 (negative),
                              length = following byte + 1
  The decompressed data is 4 EGA/VGA bit planes stored one after another,
  each plane (width/8)*height bytes, MSB = leftmost pixel.
The result is an array of 4-bit colour indices (height x width).
"""
import struct
import numpy as np


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
	arr = np.frombuffer(raw, dtype=np.uint8)
	if arr.size < plane * 4:
		arr = np.concatenate([arr, np.zeros(plane * 4 - arr.size, np.uint8)])
	planes = np.stack([arr[k * plane:k * plane + rows * stride].reshape(rows, stride) for k in range(4)])
	bits = np.unpackbits(planes, axis=2)  # 4 x rows x stride*8, MSB first
	idx = bits[0] | (bits[1] << 1) | (bits[2] << 2) | (bits[3] << 3)
	return idx[:, :width].astype(np.uint8)


def load_pck(path):
	with open(path, 'rb') as f:
		data = f.read()
	_unk, width, height = struct.unpack_from('<HHH', data, 0)
	raw = decompress(data[6:])
	return planar_to_indices(raw, width, height)

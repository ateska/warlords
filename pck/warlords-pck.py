import struct
import argparse

import numpy as np
import PIL.Image


class PlanarVGA:

	# This is Palette for MAIN.PCK
	Palette_MAIN = [
		(0x00, 0x00, 0x00),
		(0xf7, 0xf7, 0xf7),
		(0x9e, 0x86, 0x5a),
		(0x78, 0x65, 0x40),
		(0x58, 0x45, 0x31),
		(0xc6, 0x00, 0x00),
		(0x34, 0x34, 0x34),
		(0x6e, 0x06, 0x0f),

		(0x58, 0x45, 0x31),
		(0xa4, 0x00, 0x04),
		(0x55, 0x55, 0x66),
		(0x78, 0x65, 0x40),
		(0xe2, 0x93, 0x6f),
		(0x99, 0x86, 0x60),
		(0xdd, 0xb6, 0x3f),
		(0xb6, 0xb7, 0x92),
	]


	# This is Palette used in the game
	Palette_GAME = [
		# 00: 000000 3d3d3d 252525 1d1d1d-151515 000000 251500 190d00 <---- 0..7
		(0x00 << 2, 0x00 << 2, 0x00 << 2),
		(0x3d << 2, 0x3d << 2, 0x3d << 2),
		(0x25 << 2, 0x25 << 2, 0x25 << 2),
		(0x1d << 2, 0x1d << 2, 0x1d << 2),
		(0x15 << 2, 0x15 << 2, 0x15 << 2),
		(0x00 << 2, 0x00 << 2, 0x00 << 2),
		(0x25 << 2, 0x15 << 2, 0x00 << 2),
		(0x19 << 2, 0x0d << 2, 0x00 << 2),

		# 10: 002131 001531 001900 0a210a-152515 310000 312100 313100 <---- 8..15
		(0x00 << 2, 0x21 << 2, 0x31 << 2),
		(0x00 << 2, 0x15 << 2, 0x31 << 2),
		(0x00 << 2, 0x19 << 2, 0x00 << 2),
		(0x0a << 2, 0x21 << 2, 0x0a << 2),
		(0x15 << 2, 0x25 << 2, 0x15 << 2),
		(0x31 << 2, 0x00 << 2, 0x00 << 2),
		(0x31 << 2, 0x21 << 2, 0x00 << 2),
		(0x31 << 2, 0x31 << 2, 0x00 << 2),
	]


	def __init__(self, raw, width, height, *, palette=None):
		# VGA has 4 planes
		planelen = len(raw) // 4
		self.Plane0 = raw[:planelen]
		self.Plane1 = raw[planelen:planelen * 2]
		self.Plane2 = raw[planelen * 2:planelen * 3]
		self.Plane3 = raw[planelen * 3:]
		assert len(self.Plane0) == len(self.Plane1)
		assert len(self.Plane1) == len(self.Plane2)
		assert len(self.Plane2) == len(self.Plane3)

		self.Width = width // 8
		self.Height = height

		if palette == "game":
			self.Palette = self.Palette_GAME
		elif palette == "main":
			self.Palette = self.Palette_MAIN
		else:
			raise ValueError(f"Invalid palette: {palette}")


	def get_pixel(self, x, y, transparent_color=None):
		mask = 0x80 >> (x % 8)

		plane_x = x // 8

		bit0 = (self.Plane0[plane_x + y * self.Width] & mask) != 0
		bit1 = (self.Plane1[plane_x + y * self.Width] & mask) != 0
		bit2 = (self.Plane2[plane_x + y * self.Width] & mask) != 0
		bit3 = (self.Plane3[plane_x + y * self.Width] & mask) != 0

		color_ix = bit0 | (bit1 << 1) | (bit2 << 2) | (bit3 << 3)

		if color_ix == transparent_color:
			return (0, 0, 0, 0)  # Transparent pixel

		r, g, b = self.Palette[color_ix]
		return (r, g, b, 255)  # Opaque pixel


	def dump(self, transparent_color=None):
		img = np.zeros((self.Height * 2, self.Width * 8, 4), dtype=np.uint8)

		for y in range(self.Height):
			for x in range(self.Width * 8):
				pixel = self.get_pixel(x, y, transparent_color=transparent_color)
				img[y * 2, x] = pixel
				img[y * 2 + 1, x] = pixel

		return img


def decompress_lzss_pck(path, **kwargs):
	"""
	Decompresses a .PCK file using the LZSS algorithm.

	https://en.wikipedia.org/wiki/Lempel–Ziv–Storer–Szymanski
	"""
	with open(path, 'rb') as f:
		header = f.read(6)
		_, width, height = struct.unpack('<HHH', header)
		print(f"[Header] Width: {width}, Height: {height}")
		compressed = f.read()

	src = bytearray(compressed)
	dst = bytearray()
	i = 0

	while i < len(src):
		b1 = src[i]
		i += 1

		if (b1 & 0x80) == 0:
			# Literal run
			count = b1 + 1
			dst.extend(src[i:i + count])
			i += count
		else:
			# Backreference
			if i + 2 > len(src):
				break  # not enough bytes
			b2 = src[i]
			b3 = src[i + 1] + 1
			i += 2

			offset = ((b1 << 8) | b2) - 0x10000

			src_pos = len(dst) + offset
			for j in range(b3):
				if src_pos + j < 0 or src_pos + j >= len(dst):
					raise ValueError("Out of bounds")
				else:
					dst.append(dst[src_pos + j])

	print(f"[Decompress] Output size: {len(dst)} bytes")
	return PlanarVGA(dst, width, height, **kwargs)


def show_image(img, title="Decoded Image"):
	import matplotlib.pyplot
	matplotlib.pyplot.imshow(img)
	matplotlib.pyplot.title(title)
	matplotlib.pyplot.axis('off')
	matplotlib.pyplot.show()


if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		description="Decode Warlords .PCK files.\nPCK files are stored in the game's PICTS directory and contain game graphics.",
		epilog="Written by Ales Teska, 2025",
		formatter_class=argparse.RawDescriptionHelpFormatter,
	)
	parser.add_argument("file", help="Path to the .PCK file to decode")
	parser.add_argument("-o", "--output", help="Path to the output PNG file", default="")
	parser.add_argument("-t", "--transparent", help="Transparent color index", type=int, default=-1)
	parser.add_argument("-p", "--palette", help="Use palette", default="auto", choices=["auto", "game", "main"])
	parser.add_argument("-S", "--show", help="Show image", action="store_true", default=False)
	args = parser.parse_args()

	if args.palette == "auto":
		if "MAIN.PCK" in args.file:
			args.palette = "main"
		else:
			args.palette = "game"

	planar = decompress_lzss_pck(args.file, palette=args.palette)
	img = planar.dump(transparent_color=args.transparent if args.transparent != -1 else None)
	if args.output:
		PIL.Image.fromarray(img, 'RGBA').save(args.output)
	if args.show:
		show_image(img)

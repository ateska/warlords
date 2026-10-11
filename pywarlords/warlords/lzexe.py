"""Minimal LZEXE 0.91 unpacker (pure Python).

The floppy release of Warlords ships WARLORDS.EXE compressed with LZEXE 0.91
(signature "LZ91" at offset 0x1C). We only need the decompressed load image
(the game's code and initialised data), so relocations are not rebuilt.
"""
import struct


class _Bits:
	def __init__(self, data, pos):
		self.d = data
		self.p = pos
		self._load()

	def _load(self):
		self.buf = self.d[self.p] | (self.d[self.p + 1] << 8)
		self.p += 2
		self.cnt = 16

	def bit(self):
		b = self.buf & 1
		self.buf >>= 1
		self.cnt -= 1
		if self.cnt == 0:
			self._load()
		return b

	def byte(self):
		b = self.d[self.p]
		self.p += 1
		return b


def is_lzexe(data):
	return len(data) > 0x20 and data[:2] == b'MZ' and data[0x1C:0x20] in (b'LZ91', b'LZ09')


def unpack_image(data):
	"""Return the decompressed load image (bytes) of an LZ91 packed EXE."""
	if data[0x1C:0x20] != b'LZ91':
		raise ValueError("Only LZEXE 0.91 is supported")
	hdr_paras = struct.unpack_from('<H', data, 8)[0]
	cs = struct.unpack_from('<H', data, 0x16)[0]
	base = hdr_paras * 16
	stub = base + cs * 16
	_ip, _cs, _sp, _ss, cmp_paras, _inc, _dsize, _chk = struct.unpack_from('<8H', data, stub)
	# compressed stream starts at the stub segment minus the compressed size
	src = stub - cmp_paras * 16
	bits = _Bits(data, src)
	out = bytearray()
	while True:
		if bits.bit():
			out.append(bits.byte())
			continue
		if bits.bit() == 0:
			ln = ((bits.bit() << 1) | bits.bit()) + 2
			span = bits.byte() - 0x100
		else:
			lo = bits.byte()
			hi = bits.byte()
			span = lo | ((hi & 0xf8) << 5) | 0xe000
			span -= 0x10000
			ln = hi & 7
			if ln:
				ln += 2
			else:
				ln = bits.byte()
				if ln == 0:
					break
				if ln == 1:
					continue
				ln += 1
		p = len(out) + span
		for i in range(ln):
			out.append(out[p + i])
	return bytes(out)

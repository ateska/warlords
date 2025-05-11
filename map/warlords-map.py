import argparse

import numpy as np
from PIL import Image, ImageDraw, ImageFont

tile_size = 40


class WarlordsMap:


	def __init__(self, filename="ILLURIA.MAP", width=109, height=156):
		with open(filename, "rb") as f:
			data = f.read()

		self.Width = width
		self.Height = height

		# Convert to 16-bit unsigned integers, little-endian
		tiles = np.frombuffer(data, dtype='<u2')
		self.TilesMap = tiles.reshape((height, width))

		# lower byte: movement, restrictions, etc.
		self.TileAttrs = self.TilesMap & 0x00FF

		# upper byte: graphical tile ID
		self.TileIDs = self.TilesMap >> 8

		self.TileIdsToScenery = {}


	def load_scenery(self, filename="SCENERY.png"):
		tileset = Image.open(filename).convert("RGB")
		tileset_width, tileset_height = tileset.size

		# Compute number of tiles in the tileset
		tiles_per_row = tileset_width // tile_size
		tiles_per_col = tileset_height // tile_size

		# Precut all tiles into a list
		self.SceneryTiles = []
		for ty in range(tiles_per_col):
			for tx in range(tiles_per_row):
				box = (tx * tile_size, ty * tile_size, (tx + 1) * tile_size, (ty + 1) * tile_size)
				tile = tileset.crop(box)
				self.SceneryTiles.append(tile)

		self.TileIdsToScenery.update({
			0x00: self.SceneryTiles[9],    # grass
			0x80: self.SceneryTiles[9],    # grass (again?)

			0x81: self.SceneryTiles[0],    # unoccupied tower
			0x8A: self.SceneryTiles[10],   # Small temple
			0x8B: self.SceneryTiles[11],   # Big temple
			0x8C: self.SceneryTiles[12],   # Ruin
			0x8D: self.SceneryTiles[13],   # bigger grass

			0x8E: self.SceneryTiles[16],   # road E-W
			0x8F: self.SceneryTiles[17],   # road N-S

			0x90: self.SceneryTiles[18],   # crossroad E-W-S-N
			0x91: self.SceneryTiles[19],   # crossroad E-W-S
			0x92: self.SceneryTiles[20],   # crossroad E-S-N
			0x93: self.SceneryTiles[21],   # crossroad E-W-N
			0x94: self.SceneryTiles[22],   # crossroad E-S-N

			0x95: self.SceneryTiles[23],   # road W-S
			0x96: self.SceneryTiles[24],   # road W-N
			0x97: self.SceneryTiles[25],   # road E-N
			0x98: self.SceneryTiles[26],   # road E-S

			0x99: self.SceneryTiles[27],   # road E
			0x9A: self.SceneryTiles[28],   # road S
			0x9B: self.SceneryTiles[29],   # road W
			0x9C: self.SceneryTiles[30],   # road N

			0x9D: self.SceneryTiles[32],   # Coast E-S
			0x9E: self.SceneryTiles[33],   # Coast E-W (S)
			0x9F: self.SceneryTiles[34],   # Coast W-S
			0xA0: self.SceneryTiles[35],   # Coast E-N
			0xA1: self.SceneryTiles[36],   # Coast E-W (N)
			0xA2: self.SceneryTiles[37],   # Coast E-N
			0xA3: self.SceneryTiles[38],   # Coast S-N (W)
			0xA4: self.SceneryTiles[39],   # Water
			0xA5: self.SceneryTiles[40],   # Coast S-N (E)
			0xA6: self.SceneryTiles[41],   # Coast
			0xA7: self.SceneryTiles[42],   # Coast
			0xA8: self.SceneryTiles[43],   # Coast
			0xA9: self.SceneryTiles[44],   # Coast
			0xAA: self.SceneryTiles[45],   # Whirlpool ?

			0xAB: self.SceneryTiles[48],   # Treeline E-S
			0xAC: self.SceneryTiles[49],   # Treeline E-W (S)
			0xAD: self.SceneryTiles[50],   # Treeline W-S
			0xAE: self.SceneryTiles[51],   # Treeline E-N
			0xAF: self.SceneryTiles[52],   # Treeline E-W (N)
			0xB0: self.SceneryTiles[53],   # Treeline E-N
			0xB1: self.SceneryTiles[54],   # Treeline S-N (W)
			0xB2: self.SceneryTiles[55],   # Forest E-S
			0xB3: self.SceneryTiles[56],   # Treeline S-N (E)
			0xB4: self.SceneryTiles[57],   # Treeline
			0xB5: self.SceneryTiles[58],   # Treeline
			0xB6: self.SceneryTiles[59],   # Treeline
			0xB7: self.SceneryTiles[60],   # Treeline
			0xB8: self.SceneryTiles[61],   # Treeline patch

			0xB9: self.SceneryTiles[64],   # Hills
			0xBA: self.SceneryTiles[65],   # Hills
			0xBB: self.SceneryTiles[66],   # Hills
			0xBC: self.SceneryTiles[67],   # Hills
			0xBD: self.SceneryTiles[68],   # Hills
			0xBE: self.SceneryTiles[69],   # Hills
			0xBF: self.SceneryTiles[70],   # Hills
			0xC0: self.SceneryTiles[71],   # Hills
			0xC1: self.SceneryTiles[72],   # Hills
			0xC2: self.SceneryTiles[73],   # Hills
			0xC3: self.SceneryTiles[74],   # Hills
			0xC4: self.SceneryTiles[75],   # Hills
			0xC5: self.SceneryTiles[76],   # Hills
			0xC6: self.SceneryTiles[77],   # Hills

			0xC7: self.SceneryTiles[80],   # Mountains
			0xC8: self.SceneryTiles[81],   # Mountains
			0xC9: self.SceneryTiles[82],   # Mountains
			0xCA: self.SceneryTiles[83],   # Mountains
			0xCB: self.SceneryTiles[84],   # Mountains
			0xCC: self.SceneryTiles[85],   # Mountains
			0xCD: self.SceneryTiles[86],   # Mountains
			0xCE: self.SceneryTiles[87],   # Mountains with snow
			0xCF: self.SceneryTiles[88],   # Mountains
			0xD0: self.SceneryTiles[89],   # Mountains
			0xD1: self.SceneryTiles[90],   # Mountains
			0xD2: self.SceneryTiles[91],   # Mountains
			0xD3: self.SceneryTiles[92],   # Mountains
			0xD4: self.SceneryTiles[93],   # Mountains
			0xD5: self.SceneryTiles[94],   # Vulcano

			0xFA: self.SceneryTiles[132],  # Bridge N-S N
			0xFB: self.SceneryTiles[148],  # Bridge N-S S

			0xFC: self.SceneryTiles[133],  # Bridge E-W E
			0xFD: self.SceneryTiles[134],  # Bridge E-W W
		})

		self.add_castle_tiles(0xD6, 96)    # unoccupied castle

		self.add_castle_tiles(0xDA, 98)    # Sirians castle
		self.add_castle_tiles(0xDE, 100)   # Storm Giants castle
		self.add_castle_tiles(0xE2, 102)   # Grey Dwarves castle
		self.add_castle_tiles(0xE6, 104)   # Orcs of Kor castle
		self.add_castle_tiles(0xEA, 106)   # Elvallie castle
		self.add_castle_tiles(0xEE, 108)   # The Selentines castle
		self.add_castle_tiles(0xF2, 128)   # Horse Lords castle
		self.add_castle_tiles(0xF6, 130)   # Lord Bane castle


	def add_castle_tiles(self, tile_id, scenery_tile):
		self.TileIdsToScenery.update({
			tile_id + 0: self.SceneryTiles[scenery_tile],
			tile_id + 1: self.SceneryTiles[scenery_tile + 1],
			tile_id + 2: self.SceneryTiles[scenery_tile + 16],
			tile_id + 3: self.SceneryTiles[scenery_tile + 17],
		})



	def show(self):

		image = self.TileIDs.astype(np.uint8)

		print("Min TileID:", np.min(self.TileIDs))
		print("Max TileID:", np.max(self.TileIDs))

		# Display the tilemap
		import matplotlib.pyplot
		matplotlib.pyplot.figure(figsize=(8, 10))
		matplotlib.pyplot.imshow(image)
		matplotlib.pyplot.title("Warlords: ILLURIA.MAP")
		matplotlib.pyplot.axis('off')
		matplotlib.pyplot.show()


	def export(self, output_file="ILLURIA.png", enable_text=False):
		img_width = self.Width * tile_size
		img_height = self.Height * tile_size

		image = Image.new("RGB", (img_width, img_height), "white")
		draw = ImageDraw.Draw(image)

		font = ImageFont.load_default()

		for y in range(self.Height):
			for x in range(self.Width):
				tile_id = self.TileIDs[y, x]
				tile_attrs = self.TileAttrs[y, x]

				# Position in image
				x0 = x * tile_size
				y0 = y * tile_size
				x1 = x0 + tile_size
				y1 = y0 + tile_size

				tile_image = self.TileIdsToScenery.get(tile_id, None)
				if tile_image is None:
					# Fill color (based on tile_id, here simple hash to color)
					fill = (100 + (tile_id * 11) % 156, 100 + (tile_id * 7) % 156, 100 + (tile_id * 3) % 156)
					draw.rectangle([x0, y0, x1, y1], fill=fill, outline=None)
					print("WARNING: unmapped tile:", tile_id)
				else:
					image.paste(tile_image, (x0, y0))

				# Draw tile ID in the center
				if enable_text:
					text = "{:02X}\n{:02X}".format(tile_id, tile_attrs)
					text_bbox = draw.textbbox((0, 0), text, font=font)
					text_width = text_bbox[2] - text_bbox[0]
					text_height = text_bbox[3] - text_bbox[1]
					text_x = x0 + (tile_size - text_width) // 2
					text_y = y0 + (tile_size - text_height) // 2
					draw.text((text_x, text_y), text, fill="black", font=font)

		print("Saving to:", output_file)
		image.save(output_file)


if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		description="Decode Warlords ILLURIA.MAP file.",
		epilog="Written by Ales Teska, 2025",
		formatter_class=argparse.RawDescriptionHelpFormatter,
	)
	parser.add_argument("file", help="Path to the ILLURIA.MAP file to decode (default: ILLURIA.MAP)", default="ILLURIA.MAP")
	parser.add_argument("-s", "--scenery", help="PNG file with scenery tiles (default: SCENERY.png)", default="SCENERY.png")
	parser.add_argument("-o", "--output", help="Path to the output PNG file (default: ILLURIA.png)", default="ILLURIA.png")
	parser.add_argument("-t", "--text", help="Draw tile ID and attributes in the center of each tile", action="store_true", default=False)
	args = parser.parse_args()

	map = WarlordsMap(filename=args.file)
	map.load_scenery(filename=args.scenery)
	map.export(output_file=args.output, enable_text=args.text)

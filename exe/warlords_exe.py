import os
import json
import struct
import argparse



def extract_castles(f):
	f.seek(311857)

	castles_count = 80
	export = []

	for i in range(castles_count):
		castle_data = f.read(100)

		x = struct.unpack('<5B20sbb', castle_data[:27])
		i = 0
		assert x[i] == 0
		i += 1
		castle_x = x[i]
		i += 1
		assert x[i] == 0
		i += 1
		castle_y = x[i]
		i += 1
		assert x[i] == 0
		i += 1
		castle_name = x[i].decode("ascii").rstrip("\x00")
		i += 1
		castle_level = x[i]
		i += 1
		if x[i] == 0x0f:
			castle_owner = 8
		else:
			castle_owner = x[i]

		# TODO: More bytes to be analyzed

		export.append({
			"name": castle_name,
			"x": castle_x,
			"y": castle_y,
			"level": castle_level,
			"owner": castle_owner,
		})

	return export


def main():
	parser = argparse.ArgumentParser(
		description="Decode Warlords WARLORDS.EXE file.",
		epilog="Written by Ales Teska, 2025",
		formatter_class=argparse.RawDescriptionHelpFormatter,
	)
	parser.add_argument("file", help="Path to the WARLORDS.EXE file to decode (default: WARLORDS.EXE)", default="WARLORDS.EXE")
	args = parser.parse_args()

	try:
		stat = os.stat(args.file)
	except FileNotFoundError:
		print(f"File not found: {args.file}")
		return

	if stat.st_size != 332182:
		print(f"File size is not 332182 bytes: {stat.st_size} bytes (not the correct EXE file)")
		return


	# Extract castles
	with open(args.file, "rb") as f:
		castles = extract_castles(f)
		with open("castles.json", "w") as f:
			json.dump(castles, f, indent='\t')


if __name__ == "__main__":
	main()

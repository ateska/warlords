from PIL import Image
import numpy as np


def get_character_width(img, x, y, char_width=15, char_height=18):
	"""Calculate the actual width of a character by finding the rightmost non-transparent pixel."""
	# Extract the character region
	char_region = img.crop((x, y, x + char_width, y + char_height))
	# Convert to numpy array for easier processing
	char_array = np.array(char_region)

	# Find the rightmost non-transparent pixel in each row
	max_width = 0
	for row in char_array:
		# Find indices of non-transparent pixels (where alpha > 0)
		non_transparent = np.where(row[:, 3] > 0)[0]
		if len(non_transparent) > 0:
			# Add 1 because we want the width (not the index)
			row_width = non_transparent[-1] + 1
			max_width = max(max_width, row_width)

	return max_width


def analyze_font_image(image_path):
	"""Analyze the FANTS.png file and determine character widths."""
	try:
		# Load the image
		img = Image.open(image_path)

		# Image dimensions
		char_width = 16
		char_height = 18
		cols = 16
		rows = 6

		# Store results
		character_widths = {}

		# Process each character
		for row in range(rows):
			for col in range(cols):
				# Calculate character position
				x = col * char_width
				y = row * char_height

				# Calculate ASCII code (starting from space, 32)
				ascii_code = 32 + (row * cols + col)

				# Get character width
				width = get_character_width(img, x, y)

				# Store result
				character_widths[ascii_code] = width + 1

		character_widths[32] = 8
		return character_widths

	except Exception as e:
		print(f"Error processing image: {e}")
		return None


if __name__ == "__main__":
	# Path to the FANTS.png file
	image_path = "FANTS.PNG"

	# Analyze the font image
	character_widths = analyze_font_image(image_path)
	for ch, w in character_widths.items():
		print("{}, // {}".format(w, chr(ch)))

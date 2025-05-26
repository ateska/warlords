import numpy as np
from PIL import Image
import os


def slice_armies():
	# Load the ARMIES.png image
	img = Image.open('ARMIES.png')
	img_array = np.array(img)

	# Constants for slicing
	UNIT_SIZE = 28
	START_X = 5
	START_Y = 0
	UNITS_PER_ROW = 18
	NUM_ROWS = 8

	# Create output directory if it doesn't exist
	output_dir = 'ARMIES'
	os.makedirs(output_dir, exist_ok=True)

	# Slice the image into individual units
	for row in range(NUM_ROWS):
		for col in range(UNITS_PER_ROW):
			# Calculate the coordinates for this unit
			x = START_X + (col * UNIT_SIZE)
			y = START_Y + (row * UNIT_SIZE)

			# Extract the unit image
			unit = img_array[y:y + UNIT_SIZE, x:x + UNIT_SIZE]

			# Convert back to PIL Image and save
			unit_img = Image.fromarray(unit)
			output_path = os.path.join(output_dir, f'ARMY_{row}_{col:02}.png')
			unit_img.save(output_path)

			print(f'Saved unit at position ({row}, {col}) to {output_path}')


if __name__ == '__main__':
	slice_armies()

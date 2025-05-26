from PIL import Image
import os


def split_scenery():
    # Open the source image
    try:
        img = Image.open('SCENERY.png')
    except FileNotFoundError:
        print("Error: SCENERY.png not found in the current directory")
        return
    except Exception as e:
        print(f"Error opening image: {e}")
        return

    # Get image dimensions
    width, height = img.size

    # Calculate number of tiles in each dimension
    tiles_x = width // 40
    tiles_y = height // 40

    # Create output directory if it doesn't exist
    output_dir = 'tiles'
    os.makedirs(output_dir, exist_ok=True)

    # Split the image into tiles
    for y in range(tiles_y):
        for x in range(tiles_x):
            # Calculate tile position
            left = x * 40
            upper = y * 40
            right = left + 40
            lower = upper + 40

            # Crop the tile
            tile = img.crop((left, upper, right, lower))

            # Generate hexadecimal position
            position = y * tiles_x + x
            hex_position = format(position, '02x')

            # Save the tile
            output_path = os.path.join(output_dir, f'SCENERY_{hex_position}.png')
            tile.save(output_path)

    print(f"Successfully created {tiles_x * tiles_y} tiles in the 'tiles' directory")


if __name__ == '__main__':
    split_scenery()

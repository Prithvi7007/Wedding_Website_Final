from PIL import Image
from pathlib import Path
import sys

def crop_transparent_png(input_path, output_path=None, padding=24, alpha_threshold=25):
    input_path = Path(input_path)

    if output_path is None:
        output_path = input_path.with_name(input_path.stem + "-cropped.png")
    else:
        output_path = Path(output_path)

    img = Image.open(input_path).convert("RGBA")

    # Treat very faint alpha pixels as transparent
    alpha = img.getchannel("A")
    thresholded_alpha = alpha.point(lambda p: 255 if p > alpha_threshold else 0)

    bbox = thresholded_alpha.getbbox()

    if bbox is None:
        print(f"No visible pixels found in {input_path}")
        return

    left, top, right, bottom = bbox

    left = max(left - padding, 0)
    top = max(top - padding, 0)
    right = min(right + padding, img.width)
    bottom = min(bottom + padding, img.height)

    cropped = img.crop((left, top, right, bottom))
    cropped.save(output_path)

    print(f"Saved: {output_path}")
    print(f"Original size: {img.width} x {img.height}")
    print(f"Cropped size: {cropped.width} x {cropped.height}")
    print(f"Crop box: left={left}, top={top}, right={right}, bottom={bottom}")
    print(f"Alpha threshold used: {alpha_threshold}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python crop_transparent.py path/to/image.png [alpha_threshold]")
        sys.exit(1)

    threshold = 25
    if len(sys.argv) >= 3:
        threshold = int(sys.argv[2])

    crop_transparent_png(sys.argv[1], alpha_threshold=threshold)
import os
import sys

from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication


def convert_svg_to_ico(svg_path, ico_path, png_path):
    _app = QApplication(sys.argv)

    # Render SVG to PNG
    renderer = QSvgRenderer(svg_path)
    if not renderer.isValid():
        print("Invalid SVG file")
        sys.exit(1)

    # Standard icon size
    size = 256
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(0)  # Transparent

    painter = QPainter(image)
    renderer.render(painter)
    painter.end()

    # Save as PNG
    image.save(png_path, "PNG")
    print(f"Saved {png_path}")

    # Save as ICO
    # QImage can save as ICO on Windows natively if image formats plugin is there
    success = image.save(ico_path, "ICO")
    if success:
        print(f"Saved {ico_path}")
    else:
        print("Failed to save as ICO directly via Qt. Saving via PIL.")
        try:
            from PIL import Image

            img = Image.open(png_path)
            img.save(
                ico_path, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)]
            )
            print(f"Saved {ico_path} using PIL")
        except ImportError:
            print("Please install Pillow to complete ICO conversion: uv pip install Pillow")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    svg_in = os.path.join(base_dir, "resources", "app_icon.svg")
    png_out = os.path.join(base_dir, "resources", "app_icon.png")
    ico_out = os.path.join(base_dir, "resources", "app_icon.ico")

    convert_svg_to_ico(svg_in, ico_out, png_out)

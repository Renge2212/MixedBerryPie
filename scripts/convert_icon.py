import io
import os
import sys

from PIL import Image
from PyQt6.QtCore import QBuffer
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication


def convert_svg_to_ico(svg_path, ico_path, png_path):
    _app = QApplication(sys.argv)

    # Render SVG to multiple sizes
    renderer = QSvgRenderer(svg_path)
    if not renderer.isValid():
        print("Invalid SVG file")
        sys.exit(1)

    # Step 1: Render SVG at very high resolution (1024x1024) for maximum detail
    base_size = 1024
    high_res_image = QImage(base_size, base_size, QImage.Format.Format_ARGB32)
    high_res_image.fill(0)  # Transparent

    painter = QPainter(high_res_image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()

    # Convert high-res QImage to PIL Image
    q_buffer = QBuffer()
    q_buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    high_res_image.save(q_buffer, "PNG")
    full_pil_img = Image.open(io.BytesIO(q_buffer.data().data()))

    # Step 2: Resize to all standard Windows icon sizes using high-quality LANCZOS filter
    # Descending order is standard for ICO. 256px is usually stored as PNG inside the ICO.
    target_sizes = [256, 128, 64, 48, 40, 32, 24, 20, 16]
    images = []

    for size in target_sizes:
        if size == base_size:
            images.append(full_pil_img.copy())
        else:
            # LANCZOS is the highest quality downsampling filter in Pillow
            resized_img = full_pil_img.resize((size, size), Image.Resampling.LANCZOS)
            images.append(resized_img)

        if size == 256:
            resized_img.save(png_path, "PNG")
            print(f"Saved preview PNG: {png_path}")

    # Step 3: Save as multi-size ICO using PIL
    # Standard practice is to let Pillow decide PNG/BMP format (Windows 10+ uses PNG for 256px)
    images[0].save(
        ico_path,
        format="ICO",
        append_images=images[1:],
    )
    print(f"Saved optimized high-quality {ico_path} with sizes: {target_sizes}")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    svg_in = os.path.join(base_dir, "resources", "app_icon.svg")
    png_out = os.path.join(base_dir, "resources", "app_icon.png")
    ico_out = os.path.join(base_dir, "resources", "app_icon.ico")

    convert_svg_to_ico(svg_in, ico_out, png_out)

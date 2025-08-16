"""Entry point and main interface for the ColorScheme Recolorer application."""

import argparse
import contextlib
import json
import logging
import os
import pathlib
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from .clustering import apply_color_scheme, compute_image_clusters
from .launcher import launch_application

os.environ["OMP_NUM_THREADS"] = str(os.cpu_count())

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_color_schemes(theme_file: str = "iterm2") -> dict:
    """Load color schemes from specified theme file with proper path resolution."""
    script_dir = pathlib.Path(__file__).parent.parent
    themes_path = script_dir / "assets" / "themes" / f"{theme_file}.json"

    try:
        with themes_path.open() as f:
            return json.load(f)
    except FileNotFoundError:
        logger.exception("Error: Theme file '%s' not found.", themes_path)
        sys.exit(1)


def recolor_image(
    image: Image.Image,
    color_scheme: np.ndarray,
    sample_size: int = 50000,
    n_colors: int = 8,
) -> Image.Image:
    """Legacy function for compatibility. Combines clustering and color application."""
    clustering_data = compute_image_clusters(image, sample_size, n_colors)
    return apply_color_scheme(clustering_data, color_scheme)


def main_interface(image_path: str, color_schemes: dict) -> None:
    """Launch the main user interface with error handling."""
    with contextlib.suppress(KeyboardInterrupt):
        launch_application(image_path, color_schemes, recolor_image)


def main() -> None:
    """Run the color schemer application."""
    parser = argparse.ArgumentParser(
        description="ColorScheme Recolorer - Recolor images using color schemes",
    )

    parser.add_argument("image_path", help="Path to image file or URL")
    parser.add_argument(
        "--theme-file",
        choices=["iterm2", "base16"],
        default="iterm2",
        help="Theme file to use (default: iterm2)",
    )
    parser.add_argument("--version", action="version", version="colorschemer 1.0.0")

    args = parser.parse_args()

    image = args.image_path
    if not Path(image).exists() and not image.startswith(("http://", "https://")):
        logger.exception("Error: Image path '%s' does not exist.", image)
        sys.exit(1)

    color_schemes = load_color_schemes(args.theme_file)

    main_interface(args.image_path, color_schemes)


if __name__ == "__main__":
    main()

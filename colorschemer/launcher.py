"""Application launcher for the Color Scheme interface."""

from collections.abc import Callable
from typing import Any

from .components.app import App
from .utils.terminal import query_terminal_cell_size


def launch_application(
    image_path: str,
    color_schemes: dict[str, list[str]],
    color_transformation_function: Callable[[Any, Any, int, int], Any],
) -> None:
    """Launch the Color Scheme Application interface.

    Args:
        image_path: Path to the source image file or URL
        color_schemes: Dictionary mapping theme names to color lists
        color_transformation_function: Function to apply color transformations

    """
    cell_width_px, cell_height_px = query_terminal_cell_size()
    app = App(
        image_path,
        color_schemes,
        color_transformation_function,
        cell_width_px,
        cell_height_px,
    )
    app.run()

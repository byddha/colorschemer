"""Application launcher for the Color Scheme interface."""

from typing import Any

from .components.app import App
from .utils.terminal import query_terminal_cell_size


def launch_application(
    image_path: str,
    color_schemes: dict[str, list[str]],
    extractor: Any,  # noqa: ANN401
    settings: Any,  # noqa: ANN401
) -> None:
    """Launch the Color Scheme Application interface.

    Args:
        image_path: Path to the source image file or URL
        color_schemes: Dictionary mapping theme names to color lists
        extractor: Color extractor instance
        settings: Settings component instance

    """
    cell_width_px, cell_height_px = query_terminal_cell_size()
    app = App(
        image_path,
        color_schemes,
        extractor,
        settings,
        cell_width_px,
        cell_height_px,
    )
    app.run()

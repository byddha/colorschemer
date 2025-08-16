"""Image preview component for displaying transformed images."""

from typing import Any

from PIL import Image
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.events import Resize
from textual.widgets import Static
from textual_image.widget import Image as ImageWidget

from colorschemer.utils.cache import ImageCache

from .settings import Settings

MAX_IMAGE_WIDTH = 1200
MAX_IMAGE_HEIGHT = 800


class Preview(Container):
    """Image preview container."""

    def __init__(
        self,
        image_cache: ImageCache,
        cell_width_px: float,
        cell_height_px: float,
        **kwargs,
    ) -> None:
        self.image_cache = image_cache
        self.current_image: Image.Image | None = None
        self.current_image_widget: Any = None
        self.current_theme = ""
        self.cell_width_px = cell_width_px
        self.cell_height_px = cell_height_px

        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        with Vertical():
            with Container(id="image-container", classes="image-main"):
                pass
            yield Static("[bold]2[/bold] Settings", classes="pane-title")
            yield Settings(id="settings-panel")

    def update_image(self, theme_name: str, image: Image.Image) -> None:
        self.current_image = image
        self.current_theme = theme_name

        try:
            image_container = self.query_one("#image-container", Container)
            image_container.remove_children()
            self.current_image_widget = None

            max_width, max_height = MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT
            if image.size[0] > max_width or image.size[1] > max_height:
                image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

            self.current_image_widget = ImageWidget(image)
            self._apply_optimal_sizing(image)

            if self.current_image_widget is not None:
                image_container.mount(self.current_image_widget)
        except Exception as e:
            image_container = self.query_one("#image-container", Container)
            image_container.remove_children()
            error_details = f"Image: {image.size[0]}x{image.size[1]} pixels\nMode: {image.mode}\nError: {e!s}"  # noqa: E501
            fallback_text = Static(error_details)
            image_container.mount(fallback_text)

    def on_resize(self, _event: Resize) -> None:
        if self.current_image and self.current_image_widget:
            self._apply_optimal_sizing(self.current_image)

    def _apply_optimal_sizing(self, image: Image.Image) -> None:
        if not self.cell_width_px or not self.cell_height_px:
            msg = "Cell size not initialized"
            raise RuntimeError(msg)

        image_container = self.query_one("#image-container", Container)
        container_width_cells = image_container.size.width
        container_height_cells = image_container.size.height

        if container_width_cells == 0 or container_height_cells == 0:
            return

        container_width_px = container_width_cells * self.cell_width_px
        container_height_px = container_height_cells * self.cell_height_px
        image_width_px, image_height_px = image.size

        width_scale = container_width_px / image_width_px
        height_scale = container_height_px / image_height_px
        scale_factor = min(width_scale, height_scale)

        width_percent = int((image_width_px * scale_factor / container_width_px) * 100)
        height_percent = int(
            (image_height_px * scale_factor / container_height_px) * 100,
        )
        width_percent = min(width_percent, 100)
        height_percent = min(height_percent, 100)

        if self.current_image_widget:
            self.current_image_widget.styles.width = f"{width_percent}%"
            self.current_image_widget.styles.height = f"{height_percent}%"
            self.current_image_widget.refresh()

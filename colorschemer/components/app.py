"""Main application component for the color schemer."""

import pathlib
import subprocess
import tempfile
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Any

import numpy as np
import requests
from PIL import Image
from textual.app import App as TextualApp
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    OptionList,
    Static,
)
from textual_slider import Slider

from colorschemer.clustering import apply_color_scheme, compute_image_clusters
from colorschemer.utils.cache import ImageCache

from .preview import Preview
from .search import Search
from .settings import Settings
from .themes import Themes

MIN_SAMPLING_SIZE = 1000
MAX_SAMPLING_SIZE = 100000
MIN_COLOR_COUNT = 4
MAX_COLOR_COUNT = 16
MIN_MAX_ITERATIONS = 50
MAX_MAX_ITERATIONS = 500
CACHE_SIZE_LIMIT = 50
SEARCH_DEBOUNCE_DELAY_SECONDS = 0.2
NOTIFICATION_TIMEOUT_SECONDS = 2


class App(TextualApp):
    """Main color schemer application."""

    DEFAULT_SAMPLING_SIZE = 50000
    DEFAULT_COLOR_COUNT = 8
    DEFAULT_MAX_ITERATIONS = 100
    DEFAULT_PRESERVE_BRIGHTNESS = True
    CSS = """
    Screen {
        layout: horizontal;
    }

    #left-panel {
        width: 35;
        min-width: 30;
        max-width: 40;
        border: solid $primary;
    }

    .pane-title {
        height: 1;
        margin: 0 1;
        text-align: center;
        background: $surface;
    }


    #right-panel {
        width: 1fr;
        min-width: 80;
        border: solid $success;
    }

    #search {
        height: 3;
        margin: 0 1 1 1;
    }

    #theme-list {
        height: 1fr;
        margin: 0 1;
    }

    #image-preview {
        height: 1fr;
        padding: 0;
    }

    #image-container {
        height: 2fr;
        border: solid $secondary;
        margin: 0;
        align: center middle;
        overflow: hidden;
    }

    #image-container Image {
    }

    #settings-panel {
        height: 15;
        border: solid $accent;
        margin: 0;
        padding: 1;
        overflow-y: auto;
    }

    .parameter-controls-row {
        height: 8;
        margin-bottom: 0;
        content-align: center middle;
    }

    .parameter-control-group {
        width: 1fr;
        max-width: 35;
        margin: 0;
        padding: 0 1;
    }

    .parameter-label {
        height: 1;
        margin-bottom: 1;
        text-align: center;
    }

    .action-controls-section {
        height: 3;
        margin-top: 0;
        content-align: center middle;
    }

    #preserve-brightness-checkbox {
        margin: 0;
        text-align: center;
        width: 1fr;
    }

    .action-controls-section > Button {
        width: 1fr;
        min-height: 2;
        margin: 0 1;
    }



    #theme-list {
        text-align: center;
    }

    OptionList > Option {
        padding: 0 1;
        text-align: center;
    }

    OptionList > Option.--highlight {
        background: $accent 50%;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("s", "save", "Save"),
        ("c", "copy", "Copy"),
        ("ctrl+c", "quit", "Quit"),
        ("/", "focus_search", "Search"),
        ("escape", "smart_escape", "Back"),
        ("1", "focus_themes", "Themes"),
        ("2", "focus_settings", "Settings"),
    ]

    def __init__(
        self,
        image_path: str,
        color_schemes: dict[str, list[str]],
        color_transformation_function: Callable[[Any, Any, int, int], Any],
        cell_width_px: float,
        cell_height_px: float,
    ) -> None:
        """Initialize the app."""
        self.image_path = image_path
        self.color_schemes = color_schemes
        self.color_transformation_function = color_transformation_function
        self.cell_width_px = cell_width_px
        self.cell_height_px = cell_height_px
        self.image_cache = ImageCache()
        self.original_image: Image.Image | None = None
        self.clustering_data = None
        self.search_timer = None
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.processing_lock = threading.Lock()
        self.current_processing_theme = None

        self.previous_panel_focus = "theme-list"

        # Detect color count from first theme (8 for iterm2, 16 for base16)
        if color_schemes:
            first_theme = next(iter(color_schemes.values()))
            detected_color_count = len(first_theme)
            self.DEFAULT_COLOR_COUNT = detected_color_count

        self.sampling_size = self.DEFAULT_SAMPLING_SIZE
        self.color_count = self.DEFAULT_COLOR_COUNT
        self.max_iterations = self.DEFAULT_MAX_ITERATIONS
        self.preserve_brightness = self.DEFAULT_PRESERVE_BRIGHTNESS
        self.random_state = 42

        super().__init__()

    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield Header()

        with Horizontal():
            with Container(id="left-panel"):
                yield Static("[bold]/[/bold] Search", classes="pane-title")
                yield Search(id="search")
                yield Static("[bold]1[/bold] Themes", classes="pane-title")
                yield Themes(self.color_schemes, id="theme-list")

            with Container(id="right-panel"):
                yield Preview(
                    self.image_cache,
                    self.cell_width_px,
                    self.cell_height_px,
                    id="image-preview",
                )

        yield Footer()

    def on_mount(self) -> None:
        """Set up app on mount."""
        self.load_original_image()
        theme_list = self.query_one("#theme-list", Themes)
        if theme_list.filtered_themes:
            first_theme = theme_list.filtered_themes[0]

            theme_list.highlighted = 0
            self.load_theme_image(first_theme)

            self.set_timer(0.5, self.aggressive_preload)

        theme_list.focus()

    def load_original_image(self) -> None:
        """Load the original image."""
        try:
            if self.image_path.startswith(("http://", "https://")):
                response = requests.get(self.image_path, timeout=30)
                response.raise_for_status()
                self.original_image = Image.open(BytesIO(response.content))
            else:
                if not self.image_path or not isinstance(self.image_path, str):
                    msg = "Invalid image path provided"
                    raise ValueError(msg)
                self.original_image = Image.open(self.image_path)

            if self.original_image.mode != "RGB":
                self.original_image = self.original_image.convert("RGB")

            if self.original_image:
                self.clustering_data = compute_image_clusters(
                    self.original_image,
                    sample_size=self.sampling_size,
                    n_colors=self.color_count,
                )
        except (requests.RequestException, requests.Timeout) as e:
            self.notify(f"Network error loading image: {e}", severity="error")
        except (FileNotFoundError, OSError) as e:
            self.notify(f"File error loading image: {e}", severity="error")
        except ValueError as e:
            self.notify(f"Invalid image data: {e}", severity="error")
        except Exception as e:
            self.notify(f"Unexpected error loading image: {e}", severity="error")

    def _process_theme_background(self, theme_name: str) -> None:
        """Process theme in background thread."""
        if not self.original_image or not self.clustering_data:
            return

        try:
            color_scheme = np.array(
                [
                    [int(hex_color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
                    for hex_color in self.color_schemes[theme_name]
                ],
                dtype=np.float32,
            )

            recolored = apply_color_scheme(
                self.clustering_data,
                color_scheme,
                preserve_brightness=self.preserve_brightness,
            )

            self.call_from_thread(self._update_processed_theme, theme_name, recolored)

        except Exception as e:
            self.call_from_thread(
                self.notify,
                f"Error processing theme {theme_name}: {e}",
                severity="error",
            )

    def _update_processed_theme(self, theme_name: str, image: Image.Image) -> None:
        """Update cache and preview on main thread."""
        self.image_cache.put(theme_name, image)
        # Only update preview if this is still the current theme
        with self.processing_lock:
            if self.current_processing_theme == theme_name:
                self.update_preview(theme_name, image)
                self.current_processing_theme = None

    def load_theme_image(self, theme_name: str) -> None:
        """Load theme image."""
        if not self.original_image or not self.clustering_data:
            return

        cached = self.image_cache.get(theme_name)
        if cached:
            preview = self.query_one("#image-preview", Preview)
            preview.update_image(theme_name, cached)
            return

        with self.processing_lock:
            self.current_processing_theme = theme_name

        self.executor.submit(self._process_theme_background, theme_name)

    def update_preview(self, theme_name: str, image: Image.Image) -> None:
        """Update image preview."""
        preview = self.query_one("#image-preview", Preview)
        preview.update_image(theme_name, image)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "search":
            if self.search_timer:
                self.search_timer.stop()
            self.search_timer = self.set_timer(
                SEARCH_DEBOUNCE_DELAY_SECONDS,
                lambda: self._execute_theme_search(event.value),
            )

    def _execute_theme_search(self, query: str) -> None:
        try:
            theme_list = self.query_one("#theme-list", Themes)
            theme_list.filter_themes(query)
            current_theme = theme_list.get_current_theme()
            if current_theme:
                self.load_theme_image(current_theme)
        except Exception:
            pass

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle theme selection."""
        if event.option_list.id == "theme-list":
            theme_name = event.option.id
            if theme_name:
                self.load_theme_image(theme_name)
                self.preload_adjacent_themes(theme_name)

    def on_option_list_option_highlighted(
        self,
        event: OptionList.OptionHighlighted,
    ) -> None:
        """Handle theme highlighting."""
        if event.option_list.id == "theme-list":
            theme_name = event.option.id if event.option else None
            if theme_name:
                self.load_theme_image(theme_name)

    def on_slider_changed(self, event: Slider.Changed) -> None:
        """Handle slider value changes - only update labels."""
        slider = event.control
        slider_id = slider.id
        value = int(slider.value)

        if slider_id == "sampling-size-control":
            label = self.query_one("#sampling-size-value", Label)
            label.update(f"{value} pixels")
        elif slider_id == "color-count-control":
            label = self.query_one("#color-count-value", Label)
            label.update(f"{value} colors")
        elif slider_id == "max-iterations-control":
            label = self.query_one("#max-iterations-value", Label)
            label.update(f"{value}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "apply-settings-button":
            self.apply_settings()
        elif event.button.id == "reset-defaults-button":
            self.restore_default_settings()

    def apply_settings(self) -> None:
        """Apply current configuration and reprocess the selected image.

        Reads current values from all UI controls, updates internal settings,
        and triggers image recoloring with the new parameters. Provides user
        feedback upon successful completion.
        """
        try:
            sample_slider = self.query_one("#sampling-size-control", Slider)
            colors_slider = self.query_one("#color-count-control", Slider)
            iter_slider = self.query_one("#max-iterations-control", Slider)
            brightness_checkbox = self.query_one(
                "#preserve-brightness-checkbox",
                Checkbox,
            )

            sampling_size = int(sample_slider.value)
            color_count = int(colors_slider.value)
            max_iterations = int(iter_slider.value)

            if sampling_size < MIN_SAMPLING_SIZE or sampling_size > MAX_SAMPLING_SIZE:
                msg = (
                    f"Sampling size must be between {MIN_SAMPLING_SIZE:,} "
                    f"and {MAX_SAMPLING_SIZE:,}"
                )
                raise ValueError(msg)
            if color_count < MIN_COLOR_COUNT or color_count > MAX_COLOR_COUNT:
                msg = (
                    f"Color count must be between {MIN_COLOR_COUNT} "
                    f"and {MAX_COLOR_COUNT}"
                )
                raise ValueError(msg)
            if (
                max_iterations < MIN_MAX_ITERATIONS
                or max_iterations > MAX_MAX_ITERATIONS
            ):
                msg = (
                    f"Max iterations must be between {MIN_MAX_ITERATIONS} "
                    f"and {MAX_MAX_ITERATIONS}"
                )
                raise ValueError(msg)

            self.sampling_size = sampling_size
            self.color_count = color_count
            self.max_iterations = max_iterations
            self.preserve_brightness = brightness_checkbox.value
        except ValueError as e:
            self.notify(f"Invalid settings: {e}", severity="error")
            return
        except Exception as e:
            self.notify(f"Error reading settings: {e}", severity="error")
            return

        settings_panel = self.query_one("#settings-panel", Settings)
        settings_panel.sampling_size = self.sampling_size
        settings_panel.color_count = self.color_count
        settings_panel.max_iterations = self.max_iterations
        settings_panel.preserve_brightness = self.preserve_brightness

        if (
            self.sampling_size != settings_panel.sampling_size
            or self.color_count != settings_panel.color_count
        ) and self.original_image:
            self.clustering_data = compute_image_clusters(
                self.original_image,
                sample_size=self.sampling_size,
                n_colors=self.color_count,
            )
            self.image_cache = ImageCache()

        theme_list = self.query_one("#theme-list", Themes)
        current_theme = theme_list.get_current_theme()
        if current_theme:
            if current_theme in self.image_cache.cache:
                del self.image_cache.cache[current_theme]
                self.image_cache.access_order.remove(current_theme)
            self.load_theme_image(current_theme)
            self.notify(
                "Configuration applied successfully",
                timeout=NOTIFICATION_TIMEOUT_SECONDS,
            )

    def restore_default_settings(self) -> None:
        """Reset all configuration parameters to their default values.

        Restores all UI controls and internal settings to their original
        default state and provides user confirmation of the action.
        """
        sample_slider = self.query_one("#sampling-size-control", Slider)
        colors_slider = self.query_one("#color-count-control", Slider)
        iter_slider = self.query_one("#max-iterations-control", Slider)
        brightness_checkbox = self.query_one("#preserve-brightness-checkbox", Checkbox)

        sample_slider.value = self.DEFAULT_SAMPLING_SIZE
        colors_slider.value = self.DEFAULT_COLOR_COUNT
        iter_slider.value = self.DEFAULT_MAX_ITERATIONS
        brightness_checkbox.value = self.DEFAULT_PRESERVE_BRIGHTNESS

        self.sampling_size = self.DEFAULT_SAMPLING_SIZE
        self.color_count = self.DEFAULT_COLOR_COUNT
        self.max_iterations = self.DEFAULT_MAX_ITERATIONS
        self.preserve_brightness = self.DEFAULT_PRESERVE_BRIGHTNESS

        sample_label = self.query_one("#sampling-size-value", Label)
        colors_label = self.query_one("#color-count-value", Label)
        iter_label = self.query_one("#max-iterations-value", Label)

        sample_label.update(f"{self.DEFAULT_SAMPLING_SIZE} pixels")
        colors_label.update(f"{self.DEFAULT_COLOR_COUNT} colors")
        iter_label.update(f"{self.DEFAULT_MAX_ITERATIONS}")

        settings_panel = self.query_one("#settings-panel", Settings)
        settings_panel.sampling_size = self.DEFAULT_SAMPLING_SIZE
        settings_panel.color_count = self.DEFAULT_COLOR_COUNT
        settings_panel.max_iterations = self.DEFAULT_MAX_ITERATIONS
        settings_panel.preserve_brightness = self.DEFAULT_PRESERVE_BRIGHTNESS

        self.notify(
            "Settings restored to default values", timeout=NOTIFICATION_TIMEOUT_SECONDS
        )

    def preload_adjacent_themes(self, current_theme: str) -> None:
        """Preload themes around current selection for smooth scrolling."""
        theme_list = self.query_one("#theme-list", Themes)
        try:
            current_idx = theme_list.filtered_themes.index(current_theme)
            for offset in [-3, -2, -1, 1, 2, 3]:
                idx = current_idx + offset
                if 0 <= idx < len(theme_list.filtered_themes):
                    theme_name = theme_list.filtered_themes[idx]
                    if not self.image_cache.get(theme_name):
                        self.executor.submit(self._process_theme_background, theme_name)
        except ValueError:
            pass

    def aggressive_preload(self) -> None:
        """Aggressively preload all visible themes for instant switching."""
        theme_list = self.query_one("#theme-list", Themes)
        if not theme_list.filtered_themes:
            return

        current_idx = theme_list.highlighted or 0

        for offset in range(-5, 6):
            idx = current_idx + offset
            if 0 <= idx < len(theme_list.filtered_themes):
                theme_name = theme_list.filtered_themes[idx]
                if not self.image_cache.get(theme_name):
                    self.executor.submit(self._process_theme_background, theme_name)

    def action_save(self) -> None:
        """Save the current image to a PNG file."""
        preview = self.query_one("#image-preview", Preview)
        if preview.current_image:
            try:
                filename = f"output_{preview.current_theme}.png"
                preview.current_image.save(filename, optimize=False, compress_level=0)
                self.notify(f"Saved as {filename}", severity="information")
            except Exception as e:
                self.notify(f"Error saving: {e}", severity="error")

    def action_copy(self) -> None:
        """Copy the current image to the system clipboard."""
        preview = self.query_one("#image-preview", Preview)
        if preview.current_image:
            try:
                with tempfile.NamedTemporaryFile(
                    suffix=".png",
                    delete=False,
                ) as tmp_file:
                    preview.current_image.save(
                        tmp_file.name,
                        optimize=False,
                        compress_level=0,
                    )

                    tmp_path = pathlib.Path(tmp_file.name)
                    with tmp_path.open("rb") as f:
                        subprocess.Popen(
                            ["/usr/bin/wl-copy", "--type", "image/png"],
                            stdin=f,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            start_new_session=True,
                            close_fds=True,
                        )
                    self.notify("Copied to clipboard!", severity="information")
            except Exception as e:
                self.notify(f"Copy failed: {e}", severity="error")

    def action_focus_search(self) -> None:
        """Focus the search input (/)."""
        if self.focused and self.focused.id in ["theme-list", "settings-panel"]:
            self.previous_panel_focus = self.focused.id
        elif (
            self.focused
            and hasattr(self.focused, "parent")
            and self.focused.parent
            and self.focused.parent.id == "settings-panel"
        ):
            self.previous_panel_focus = "settings-panel"

        search_input = self.query_one("#search", Search)
        search_input.focus()

    def action_focus_themes(self) -> None:
        """Focus the theme list (1)."""
        theme_list = self.query_one("#theme-list", Themes)
        theme_list.focus()
        self.previous_panel_focus = "theme-list"

    def action_focus_settings(self) -> None:
        """Focus the settings panel (2)."""
        first_slider = self.query_one("#sampling-size-control", Slider)
        first_slider.focus()
        self.previous_panel_focus = "settings-panel"

    def action_smart_escape(self) -> None:
        """Smart escape: go back to previous panel."""
        search_input = self.query_one("#search", Search)
        if search_input.has_focus:
            if self.previous_panel_focus == "theme-list":
                self.action_focus_themes()
            else:
                self.action_focus_settings()
        else:
            pass

    def on_unmount(self) -> None:
        """Clean up resources when app is unmounted."""
        self.executor.shutdown(wait=True)

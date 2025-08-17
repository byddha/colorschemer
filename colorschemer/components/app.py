"""Main application component for the color schemer."""

import threading
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Any

import numpy as np
import pyperclipimg
import requests
from PIL import Image
from textual.app import App as TextualApp
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    OptionList,
    Static,
)
from textual_slider import Slider

from colorschemer.utils.cache import ImageCache

from .preview import Preview
from .search import Search
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

    def __init__(  # noqa: PLR0913
        self,
        image_path: str,
        color_schemes: dict[str, list[str]],
        extractor: Any,  # noqa: ANN401
        settings: Any,  # noqa: ANN401
        cell_width_px: float,
        cell_height_px: float,
    ) -> None:
        """Initialize the app."""
        self.image_path = image_path
        self.color_schemes = color_schemes
        self.extractor = extractor
        self.settings_component = settings
        self.cell_width_px = cell_width_px
        self.cell_height_px = cell_height_px
        self.image_cache = ImageCache()
        self.original_image: Image.Image | None = None
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
            self.detected_color_count = detected_color_count

        super().__init__()

    def _get_cache_key(self, theme_name: str) -> str:
        """Generate cache key including extractor and parameters."""
        params = self.settings_component.get_parameters()
        extractor_key = self.extractor.get_cache_key(**params)
        return f"{theme_name}_{extractor_key}"

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
                yield Static("[bold]2[/bold] Settings", classes="pane-title")
                self.settings_component.id = "settings-panel"
                yield self.settings_component

        yield Footer()

    def on_mount(self) -> None:
        """Set up app on mount."""
        # Update settings component with detected color count now that widgets exist
        if hasattr(self, "detected_color_count"):
            self.settings_component.set_parameters(n_colors=self.detected_color_count)

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
        if not self.original_image:
            return

        try:
            color_scheme = np.array(
                [
                    [int(hex_color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
                    for hex_color in self.color_schemes[theme_name]
                ],
                dtype=np.float32,
            )

            params = self.settings_component.get_parameters()
            recolored = self.extractor.recolor_image(
                self.original_image,
                color_scheme,
                **params,
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
        cache_key = self._get_cache_key(theme_name)
        self.image_cache.put(cache_key, image)
        # Only update preview if this is still the current theme
        with self.processing_lock:
            if self.current_processing_theme == theme_name:
                self.update_preview(theme_name, image)
                self.current_processing_theme = None

    def load_theme_image(self, theme_name: str) -> None:
        """Load theme image."""
        if not self.original_image:
            return

        cache_key = self._get_cache_key(theme_name)
        cached = self.image_cache.get(cache_key)
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
        self.settings_component.get_parameters()

        # Clear cache since settings changed
        self.image_cache = ImageCache()

        theme_list = self.query_one("#theme-list", Themes)
        current_theme = theme_list.get_current_theme()
        if current_theme:
            cache_key = self._get_cache_key(current_theme)
            if cache_key in self.image_cache.cache:
                del self.image_cache.cache[cache_key]
                self.image_cache.access_order.remove(cache_key)
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
        self.settings_component.reset_defaults()

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
                    cache_key = self._get_cache_key(theme_name)
                    if not self.image_cache.get(cache_key):
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
                cache_key = self._get_cache_key(theme_name)
                if not self.image_cache.get(cache_key):
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
                pyperclipimg.copy(preview.current_image)
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

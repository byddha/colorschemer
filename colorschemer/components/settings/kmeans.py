"""K-means specific settings component."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Checkbox, Label
from textual_slider import Slider

DEFAULT_SAMPLING_SIZE = 50000
DEFAULT_COLOR_COUNT = 8
DEFAULT_MAX_ITERATIONS = 100
DEFAULT_PRESERVE_BRIGHTNESS = True
DEFAULT_RANDOM_STATE = 42


class KmeansSettings(Container):
    """K-means settings panel for image processing."""

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        """Set up settings panel with defaults."""
        self.sampling_size = DEFAULT_SAMPLING_SIZE
        self.color_count = DEFAULT_COLOR_COUNT
        self.max_iterations = DEFAULT_MAX_ITERATIONS
        self.preserve_brightness = DEFAULT_PRESERVE_BRIGHTNESS
        self.random_state = DEFAULT_RANDOM_STATE
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Build the k-means settings UI."""
        with Vertical():
            with Horizontal(classes="parameter-controls-row"):
                with Container(classes="parameter-control-group"):
                    yield Label("Sample Size", classes="parameter-label")
                    yield Slider(
                        min=1000,
                        max=100000,
                        value=self.sampling_size,
                        step=1000,
                        id="sampling-size-control",
                    )
                    yield Label(
                        f"{self.sampling_size} pixels",
                        id="sampling-size-value",
                    )

                with Container(classes="parameter-control-group"):
                    yield Label("Color Count", classes="parameter-label")
                    yield Slider(
                        min=4,
                        max=16,
                        value=self.color_count,
                        step=1,
                        id="color-count-control",
                    )
                    yield Label(f"{self.color_count} colors", id="color-count-value")

                with Container(classes="parameter-control-group"):
                    yield Label("Max Iterations", classes="parameter-label")
                    yield Slider(
                        min=50,
                        max=500,
                        value=self.max_iterations,
                        step=10,
                        id="max-iterations-control",
                    )
                    yield Label(f"{self.max_iterations}", id="max-iterations-value")

            with Horizontal(classes="action-controls-section"):
                yield Checkbox(
                    "Preserve Brightness",
                    self.preserve_brightness,
                    id="preserve-brightness-checkbox",
                )
                yield Button(
                    "Apply",
                    id="apply-settings-button",
                    variant="primary",
                )
                yield Button(
                    "Reset",
                    id="reset-defaults-button",
                    variant="default",
                )

    def get_parameters(self) -> dict[str, Any]:
        """Get current parameter values from UI."""
        sample_slider = self.query_one("#sampling-size-control", Slider)
        color_slider = self.query_one("#color-count-control", Slider)
        iter_slider = self.query_one("#max-iterations-control", Slider)
        brightness_checkbox = self.query_one("#preserve-brightness-checkbox", Checkbox)

        return {
            "sample_size": int(sample_slider.value),
            "n_colors": int(color_slider.value),
            "max_iterations": int(iter_slider.value),
            "preserve_brightness": brightness_checkbox.value,
            "random_state": self.random_state,
        }

    def set_parameters(self, **kwargs) -> None:  # noqa: ANN003
        """Set parameter values in UI."""
        if "sample_size" in kwargs:
            self.sampling_size = kwargs["sample_size"]
            sample_slider = self.query_one("#sampling-size-control", Slider)
            sample_slider.value = kwargs["sample_size"]
            sample_label = self.query_one("#sampling-size-value", Label)
            sample_label.update(f"{kwargs['sample_size']} pixels")

        if "n_colors" in kwargs:
            self.color_count = kwargs["n_colors"]
            color_slider = self.query_one("#color-count-control", Slider)
            color_slider.value = kwargs["n_colors"]
            color_label = self.query_one("#color-count-value", Label)
            color_label.update(f"{kwargs['n_colors']} colors")

        if "max_iterations" in kwargs:
            self.max_iterations = kwargs["max_iterations"]
            iter_slider = self.query_one("#max-iterations-control", Slider)
            iter_slider.value = kwargs["max_iterations"]
            iter_label = self.query_one("#max-iterations-value", Label)
            iter_label.update(f"{kwargs['max_iterations']}")

        if "preserve_brightness" in kwargs:
            self.preserve_brightness = kwargs["preserve_brightness"]
            brightness_checkbox = self.query_one(
                "#preserve-brightness-checkbox", Checkbox
            )
            brightness_checkbox.value = kwargs["preserve_brightness"]

        if "random_state" in kwargs:
            self.random_state = kwargs["random_state"]

    def reset_defaults(self) -> None:
        """Reset all parameters to default values."""
        self.set_parameters(
            sample_size=DEFAULT_SAMPLING_SIZE,
            n_colors=DEFAULT_COLOR_COUNT,
            max_iterations=DEFAULT_MAX_ITERATIONS,
            preserve_brightness=DEFAULT_PRESERVE_BRIGHTNESS,
            random_state=DEFAULT_RANDOM_STATE,
        )

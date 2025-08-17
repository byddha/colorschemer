"""Settings panel component for image processing configuration."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Checkbox, Label
from textual_slider import Slider

DEFAULT_SAMPLING_SIZE = 50000
DEFAULT_COLOR_COUNT = 8
DEFAULT_MAX_ITERATIONS = 100
DEFAULT_PRESERVE_BRIGHTNESS = True
DEFAULT_RANDOM_STATE = 42


class Settings(Container):
    """Settings panel for image processing."""

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        """Set up settings panel with defaults."""
        self.sampling_size = DEFAULT_SAMPLING_SIZE
        self.color_count = DEFAULT_COLOR_COUNT
        self.max_iterations = DEFAULT_MAX_ITERATIONS
        self.preserve_brightness = DEFAULT_PRESERVE_BRIGHTNESS
        self.random_state = DEFAULT_RANDOM_STATE
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Build the settings UI."""
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

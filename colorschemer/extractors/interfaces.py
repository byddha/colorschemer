"""Core interfaces for color extraction system."""

from abc import abstractmethod
from typing import Any, Protocol

import numpy as np
from PIL import Image
from textual.app import ComposeResult


class ColorExtractor(Protocol):
    """Interface for color extraction algorithms."""

    @abstractmethod
    def recolor_image(
        self,
        image: Image.Image,
        color_scheme: np.ndarray,
        **kwargs,  # noqa: ANN003
    ) -> Image.Image:
        """Recolor image using the color scheme."""

    @abstractmethod
    def get_cache_key(self, **kwargs) -> str:  # noqa: ANN003
        """Generate cache key for the extractor with given parameters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the extraction method."""


class SettingsComponent(Protocol):
    """Interface for settings UI components."""

    @abstractmethod
    def compose(self) -> ComposeResult:
        """Compose the settings UI."""

    @abstractmethod
    def get_parameters(self) -> dict[str, Any]:
        """Get current parameter values from UI."""

    @abstractmethod
    def set_parameters(self, **kwargs) -> None:  # noqa: ANN003
        """Set parameter values in UI."""

    @abstractmethod
    def reset_defaults(self) -> None:
        """Reset all parameters to default values."""

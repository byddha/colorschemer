"""Theme data container for color schemes."""


class ThemeData:
    """Container for theme data with name and color information."""

    def __init__(self, name: str, colors: list[str]) -> None:
        """Initialize theme data with name and hex color list."""
        self.name = name
        self.colors = colors
        self._rgb_colors = None

    @property
    def rgb_colors(self) -> list[tuple[int, int, int]]:
        """Convert hex colors to RGB tuples."""
        if self._rgb_colors is None:
            self._rgb_colors = [
                (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))
                for color in self.colors
            ]
        return self._rgb_colors

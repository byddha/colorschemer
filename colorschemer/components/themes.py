"""Theme list component for browsing and selecting color schemes."""

from textual.widgets import OptionList
from textual.widgets.option_list import Option

from colorschemer.theme_data import ThemeData


def create_theme_display(theme_name: str, theme_colors: list[str]) -> str:
    """Make colored text display for theme."""
    theme_data = ThemeData(theme_name, theme_colors)
    color_blocks = ""
    num_colors = min(len(theme_data.rgb_colors), 16)
    for r, g, b in theme_data.rgb_colors[:num_colors]:
        color_blocks += f"[rgb({r},{g},{b})]██[/]"

    return f"{theme_name}\n{color_blocks}"


class Themes(OptionList):
    """Theme list with vim-like navigation."""

    BINDINGS = [
        ("k,up", "cursor_up", "Up"),
        ("j,down", "cursor_down", "Down"),
        ("g", "prepare_go_to_first", "Go first"),
        ("G", "go_to_last", "Go last"),
    ]

    def __init__(self, themes: dict[str, list[str]], **kwargs) -> None:  # noqa: ANN003
        """Init theme list widget."""
        self.themes = themes
        self.filtered_themes = list(themes.keys())
        self.pending_g = False  # Track if 'g' was pressed for 'gg' sequence
        super().__init__(**kwargs)

    def on_mount(self) -> None:
        """When widget mounts, populate the list."""
        self._populate_list()

    def _populate_list(self) -> None:
        self.clear_options()
        for theme_name in self.filtered_themes:
            display_text = create_theme_display(theme_name, self.themes[theme_name])
            self.add_option(Option(display_text, id=theme_name))

    def filter_themes(self, query: str) -> None:
        """Filter themes based on search."""
        old_filtered = self.filtered_themes.copy()

        if query:
            self.filtered_themes = [
                name for name in self.themes if query.lower() in name.lower()
            ]
        else:
            self.filtered_themes = list(self.themes.keys())

        if old_filtered != self.filtered_themes:
            self._populate_list()

    def get_current_theme(self) -> str | None:
        """Get selected theme name."""
        if self.highlighted is not None:
            option = self.get_option_at_index(self.highlighted)
            if option and hasattr(option, "id"):
                return option.id
        return None

    def action_prepare_go_to_first(self) -> None:
        """Handle first 'g' press - wait for second 'g' for 'gg' sequence."""
        if self.pending_g:
            self.action_go_to_first()
            self.pending_g = False
        else:
            self.pending_g = True
            self.set_timer(1.0, self._reset_pending_g)

    def action_go_to_first(self) -> None:
        """Go to first theme (gg)."""
        if self.option_count > 0:
            self.highlighted = 0

    def action_go_to_last(self) -> None:
        """Go to last theme (G)."""
        if self.option_count > 0:
            self.highlighted = self.option_count - 1

    def _reset_pending_g(self) -> None:
        """Reset the pending 'g' state after timeout."""
        self.pending_g = False

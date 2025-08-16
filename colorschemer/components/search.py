"""Search input component for filtering themes."""

from textual.widgets import Input


class Search(Input):
    """Theme search input."""

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        super().__init__(placeholder="Search themes...", **kwargs)

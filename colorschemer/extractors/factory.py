"""Factory for creating color extractors."""

from colorschemer.components.settings.kmeans import KmeansSettings

from .interfaces import ColorExtractor, SettingsComponent
from .kmeans import KmeansExtractor


class ExtractorFactory:
    """Factory for creating color extractor instances."""

    _extractors: dict[str, type[ColorExtractor]] = {}
    _settings: dict[str, type[SettingsComponent]] = {}

    @classmethod
    def register(
        cls,
        name: str,
        extractor_class: type[ColorExtractor],
        settings_class: type[SettingsComponent],
    ) -> None:
        """Register an extractor and its settings component."""
        cls._extractors[name] = extractor_class
        cls._settings[name] = settings_class

    @classmethod
    def create_extractor(cls, name: str) -> ColorExtractor:
        """Create an extractor instance by name."""
        if name not in cls._extractors:
            available = ", ".join(cls._extractors.keys())
            msg = f"Unknown extractor '{name}'. Available: {available}"
            raise ValueError(msg)
        return cls._extractors[name]()

    @classmethod
    def create_settings(cls, name: str) -> SettingsComponent:
        """Create a settings component instance by name."""
        if name not in cls._settings:
            available = ", ".join(cls._settings.keys())
            msg = f"Unknown settings '{name}'. Available: {available}"
            raise ValueError(msg)
        return cls._settings[name]()

    @classmethod
    def get_available_methods(cls) -> list[str]:
        """Get list of available extraction methods."""
        return list(cls._extractors.keys())


# Register extractors here
def _register_extractors() -> None:
    """Register all available extractors."""
    ExtractorFactory.register("kmeans", KmeansExtractor, KmeansSettings)


_register_extractors()

"""LRU cache for processed images."""

from PIL import Image

CACHE_SIZE_LIMIT = 50


class ImageCache:
    """LRU cache for processed images."""

    def __init__(self, max_size: int = CACHE_SIZE_LIMIT) -> None:
        self.cache: dict[str, Image.Image] = {}
        self.max_size = max_size
        self.access_order: list[str] = []

    def get(self, key: str) -> Image.Image | None:
        if key in self.cache:
            self.access_order.remove(key)
            self.access_order.append(key)
            return self.cache[key]
        return None

    def put(self, key: str, image: Image.Image) -> None:
        if key in self.cache:
            self.access_order.remove(key)
        elif len(self.cache) >= self.max_size:
            oldest = self.access_order.pop(0)
            del self.cache[oldest]

        self.cache[key] = image
        self.access_order.append(key)

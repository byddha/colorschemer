"""K-means clustering color extractor."""


import numpy as np
from PIL import Image
from sklearn.cluster import KMeans


class KmeansExtractor:
    """K-means clustering color extractor."""

    @property
    def name(self) -> str:
        """Name of the extraction method."""
        return "kmeans"

    def recolor_image(  # noqa: PLR0913
        self,
        image: Image.Image,
        color_scheme: np.ndarray,
        sample_size: int = 50000,
        n_colors: int = 8,
        max_iterations: int = 100,
        random_state: int = 42,
        preserve_brightness: bool = True,  # noqa: FBT001, FBT002
        **_kwargs,  # noqa: ANN003
    ) -> Image.Image:
        """Recolor image using k-means clustering."""
        # Extract colors
        image_array = np.array(image, dtype=np.uint8)
        h, w, c = image_array.shape
        pixels = image_array.reshape(-1, 3)

        if len(pixels) > sample_size:
            rng = np.random.default_rng()
            sample_indices = rng.choice(len(pixels), sample_size, replace=False)
            sample_pixels = pixels[sample_indices].astype(np.float32)
        else:
            sample_pixels = pixels.astype(np.float32)

        kmeans = KMeans(
            n_clusters=n_colors,
            random_state=random_state,
            n_init="auto",
            init="k-means++",
            max_iter=max_iterations,
        )
        _ = kmeans.fit(sample_pixels)

        pixels_float = pixels.astype(np.float32)
        labels = kmeans.predict(pixels_float)
        dominant_colors = kmeans.cluster_centers_

        # Apply colors
        dom_brightness = np.mean(dominant_colors, axis=1)
        theme_brightness = np.mean(color_scheme, axis=1)

        dom_order = np.argsort(dom_brightness)
        theme_order = np.argsort(theme_brightness)

        mapping = np.empty_like(dominant_colors)

        min_len = min(len(dom_order), len(theme_order))
        if min_len > 0:
            mapping[dom_order[:min_len]] = color_scheme[theme_order[:min_len]]

        if min_len < len(dom_order):
            for i in range(min_len, len(dom_order)):
                dom_idx = dom_order[i]
                diff = color_scheme - dominant_colors[dom_idx]
                distances = np.sum(
                    diff * diff,
                    axis=1,
                )
                mapping[dom_idx] = color_scheme[np.argmin(distances)]

        new_pixels = mapping[labels]

        if preserve_brightness:
            original_brightness = np.mean(pixels_float, axis=1, keepdims=True)
            new_brightness = np.mean(new_pixels, axis=1, keepdims=True)
            new_brightness = np.maximum(new_brightness, 1e-6)
            brightness_ratio = original_brightness / new_brightness
            new_pixels *= brightness_ratio
            new_pixels = np.clip(new_pixels, 0, 255)

        new_image_array = new_pixels.reshape(h, w, c).astype(np.uint8)
        return Image.fromarray(new_image_array)

    def get_cache_key(
        self,
        sample_size: int = 50000,
        n_colors: int = 8,
        max_iterations: int = 100,
        random_state: int = 42,
        preserve_brightness: bool = True,  # noqa: FBT001, FBT002
        **_kwargs,  # noqa: ANN003
    ) -> str:
        """Generate cache key for k-means parameters."""
        return f"kmeans_{sample_size}_{n_colors}_{max_iterations}_{random_state}_{preserve_brightness}"  # noqa: E501

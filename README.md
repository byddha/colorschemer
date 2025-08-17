# colorschemer

TUI for recoloring images using common colorschemes. There are 424 colorschemes available with default settings. Uses K-means clustering to map colors by brightness, maybe other algorithms later / improve current one. For now I got the wallpapers i wanted :) 

## Requirements
Terminal with good image rendering support (kitty terminal graphics protocol or Sixel)

## Install

```bash
uv tool install git+https://github.com/drzbida/colorschemer/
```

## Usage

```bash
colorschemer path/to/image.jpg
colorschemer --theme-file base16 image.png
colorschemer --method kmeans https://example.com/image.jpg
```

## Demo

https://github.com/user-attachments/assets/e8e968eb-876f-4027-b7e1-d633469ed5f2


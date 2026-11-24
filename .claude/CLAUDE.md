# VIDEO_DOWNLOAD project rules

- `download.py` is the one script in this repo
- `download.py` calls the `yt_dlp` Python library
- The installed `yt_dlp` is the apt package in `/usr/lib/python3/dist-packages/yt_dlp`
- `download.py` needs `ffmpeg` and `node` on `PATH`
- Each `#+OUTPUT:` line in `CMD.org` names where that block writes
- Read `#+OUTPUT:` lines and `download.py` for output paths
- `.gitignore` lists `OUTPUT/`
- Run commands live in `CMD.org` in the format `rd_cmd` parses
- Planned work lives under `.claude/PLANS/` in the `rd_plan` layout

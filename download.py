#!/usr/bin/env python3
"""Download YouTube videos using yt-dlp."""

import argparse
import glob
import os
import sys
import yt_dlp


def _find_ffmpeg() -> str | None:
    """Return ffmpeg bin dir if found in WinGet packages, otherwise None."""
    pattern = os.path.expandvars(
        r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\*\bin\ffmpeg.exe"
    )
    matches = glob.glob(pattern)
    if matches:
        return os.path.dirname(matches[0])
    return None


def download(url: str, output_dir: str = ".", quality: str = "best", browser: str | None = None) -> None:
    quality_formats = {
        "best": "bestvideo+bestaudio/best",
        "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "audio": "bestaudio/best",
    }

    ydl_opts = {
        "format": quality_formats.get(quality, quality_formats["best"]),
        "outtmpl": f"{output_dir}/%(title)s.%(ext)s",
        "merge_output_format": "mp4",
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:github"],
    }

    ffmpeg_dir = _find_ffmpeg()
    if ffmpeg_dir:
        ydl_opts["ffmpeg_location"] = ffmpeg_dir

    if browser:
        ydl_opts["cookiesfrombrowser"] = (browser,)

    if quality == "audio":
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def main() -> None:
    parser = argparse.ArgumentParser(description="Download a YouTube video.")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument(
        "-o", "--output", default=".", metavar="DIR", help="Output directory (default: current directory)"
    )
    parser.add_argument(
        "-q",
        "--quality",
        choices=["best", "1080p", "720p", "480p", "audio"],
        default="best",
        help="Download quality (default: best)",
    )
    parser.add_argument(
        "-b",
        "--browser",
        choices=["chrome", "edge", "firefox", "brave", "opera", "chromium"],
        default=None,
        metavar="BROWSER",
        help="Pass cookies from browser to bypass bot detection (e.g. chrome, edge, firefox)",
    )
    args = parser.parse_args()

    try:
        download(args.url, args.output, args.quality, args.browser)
    except yt_dlp.utils.DownloadError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

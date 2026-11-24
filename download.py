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
        bin_dir = os.path.dirname(matches[0])
        if bin_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
        return bin_dir
    return None


def download(url: str, output_dir: str = ".", quality: str = "best", browser: str | None = None, time_range: str | None = None,
             subs: bool = False) -> None:
    quality_formats = {
        "best": "bestvideo+bestaudio/best",
        "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "audio": "bestaudio/best",
    }

    if subs:
        kind_dir = "SUBTITLE"
    elif quality == "audio":
        kind_dir = "AUDIO"
    else:
        kind_dir = "VIDEO"

    ydl_opts = {
        "format": quality_formats.get(quality, quality_formats["best"]),
        "outtmpl": f"{output_dir}/{kind_dir}/%(title)s.%(ext)s",
        "merge_output_format": "mp4",
        "js_runtimes": {"node": {}},
        "remote_components": ["ejs:github"],
    }

    ffmpeg_dir = _find_ffmpeg()
    if ffmpeg_dir:
        ydl_opts["ffmpeg_location"] = ffmpeg_dir

    if browser:
        ydl_opts["cookiesfrombrowser"] = (browser,)

    if time_range:
        start_str, end_str = time_range.split("-", 1)
        def _to_seconds(t: str) -> float:
            parts = list(map(float, t.split(":")))
            return sum(p * 60 ** (len(parts) - 1 - i) for i, p in enumerate(parts))
        ydl_opts["download_ranges"] = yt_dlp.utils.download_range_func(
            None, [(_to_seconds(start_str), _to_seconds(end_str))]
        )
        ydl_opts["force_keyframes_at_cuts"] = True

    if quality == "audio":
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]

    if subs:
        ydl_opts["skip_download"] = True
        ydl_opts["writesubtitles"] = True
        ydl_opts["writeautomaticsub"] = True
        ydl_opts["subtitleslangs"] = ["en"]
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegSubtitlesConvertor",
                "format": "srt",
                "when": "before_dl",
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
    parser.add_argument(
        "-t",
        "--time",
        default=None,
        metavar="START-END",
        help="Time range to download, e.g. 00:01:00-00:02:30",
    )
    parser.add_argument(
        "-s",
        "--subs",
        action="store_true",
        help="Download English captions as an .srt file and skip the video",
    )
    args = parser.parse_args()

    try:
        download(args.url, args.output, args.quality, args.browser, args.time, args.subs)
    except yt_dlp.utils.DownloadError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

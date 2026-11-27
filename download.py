#!/usr/bin/env python3
"""Download YouTube videos using yt-dlp."""

import argparse
import glob
import os
import subprocess
import sys
import yt_dlp

KINDS = ["video", "audio", "subtitle"]
QUALITIES = ["best", "1080p", "720p", "480p"]
BROWSERS = ["chrome", "edge", "firefox", "brave", "opera", "chromium"]


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


def download(url: str, output_dir: str, kind: str, quality: str, browser: str | None, time_range: str | None,
             lang: str) -> str | None:
    quality_formats = {
        "best": "bestvideo+bestaudio/best",
        "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    }

    if kind == "subtitle":
        kind_dir = "SUBTITLE"
    elif kind == "audio":
        kind_dir = "AUDIO"
    else:
        kind_dir = "VIDEO"

    if kind == "audio":
        format_selector = "bestaudio/best"
    else:
        format_selector = quality_formats[quality]

    ydl_opts = {
        "format": format_selector,
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

    if kind == "audio":
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]

    if kind == "subtitle":
        ydl_opts["skip_download"] = True
        ydl_opts["writesubtitles"] = True
        ydl_opts["writeautomaticsub"] = True
        ydl_opts["subtitleslangs"] = [lang]
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegSubtitlesConvertor",
                "format": "srt",
                "when": "before_dl",
            }
        ]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    downloads = info.get("requested_downloads", [])
    if len(downloads) == 0:
        return None
    return downloads[0]["filepath"]


def extract_audio(video_path: str, output_dir: str) -> None:
    audio_dir = os.path.join(output_dir, "AUDIO")
    os.makedirs(audio_dir, exist_ok=True)
    video_name = os.path.basename(video_path)
    stem, _ = os.path.splitext(video_name)
    audio_path = os.path.join(audio_dir, stem + ".mp3")
    command = [
        "ffmpeg", "-hide_banner", "-y",
        "-i", video_path,
        "-vn",
        "-codec:a", "libmp3lame",
        "-b:a", "192k",
        audio_path,
    ]
    subprocess.run(command, check=True)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download a YouTube video.")
    parser.add_argument("url", nargs="?", default=None, help="YouTube video URL (omit it to answer prompts)")
    parser.add_argument(
        "-o", "--output", default=".", metavar="DIR", help="Output directory (default: current directory)"
    )
    parser.add_argument(
        "-k",
        "--kind",
        dest="kinds",
        nargs="+",
        choices=KINDS,
        default=["video"],
        help="One or more of: video as mp4, audio as mp3, subtitle as srt (default: video)",
    )
    parser.add_argument(
        "-q",
        "--quality",
        choices=QUALITIES,
        default="best",
        help="Video quality (default: best)",
    )
    parser.add_argument(
        "-b",
        "--browser",
        choices=BROWSERS,
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
        "-l",
        "--lang",
        default="en",
        metavar="LANG",
        help="Subtitle language code (default: en)",
    )
    return parser.parse_args()


def prompt_choice(label: str, choices: list[str], default: str) -> str:
    choice_list = "/".join(choices)
    while True:
        answer = input(f"{label} [{choice_list}] ({default}): ")
        answer = answer.strip()
        if answer == "":
            return default
        if answer in choices:
            return answer
        print(f"Choose one of: {choice_list}")


def prompt_yes_no(question: str, default: bool) -> bool:
    if default:
        hint = "Y/n"
    else:
        hint = "y/N"
    while True:
        answer = input(f"{question} [{hint}]: ")
        answer = answer.strip()
        answer = answer.lower()
        if answer == "":
            return default
        if answer in ["y", "yes"]:
            return True
        if answer in ["n", "no"]:
            return False
        print("Answer y or n")


def prompt_options(args: argparse.Namespace) -> argparse.Namespace:
    url = ""
    while url == "":
        url = input("URL: ")
        url = url.strip()
    args.url = url

    kinds = []
    if prompt_yes_no("Download Video?", True):
        kinds.append("video")
    if prompt_yes_no("Download Separated Audio?", True):
        kinds.append("audio")
    if prompt_yes_no("Download Subtitles?", True):
        kinds.append("subtitle")
    args.kinds = kinds
    if len(args.kinds) == 0:
        return args

    if "video" in args.kinds:
        args.quality = prompt_choice("Quality", QUALITIES, args.quality)

    if "subtitle" in args.kinds:
        lang = input(f"Subtitle language ({args.lang}): ")
        lang = lang.strip()
        if lang != "":
            args.lang = lang

    output = input(f"Output directory ({args.output}): ")
    output = output.strip()
    if output != "":
        args.output = output

    browser_choices = ["none"] + BROWSERS
    browser_default = "none"
    if args.browser is not None:
        browser_default = args.browser
    browser = prompt_choice("Cookies from browser", browser_choices, browser_default)
    if browser == "none":
        args.browser = None
    else:
        args.browser = browser

    time_range = input("Time range START-END (empty for the whole video): ")
    time_range = time_range.strip()
    if time_range != "":
        args.time = time_range

    return args


def main() -> None:
    args = parse_arguments()
    if args.url is None:
        args = prompt_options(args)

    if len(args.kinds) == 0:
        print("Nothing chosen to download.")
        return

    audio_from_video = "video" in args.kinds and "audio" in args.kinds

    try:
        for kind in args.kinds:
            if kind == "audio" and audio_from_video:
                continue
            downloaded_path = download(args.url, args.output, kind, args.quality, args.browser, args.time, args.lang)
            if kind == "video" and audio_from_video:
                extract_audio(downloaded_path, args.output)
    except yt_dlp.utils.DownloadError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error: ffmpeg exited with code {e.returncode}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

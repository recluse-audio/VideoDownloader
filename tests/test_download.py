import argparse
import os
import sys
import tempfile
import unittest
from unittest import mock

import download


def make_fake_youtube_dl(info: dict) -> mock.MagicMock:
    fake_ydl = mock.MagicMock()
    fake_ydl.extract_info.return_value = info
    fake_class = mock.MagicMock()
    fake_class.return_value.__enter__.return_value = fake_ydl
    return fake_class


def run_download(kind: str, quality: str, lang: str, info: dict) -> tuple[str | None, dict]:
    fake_class = make_fake_youtube_dl(info)
    with mock.patch.object(download.yt_dlp, "YoutubeDL", fake_class):
        result = download.download("https://example.com/v", "OUT", kind, quality, None, None, lang)
    ydl_opts = fake_class.call_args.args[0]
    return result, ydl_opts


class TestDownload(unittest.TestCase):
    def test_audio_kind_adds_mp3_postprocessor(self) -> None:
        result, ydl_opts = run_download("audio", "best", "en", {})
        self.assertEqual(ydl_opts["format"], "bestaudio/best")
        self.assertEqual(ydl_opts["outtmpl"], "OUT/AUDIO/%(title)s.%(ext)s")
        postprocessor = ydl_opts["postprocessors"][0]
        self.assertEqual(postprocessor["key"], "FFmpegExtractAudio")
        self.assertEqual(postprocessor["preferredcodec"], "mp3")

    def test_subtitle_kind_uses_lang(self) -> None:
        result, ydl_opts = run_download("subtitle", "best", "fr", {})
        self.assertEqual(ydl_opts["subtitleslangs"], ["fr"])
        self.assertTrue(ydl_opts["skip_download"])
        self.assertEqual(ydl_opts["outtmpl"], "OUT/SUBTITLE/%(title)s.%(ext)s")

    def test_video_quality_selects_height(self) -> None:
        result, ydl_opts = run_download("video", "720p", "en", {})
        self.assertEqual(ydl_opts["format"], "bestvideo[height<=720]+bestaudio/best[height<=720]")
        self.assertEqual(ydl_opts["outtmpl"], "OUT/VIDEO/%(title)s.%(ext)s")
        self.assertNotIn("postprocessors", ydl_opts)

    def test_returns_requested_download_filepath(self) -> None:
        info = {"requested_downloads": [{"filepath": "OUT/VIDEO/clip.mp4"}]}
        result, ydl_opts = run_download("video", "best", "en", info)
        self.assertEqual(result, "OUT/VIDEO/clip.mp4")


def make_args(url: str | None, kinds: list[str]) -> argparse.Namespace:
    args = argparse.Namespace()
    args.url = url
    args.output = "."
    args.kinds = kinds
    args.quality = "best"
    args.browser = None
    args.time = None
    args.lang = "en"
    return args


def parse_command_line(argv: list[str]) -> argparse.Namespace:
    with mock.patch.object(sys, "argv", argv):
        args = download.parse_arguments()
    return args


class TestParseArguments(unittest.TestCase):
    def test_flags_set_kinds_quality_lang(self) -> None:
        argv = ["download.py", "URL", "--kind", "audio", "--quality", "720p", "--lang", "de"]
        args = parse_command_line(argv)
        self.assertEqual(args.url, "URL")
        self.assertEqual(args.kinds, ["audio"])
        self.assertEqual(args.quality, "720p")
        self.assertEqual(args.lang, "de")

    def test_kind_takes_several_values(self) -> None:
        argv = ["download.py", "URL", "--kind", "video", "subtitle"]
        args = parse_command_line(argv)
        self.assertEqual(args.kinds, ["video", "subtitle"])

    def test_missing_url_is_none(self) -> None:
        args = parse_command_line(["download.py"])
        self.assertIsNone(args.url)
        self.assertEqual(args.kinds, ["video"])
        self.assertEqual(args.quality, "best")
        self.assertEqual(args.lang, "en")


class TestPromptChoice(unittest.TestCase):
    def test_empty_answer_returns_default(self) -> None:
        fake_input = mock.MagicMock(side_effect=[""])
        with mock.patch("builtins.input", fake_input):
            answer = download.prompt_choice("Quality", download.QUALITIES, "720p")
        self.assertEqual(answer, "720p")

    def test_invalid_answer_asks_again(self) -> None:
        fake_input = mock.MagicMock(side_effect=["4k", "480p"])
        with mock.patch("builtins.input", fake_input), mock.patch("builtins.print"):
            answer = download.prompt_choice("Quality", download.QUALITIES, "best")
        self.assertEqual(answer, "480p")
        self.assertEqual(fake_input.call_count, 2)


class TestPromptYesNo(unittest.TestCase):
    def test_empty_answer_returns_default(self) -> None:
        fake_input = mock.MagicMock(side_effect=[""])
        with mock.patch("builtins.input", fake_input):
            answer = download.prompt_yes_no("Download Video?", False)
        self.assertIs(answer, False)

    def test_invalid_answer_asks_again(self) -> None:
        fake_input = mock.MagicMock(side_effect=["maybe", "Y"])
        with mock.patch("builtins.input", fake_input), mock.patch("builtins.print"):
            answer = download.prompt_yes_no("Download Video?", False)
        self.assertTrue(answer)
        self.assertEqual(fake_input.call_count, 2)


class TestPromptOptions(unittest.TestCase):
    def test_answers_fill_every_option(self) -> None:
        answers = ["URL", "y", "y", "y", "720p", "fr", "OUT", "firefox", "00:01-00:02"]
        fake_input = mock.MagicMock(side_effect=answers)
        start_args = make_args(None, ["video"])
        with mock.patch("builtins.input", fake_input):
            args = download.prompt_options(start_args)
        self.assertEqual(args.url, "URL")
        self.assertEqual(args.kinds, ["video", "audio", "subtitle"])
        self.assertEqual(args.quality, "720p")
        self.assertEqual(args.lang, "fr")
        self.assertEqual(args.output, "OUT")
        self.assertEqual(args.browser, "firefox")
        self.assertEqual(args.time, "00:01-00:02")

    def test_three_no_answers_skip_other_prompts(self) -> None:
        fake_input = mock.MagicMock(side_effect=["URL", "n", "n", "n"])
        start_args = make_args(None, ["video"])
        with mock.patch("builtins.input", fake_input):
            args = download.prompt_options(start_args)
        self.assertEqual(args.kinds, [])
        self.assertEqual(fake_input.call_count, 4)


class TestMain(unittest.TestCase):
    def run_main(self, parsed_args: argparse.Namespace, prompted_args: argparse.Namespace) -> dict:
        fakes = {
            "parse_arguments": mock.MagicMock(return_value=parsed_args),
            "prompt_options": mock.MagicMock(return_value=prompted_args),
            "download": mock.MagicMock(return_value="OUT/VIDEO/clip.mp4"),
            "extract_audio": mock.MagicMock(),
        }
        fake_print = mock.MagicMock()
        with mock.patch.multiple(download, **fakes), mock.patch("builtins.print", fake_print):
            download.main()
        fakes["print"] = fake_print
        return fakes

    def test_missing_url_calls_prompt_options(self) -> None:
        parsed_args = make_args(None, ["video"])
        prompted_args = make_args("URL", ["video"])
        fakes = self.run_main(parsed_args, prompted_args)
        fakes["prompt_options"].assert_called_once_with(parsed_args)
        fakes["download"].assert_called_once_with("URL", ".", "video", "best", None, None, "en")

    def test_each_kind_calls_download(self) -> None:
        parsed_args = make_args("URL", ["video", "subtitle"])
        fakes = self.run_main(parsed_args, parsed_args)
        fakes["prompt_options"].assert_not_called()
        download_calls = fakes["download"].call_args_list
        self.assertEqual(download_calls[0].args[2], "video")
        self.assertEqual(download_calls[1].args[2], "subtitle")
        self.assertEqual(fakes["download"].call_count, 2)

    def test_no_kinds_skips_download(self) -> None:
        parsed_args = make_args("URL", [])
        fakes = self.run_main(parsed_args, parsed_args)
        fakes["download"].assert_not_called()
        fakes["print"].assert_called_once_with("Nothing chosen to download.")

    def test_video_and_audio_download_once_then_extract(self) -> None:
        parsed_args = make_args("URL", ["video", "audio"])
        fakes = self.run_main(parsed_args, parsed_args)
        fakes["download"].assert_called_once_with("URL", ".", "video", "best", None, None, "en")
        fakes["extract_audio"].assert_called_once_with("OUT/VIDEO/clip.mp4", ".")


class TestExtractAudio(unittest.TestCase):
    def test_writes_mp3_in_audio_dir(self) -> None:
        fake_run = mock.MagicMock()
        with tempfile.TemporaryDirectory() as output_dir:
            with mock.patch.object(download.subprocess, "run", fake_run):
                download.extract_audio("OUT/VIDEO/clip.mp4", output_dir)
            audio_dir = os.path.join(output_dir, "AUDIO")
            audio_dir_exists = os.path.isdir(audio_dir)
            expected_path = os.path.join(audio_dir, "clip.mp3")
        self.assertTrue(audio_dir_exists)
        command = fake_run.call_args.args[0]
        self.assertEqual(command[0], "ffmpeg")
        self.assertIn("-vn", command)
        self.assertEqual(command[-1], expected_path)
        self.assertTrue(fake_run.call_args.kwargs["check"])


if __name__ == "__main__":
    unittest.main()

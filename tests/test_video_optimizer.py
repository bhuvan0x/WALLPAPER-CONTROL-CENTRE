import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from video_optimizer import OptimizerError, optimize_video


class VideoOptimizerValidationTests(unittest.TestCase):
    def test_rejects_non_mp4(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "wallpaper.mkv"
            source.write_bytes(b"video")
            with self.assertRaisesRegex(OptimizerError, "MP4"):
                optimize_video(source, directory)

    def test_rejects_missing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(OptimizerError, "MP4"):
                optimize_video(Path(directory) / "missing.mp4", directory)

    def test_rejects_empty_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "empty.mp4"
            source.touch()
            with self.assertRaisesRegex(OptimizerError, "empty"):
                optimize_video(source, directory)

    def test_missing_ffmpeg_keeps_original_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "original.mp4"
            source.write_bytes(b"original video bytes")
            with patch("video_optimizer.shutil.which", return_value=None):
                with self.assertRaisesRegex(OptimizerError, "ffmpeg"):
                    optimize_video(source, directory)
            self.assertEqual(source.read_bytes(), b"original video bytes")
            self.assertEqual(sorted(p.name for p in Path(directory).iterdir()), ["original.mp4"])


if __name__ == "__main__":
    unittest.main()

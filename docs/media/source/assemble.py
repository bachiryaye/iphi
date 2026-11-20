"""Assemble real browser segments with the separately rendered chapter frames."""

import argparse
import json
import logging
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory


def run_ffmpeg(arguments: list[str]) -> None:
    executable = shutil.which("ffmpeg")
    if executable is None:
        raise FileNotFoundError("Install FFmpeg before assembling the recording")
    # Local media paths are separate arguments; no shell is invoked.
    subprocess.run([executable, *arguments], check=True)  # noqa: S603


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--frames-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    edit = json.loads(Path(__file__).with_name("edit.json").read_text())
    with TemporaryDirectory(prefix="iphi-video-edit-") as directory:
        work = Path(directory)
        parts = []
        for chapter, entry in enumerate(edit, start=1):
            for cut, (start, duration) in enumerate(entry["cuts"]):
                output = work / f"part-{chapter:02}-{cut}.mp4"
                run_ffmpeg(
                    [
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-threads",
                        "1",
                        "-ss",
                        str(start),
                        "-t",
                        str(duration),
                        "-i",
                        str(args.raw_dir / entry["file"]),
                        "-loop",
                        "1",
                        "-i",
                        str(args.frames_dir / f"chapter-{chapter:02}.png"),
                        "-filter_complex_threads",
                        "1",
                        "-filter_complex",
                        "[0:v]setpts=PTS-STARTPTS[screen];[1:v][screen]overlay=24:144:shortest=1,format=yuv420p",
                        "-an",
                        "-c:v",
                        "libx264",
                        "-preset",
                        "veryfast",
                        "-crf",
                        "22",
                        "-r",
                        "20",
                        "-threads",
                        "2",
                        "-t",
                        str(duration),
                        "-map_metadata",
                        "-1",
                        "-y",
                        str(output),
                    ],
                )
                parts.append(output)
                logging.info("Chapter %s, segment %s encoded.", chapter, cut + 1)
        playlist = work / "concat.txt"
        playlist.write_text("".join(f"file '{part.name}'\n" for part in parts))
        run_ffmpeg(
            [
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "1",
                "-i",
                str(playlist),
                "-c",
                "copy",
                "-map_metadata",
                "-1",
                "-movflags",
                "+faststart",
                "-y",
                str(args.output),
            ],
        )


if __name__ == "__main__":
    main()

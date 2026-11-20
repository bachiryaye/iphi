# Demonstration media and recording recipe

- [Three-minute French MP4](iphi-demo-fr.mp4): H.264, 1920 × 1080, 20 fps, no audio.
- [Poster](iphi-demo-fr-poster.jpg), extracted from the final movie.
- [WebVTT text descriptions](iphi-demo-fr.vtt).
- [Transcript, chapter times, provenance and editing limits](../video-demo.md).

The UI footage was captured from the actual application at source `83b87b3`, on
19 November 2026, in a separate local Compose project with a fresh database and
`IPHI_LLM_PROVIDER=none`. The simulation uses seed 42. Native UI actions start and
stop `collector_down`, request the deterministic diagnosis and export CSV. Recovery
uses the platform clock at ×30. Read-only API checks confirmed one active incident,
then resolution and a healthy platform; the downloaded CSV contained 161 rows.

The published file is edited footage: pauses, loading and waiting periods are cut.
The chapter panels are presentation graphics, rendered with Remotion 4.0.539; they
do not replace the UI or calculate health states. Stored evidence stays in its
original language. No video, voice or model service is required. The application
has no new package or runtime dependency for these media files.

## Capture the interface

1. Start a separate disposable IPHI environment following [demo.md](../demo.md),
   with the AI provider disabled. Keep the normal development or review stack intact.
2. Authenticate before recording, using a private browser storage state as described
   in [access.md](../access.md). Keep state files and raw output outside Git with
   directory mode 700 and state-file mode 600. Never record a login or terminal
   containing local environment values, cookies or CSRF proofs.
3. Open a light-theme browser viewport at 1440 × 900, choose French, and wait for
   seven healthy components and an active monitor. Do not accept a stale/loading
   screen as a baseline.
4. Use Playwright CLI `video-start <file> --size=1440x900 --fps=20 --cursor` and
   `video-stop` around each of the eight stages in [the transcript](../video-demo.md).
   Take a fresh snapshot before each referenced click. Save the clips under the
   filenames in [edit.json](source/edit.json). Do not mock API replies or edit
   displayed measurements. Close the browser after recording.
5. Review the raw files. Adjust the start/duration pairs in `edit.json` for the new
   take: timestamps and browser-action durations vary. Keep the actual action order,
   label accelerated platform time, and disclose cuts. The supplied manifest is for
   the published take, not a timing assertion about another machine.

## Render the panels and assemble

Optional authoring prerequisites: Python 3.10+, Node.js 24+, FFmpeg/FFprobe, Chromium,
and an existing Remotion 4.0.539 workspace containing React, `@remotion/bundler` and
`@remotion/renderer`. IBM Plex Sans is used when installed, with DejaVu Sans as a
fallback. These tools are separate from the IPHI application environment.

Copy [the source directory](source/) to a temporary workspace and make the existing
Remotion workspace's `node_modules` available there. This avoids changing another
project or installing video tooling into IPHI. From that temporary directory:

```sh
IPHI_VIDEO_CHROME=/absolute/path/to/chromium node render-frames.mjs
python3 assemble.py --raw-dir /absolute/path/to/private-clips \
  --frames-dir ./frames --output ./iphi-demo-fr.mp4
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate \
  -of json ./iphi-demo-fr.mp4
ffmpeg -v error -i ./iphi-demo-fr.mp4 -f null -
```

The renderer explicitly selects
[Chrome for Testing mode](https://www.remotion.dev/docs/options/chrome-mode) for a
full Chromium binary. It reuses one browser for eight stills. FFmpeg places each
unaltered 1440 × 900 screen recording at `(24, 144)` in the 1920 × 1080 chapter frame,
encodes local segments without a shell, and joins them into a fast-start MP4.

Review frames across every chapter and cut, including the start, final frame,
critical/one-incident state, evidence, diagnosis, resolution and both guide languages.
Check for secrets and visible errors before copying only the final movie, poster,
text track and public sources into this directory. Raw clips, cookies, downloads,
browser profiles and intermediate frames stay private. The finished recording has
180 seconds of video and no audio track; text panels and the separate transcript
describe its actions without requiring sound.

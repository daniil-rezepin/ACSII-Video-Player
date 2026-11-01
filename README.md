# ASCII Video

Play local MP4 videos as ASCII characters in a terminal.

Features:
- Monochrome, 256-color, and 24-bit true-color output.
- Optional audio from the video's first audio track.
- Pause/resume, mute, color switching, and quit controls.
- Automatic resizing with character aspect-ratio correction.
- Timestamp-based playback and late-frame dropping.
- Custom characters, brightness adjustment, and inverted shading.

## Requirements

- Python 3.10 or newer.
- VS Code or another ANSI-compatible terminal.
- For sound: pygame-ce and the FFmpeg command-line application.

## Setup in VS Code

Open this folder, then open Terminal > New Terminal.

Create a virtual environment:

    python -m venv .venv

On Windows PowerShell:

    .\.venv\Scripts\Activate.ps1

On macOS/Linux:

    source .venv/bin/activate

If PowerShell prevents activation, use .\.venv\Scripts\python.exe
instead of python in the following commands.

Install video dependencies:

    python -m pip install -r requirements.txt

Or install video and audio dependencies:

    python -m pip install -r requirements-audio.txt

In VS Code, use "Python: Select Interpreter" and select .venv.
Install the recommended Python and Python Debugger extensions when prompted.

## Play

Put an MP4 in media/, then run:

    python player.py "media/video.mp4"

Color and sound:

    python player.py "media/video.mp4" --color truecolor --audio

Monochrome with a smaller output:

    python player.py "media/video.mp4" --color mono --width 100 --fps 20

Light terminal background:

    python player.py "media/video.mp4" --color mono --invert

Brighter image:

    python player.py "media/video.mp4" --gamma 0.7

Custom dark-to-light character ramp:

    python player.py "media/video.mp4" --chars " .oO#@"

Full options:

    python player.py --help

Alternatively, press F5 and choose a playback configuration.
Enter the video path without surrounding quotes when VS Code prompts you.

## Controls

| Key | Action |
| --- | --- |
| Space or P | Pause/resume video and audio |
| C | Cycle monochrome, 256 colors, and true color |
| M | Mute/unmute audio |
| Q or Ctrl+C | Quit |

Click inside the terminal before using playback controls.

## Optional audio

Install FFmpeg from https://ffmpeg.org/download.html and make sure the
ffmpeg executable is available on PATH. Verify with:

    ffmpeg -version

Then install requirements-audio.txt and use --audio.

Audio is extracted before playback into a temporary stereo WAV, streamed
through pygame, and deleted on exit. Extraction can take time and uses about
10 MB of temporary disk space per minute of video.

Missing audio dependencies, a missing audio track, or an unavailable audio
device cause playback to continue silently with a warning.

Audio and video start together and pause together. Synchronization is
approximate: audio-device latency and unusual video timestamps can cause
an offset. When timestamps are unavailable, playback falls back to the
reported frame rate, which can be inaccurate for variable-frame-rate video.

## How it works

OpenCV decodes video frames into BGR pixel arrays. Each frame is resized to
fit the terminal. Its grayscale brightness selects a character from a ramp
ordered from sparse to dense. Color modes attach ANSI foreground colors
derived from the original pixels.

A monotonic clock schedules frames. If decoding or terminal output falls
behind, old frames are skipped to keep playback near the video timeline.
--fps limits terminal refreshes without slowing the soundtrack.

Only a few video frames are held in memory. This is a live terminal player;
it does not export a new MP4.

## Troubleshooting

- Use the integrated Terminal, not VS Code's Debug Console or Output panel.
- Maximize the terminal or reduce its font size for more detail.
- If output is slow, use --width 80 --fps 20 --color mono.
- If colors look wrong, try --color 256 or --color mono.
- Adjust --cell-ratio if the image looks stretched; 0.5 suits many fonts.
- A dark background works best with the default ramp.
- Codec support depends on the OpenCV build.
- Windows, macOS, and Linux code paths are included; they have not been
  execution-tested in the authoring environment.

## Tests

    python -m unittest discover -s tests -v

## Reference documentation

- OpenCV: https://docs.opencv.org/4.x/dd/d43/tutorial_py_video_display.html
- pygame audio: https://pyga.me/docs/ref/music.html
- FFmpeg: https://ffmpeg.org/ffmpeg.html
- VS Code debugging: https://code.visualstudio.com/docs/python/debugging

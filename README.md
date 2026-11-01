# ASCII Video Player

Play local MP4 videos as ASCII characters in your terminal, in black and white
or full color, with optional sound.

## Quick start

Put an MP4 in the `media/` folder and run:

```bash
python player.py "media/video.mp4"
```

First time? Install the dependencies first (see [Setup in VS Code](#setup-in-vs-code)):

```bash
python -m pip install -r requirements.txt
```

### Common commands

| Command | What it does |
| --- | --- |
| `python player.py "media/video.mp4"` | Play with automatic color detection |
| `python player.py "media/video.mp4" --color truecolor --audio` | Full color with sound |
| `python player.py "media/video.mp4" --audio --keyboard` | Keyboard backlight follows the video's colors ([ASUS TUF laptops](#keyboard-lighting)) |
| `python player.py "media/video.mp4" --color mono --width 100 --fps 20` | Black and white, smaller and lighter on slow terminals |
| `python player.py "media/video.mp4" --invert` | For terminals with a light background |
| `python player.py "media/video.mp4" --gamma 0.7` | Brighter image |
| `python player.py "media/video.mp4" --chars " .oO#@"` | Use your own characters, dark to light |
| `python player.py --help` | List every option |

In VS Code you can also press **F5** and choose a playback configuration.

### Controls

| Key | Action |
| --- | --- |
| Space or P | Pause/resume video and audio |
| C | Cycle monochrome, 256 colors, and true color |
| M | Mute/unmute audio |
| Q or Ctrl+C | Quit |

Click inside the terminal before using the controls.

### All options

| Option | Default | Description |
| --- | --- | --- |
| `video` | (required) | Path to the video file |
| `--color` | `auto` | `auto`, `mono`, `256`, or `truecolor` |
| `--audio` | off | Play the video's sound (needs FFmpeg and pygame-ce) |
| `--volume` | `0.7` | Audio volume from 0 to 1 |
| `--keyboard` | off | Match the keyboard backlight to the video (ASUS TUF laptops on Windows) |
| `--width` | `0` | Maximum width in characters; `0` fits the terminal |
| `--fps` | `30` | Maximum screen refreshes per second; does not change playback speed |
| `--cell-ratio` | `0.5` | Width-to-height ratio of one terminal character; adjust if the image looks stretched |
| `--chars` | `" .:-=+*#%@"` | Characters used for shading, from dark to light |
| `--invert` | off | Reverse the shading for light backgrounds |
| `--gamma` | `1` | Below 1 brightens, above 1 darkens |

## Features

- Monochrome, 256-color, and 24-bit true-color output.
- Optional audio from the video's first audio track.
- Optional keyboard backlight that glows in the video's colors, like TV
  ambient lighting (ASUS TUF laptops on Windows).
- Pause/resume, mute, color switching, and quit controls.
- Automatic resizing with character aspect-ratio correction.
- Timestamp-based playback and late-frame dropping.
- Custom characters, brightness adjustment, and inverted shading.

## Requirements

- Python 3.10 or newer.
- VS Code or another ANSI-compatible terminal.
- For sound: pygame-ce and the FFmpeg command-line application.

## Setup in VS Code

Open this folder, then open **Terminal > New Terminal**.

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Or on macOS/Linux:

```bash
source .venv/bin/activate
```

If PowerShell prevents activation, use `.\.venv\Scripts\python.exe`
instead of `python` in the following commands.

Install video dependencies:

```bash
python -m pip install -r requirements.txt
```

Or install video and audio dependencies:

```bash
python -m pip install -r requirements-audio.txt
```

In VS Code, use **Python: Select Interpreter** and select `.venv`.
Install the recommended Python and Python Debugger extensions when prompted.

When you press F5, enter the video path without surrounding quotes when
VS Code prompts you.

## Optional audio

Install FFmpeg from https://ffmpeg.org/download.html and make sure the
`ffmpeg` executable is available on PATH. Verify with:

```bash
ffmpeg -version
```

Then install `requirements-audio.txt` and use `--audio`.

Audio is extracted before playback into a temporary stereo WAV, streamed
through pygame, and deleted on exit. Extraction can take time and uses about
10 MB of temporary disk space per minute of video.

Missing audio dependencies, a missing audio track, or an unavailable audio
device cause playback to continue silently with a warning.

Audio and video start together and pause together. Synchronization is
approximate: audio-device latency and unusual video timestamps can cause
an offset. When timestamps are unavailable, playback falls back to the
reported frame rate, which can be inaccurate for variable-frame-rate video.

## Keyboard lighting

With `--keyboard`, the keyboard backlight glows in the overall color of the
scene while the video plays, like the ambient lighting on some TVs. Dark
scenes dim it, and colors fade smoothly instead of flickering.

It works on ASUS TUF laptops running Windows with Armoury Crate or MyASUS
installed. It uses the ASUS ATKACPI driver that comes with them, so nothing
extra needs installing and admin rights aren't needed. The lighting interface
was checked on a TUF Gaming F15 (FX506HCB). These keyboards have one lighting
zone, so the whole keyboard shows one color.

- The status line shows `keys on` while the lighting is active.
- On other laptops, or if the driver can't be reached, the video plays
  normally with a warning.
- When playback ends, the keyboard is set to white. Re-apply your usual
  effect in Armoury Crate if it doesn't come back by itself.
- To make the effect softer, more vivid, or brighter, change the numbers at
  the top of `backlight.py` (`SMOOTHING`, `SATURATION_BOOST`,
  `BRIGHTNESS_BOOST`, `EXIT_COLOR`).

## Troubleshooting

- Use the integrated Terminal, not VS Code's Debug Console or Output panel.
- Maximize the terminal or reduce its font size for more detail.
- If output is slow, use `--width 80 --fps 20 --color mono`.
- If colors look wrong, try `--color 256` or `--color mono`.
- Adjust `--cell-ratio` if the image looks stretched; 0.5 suits many fonts.
- A dark background works best with the default characters.
- Codec support depends on the OpenCV build.
- Windows, macOS, and Linux code paths are included; they have not been
  execution-tested in the authoring environment.

## Tests

```bash
python -m unittest discover -s tests -v
```

---

The tests check the parts that don't need a real terminal, video file, or
keyboard:

| Test | What it checks |
| --- | --- |
| `test_black_and_white_mapping` | Black becomes the first character, white the last, and `--invert` swaps them |
| `test_truecolor_converts_bgr_to_rgb` | A red pixel (stored by OpenCV as BGR) produces a red escape code |
| `test_fit_respects_both_dimensions` | Landscape and portrait videos both fit inside an 80×24 terminal |
| `test_clock_excludes_pause` | Time spent paused is not counted (uses a fake clock) |
| `test_packet_layout` | The keyboard driver message is built byte for byte as the driver expects |
| `test_solid_frames` | Red, black, and white frames light the keyboard red, off, and white |
| `test_vivid_pixels_decide_the_hue` | A small red area on a grey frame still turns the keyboard red |
| `test_fades_between_colors_and_restores` | Colors fade instead of jumping, and the exit color is set at the end (uses a fake keyboard) |
| `test_limits_update_rate` | The keyboard isn't updated more than 60 times a second |
| `test_driver_errors_turn_lighting_off` | A keyboard error stops the lighting without stopping the video |
| `test_missing_driver_gives_warning` | Laptops without the driver get a warning instead of a crash |

### Project files

| File | Purpose |
| --- | --- |
| `player.py` | The player |
| `backlight.py` | Keyboard lighting for `--keyboard` |
| `tests/` | Unit tests |
| `requirements.txt` | Video dependencies: NumPy, OpenCV, colorama |
| `requirements-audio.txt` | The above plus pygame-ce for sound |
| `.vscode/launch.json` | The F5 playback configurations, including one with keyboard lighting |
| `.vscode/tasks.json` | A "Run tests" task |
| `.vscode/settings.json` | Uses `.venv`, enables the tests, and removes extra spacing between terminal lines |
| `media/` | Put your videos here (ignored by Git, except its README) |

## Reference documentation

- OpenCV: https://docs.opencv.org/4.x/dd/d43/tutorial_py_video_display.html
- pygame audio: https://pyga.me/docs/ref/music.html
- FFmpeg: https://ffmpeg.org/ffmpeg.html
- VS Code debugging: https://code.visualstudio.com/docs/python/debugging

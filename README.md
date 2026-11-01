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
| `--width` | `0` | Maximum width in characters; `0` fits the terminal |
| `--fps` | `30` | Maximum screen refreshes per second; does not change playback speed |
| `--cell-ratio` | `0.5` | Width-to-height ratio of one terminal character; adjust if the image looks stretched |
| `--chars` | `" .:-=+*#%@"` | Characters used for shading, from dark to light |
| `--invert` | off | Reverse the shading for light backgrounds |
| `--gamma` | `1` | Below 1 brightens, above 1 darkens |

## Features

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

## How the code works

Everything lives in one file, `player.py`. This section walks through it in
the order the program runs.

### The big picture

```
main()
 ├─ arguments()          read and check the command-line options, pick a color mode
 ├─ cv2.VideoCapture     open the video file
 ├─ Audio.prepare()      only with --audio: extract the sound with FFmpeg
 ├─ play()               the playback loop
 │   ├─ decode()         read frames one at a time, with their timestamps
 │   ├─ Clock            how far into the video should we be right now?
 │   ├─ fit_size()       how many columns and rows fit in the terminal?
 │   ├─ render()         turn one frame into lines of characters
 │   └─ Terminal         read key presses, draw the text
 └─ cleanup              close the audio, delete temp files, release the video
```

The core idea is simple: shrink each video frame until one pixel equals one
character, then pick a character based on how bright that pixel is. Dark
pixels become sparse characters like `.` and bright pixels become dense ones
like `#`. Color modes add an ANSI color code in front of each character.

### 1. Starting up: `main()` and `arguments()`

`arguments()` uses `argparse` to read the options and then checks them:

- `--width` must be 0 or more, and `--volume` must be between 0 and 1.
- `--fps`, `--cell-ratio`, and `--gamma` go through `positive()`, which
  rejects zero, negative numbers, and values like `inf` or `nan`.
- `--chars` needs at least two printable ASCII characters (codes 32 to 126),
  because anything else could break the terminal layout.
- The video path is expanded (`~` works) and turned into a full path, and the
  file must exist.

With `--color auto` (the default), the program guesses what the terminal
supports from environment variables:

| Check | Result |
| --- | --- |
| `NO_COLOR` is set | `mono` (respects the [NO_COLOR](https://no-color.org) convention) |
| `COLORTERM` is `truecolor`/`24bit`, or running in VS Code or Windows Terminal | `truecolor` |
| `TERM` contains `256color` | `256` |
| Anything else | `mono` |

`main()` then refuses to run if the output is not a real terminal (for
example VS Code's Debug Console, or output redirected to a file), opens the
video with OpenCV, prepares audio if asked, and calls `play()`. Its `finally`
block always closes the audio and releases the video, even after an error or
Ctrl+C.

Exit codes: `0` finished normally, `1` error (for example an unreadable
video), `2` not running in a terminal, `130` stopped with Ctrl+C.

### 2. Reading frames: `decode()`

`decode()` is a **generator**: each time the loop asks for the next frame,
it reads exactly one frame from OpenCV and hands it back together with its
timestamp in seconds. This is why only a couple of frames are ever in memory,
no matter how long the video is. `play()` only keeps two of them: `current`
(the one on screen) and `upcoming` (the next one).

Timestamps come from `CAP_PROP_POS_MSEC`, OpenCV's position in the video in
milliseconds. A few fixes are applied:

- The first frame's timestamp is subtracted from every frame, so playback
  always starts at 0 seconds.
- If a timestamp is missing, negative, or not later than the previous one
  (some files have broken timestamps), it is replaced with
  `previous + 1 / fps`, an estimate based on the video's frame rate.
- If the video doesn't report a usable frame rate, 30 FPS is assumed.

### 3. Fitting the picture: `fit_size()`

Terminal characters are roughly twice as tall as they are wide. If the
program used one character per pixel without correcting for that, every video
would look stretched vertically. The `--cell-ratio` (default 0.5) fixes this:

```
rows = columns × (video height ÷ video width) × cell_ratio
```

The function leaves one column free (writing into the last column can make
some terminals wrap to a new line) and two rows free (for the status line).
It starts with the full width, or the `--width` limit, and if the result is
too tall, it uses the full height instead and works out the width from that.

Example: a 1920×1080 video in a 120×30 terminal. Full width gives 119 columns
and 119 × (1080 ÷ 1920) × 0.5 ≈ 33 rows, but only 28 rows are available, so
the picture becomes 99×28 instead.

This runs again for every frame that gets drawn, which is why resizing the
terminal window resizes the video straight away.

### 4. Turning a frame into text: `render()`

This is the heart of the program. For one frame it:

1. **Shrinks the frame** to the target size with `cv2.resize` using
   `INTER_AREA`, which averages all the pixels that end up in each character
   cell. That gives a smoother result than just picking one pixel.
2. **Adjusts brightness** if `--gamma` isn't 1. Instead of doing the maths
   for every pixel, it builds a lookup table once (256 entries, one per
   possible brightness, using `(value / 255) ^ gamma × 255`) and lets
   `cv2.LUT` apply it to the whole image. Gamma below 1 lifts dark areas.
3. **Converts to grayscale** with `cv2.cvtColor`, giving each cell one
   brightness value from 0 (black) to 255 (white).
4. **Picks characters.** The brightness is scaled to a position in the
   character list:

   ```
   index = brightness × (number of characters − 1) ÷ 255   (rounded down)
   ```

   With the default characters ` .:-=+*#%@`, brightness 0–28 gives a space,
   29–56 gives `.`, and so on up to `@`. `--invert` simply reverses the list.
   NumPy does this for the whole frame in one step (`palette[indices]`)
   instead of looping over every cell in Python, which keeps it fast.
5. **Adds color** (skipped in `mono` mode, which just joins each row into a
   string). OpenCV stores pixels as BGR (blue, green, red), so the channels
   are flipped to RGB first. Then each character gets an ANSI escape code:
   - **truecolor:** `ESC[38;2;R;G;Bm` sets the exact 24-bit color.
   - **256:** each channel is squeezed from 0–255 down to 0–5, and the color
     number is `16 + 36×R + 6×G + B`. That is the position in the standard
     6×6×6 color cube that 256-color terminals use (colors 16 to 231). For
     example, orange (255, 128, 0) becomes (5, 3, 0), which is color 214.

   An escape code is only written when the color changes from the previous
   character in the row. Areas of the same color (like a sky or a black
   background) then need far less text, so the terminal can draw faster.
   Every line ends with a reset code so colors never leak into the next line.

### 5. Talking to the terminal: `Terminal`

`Terminal` is used in a `with` block, so whatever happens, the terminal is
put back the way it was afterwards.

When playback starts (`__enter__`):

- `just_fix_windows_console()` from colorama turns on ANSI escape codes in
  older Windows consoles.
- On macOS and Linux, the keyboard is switched to **cbreak mode**, so key
  presses arrive immediately instead of waiting for Enter. The old settings
  are saved first.
- The program switches to the terminal's **alternate screen** (`ESC[?1049h`),
  the same trick `vim` and `less` use, and hides the cursor. When you quit,
  your previous terminal contents come back untouched.

When playback ends (`__exit__`), all of that is reversed.

**Drawing without flicker (`draw()`):** clearing the whole screen every frame
would cause visible flicker. Instead, the cursor is moved to the start of
each line (`ESC[row;1H`) and the new line is written over the old one.
`ESC[K` erases leftovers to the right of the line, and `ESC[J` erases
anything below the status line. The full screen is only cleared when the
terminal size changes. All of a frame's text is collected into one string
and written in a single call, so the terminal never shows a half-drawn frame.

**Reading keys without waiting (`key()`):** the loop can't stop and wait for
a key, or the video would freeze. So it only checks whether a key is waiting:

- **Windows:** `msvcrt.kbhit()` checks, `msvcrt.getwch()` reads. Special keys
  like the arrows send two codes (starting with `\x00` or `\xe0`), and both
  are thrown away.
- **macOS/Linux:** `select()` with a timeout of 0 checks whether input is
  ready, then one byte is read.

### 6. Keeping time: `Clock`

The video's timing is driven by a real clock, not by counting frames. `Clock`
uses `time.perf_counter()`, which always moves forward and isn't affected if
the computer's clock is changed.

- `elapsed()` is the time since playback started.
- Pausing remembers when the pause began, and `elapsed()` stays frozen.
- Resuming moves the start time forward by however long the pause lasted,
  so the paused time never counts.

The clock takes the "what time is it?" function as a parameter. Normally
that's `time.perf_counter`, but the tests pass in a fake one, so they can
check pausing without actually waiting.

### 7. The playback loop: `play()`

`play()` reads the first two frames, enters the terminal, starts the audio
and the clock at the same moment, and then repeats these steps until the
video ends or you quit:

1. **Check the keyboard.** Q quits (Ctrl+C also stops playback, through
   Python's `KeyboardInterrupt`). Space/P pauses the clock and
   the audio together. M mutes. C moves to the next color mode. Any key that
   changes something marks the screen as **dirty**, meaning it needs to be
   redrawn even while paused.
2. **Catch up with the clock.** While the upcoming frame's timestamp is not
   later than the elapsed time, it becomes the current frame and the next
   one is read. If the computer is too slow to draw every frame, the frames
   it missed are skipped, so the video stays in time with the real clock
   (and the audio) instead of slowly falling behind. It catches up at most 60
   frames per pass and then goes back to step 1, so the keys keep responding
   even when it's far behind.
3. **Detect the end.** When there are no more frames and the last frame has
   been shown for its full duration, playback stops.
4. **Decide whether to draw.** The frame is redrawn when the screen is dirty,
   when the terminal was resized, or when enough time has passed since the
   last draw according to `--fps`. This is why `--fps` only changes how often
   the screen updates, never the playback speed: the video's position always
   comes from the clock.
5. **Draw.** `fit_size()` → `render()` → `Terminal.draw()`, plus the status
   line showing play/pause, the time, the color mode, and the audio state.
6. **Sleep 5 ms**, so the loop doesn't run one CPU core at 100%.

### 8. Sound: `Audio`

pygame can't read the audio inside an MP4 directly, so the sound is
extracted first. `prepare()`:

1. Looks for `ffmpeg` on PATH and tries to import pygame. If either is
   missing, it returns a warning and the video plays without sound.
2. Creates a temporary folder and runs FFmpeg to convert the video's first
   audio track (`-map 0:a:0`) into a 16-bit stereo 44.1 kHz WAV file. The
   `aresample=async=1:first_pts=0` filter makes the audio start at 0 and fill
   small gaps, so it lines up with the video timestamps. The conversion is
   given up to 10 minutes.
3. Starts `pygame.mixer` and loads the WAV with `pygame.mixer.music`, which
   streams it from disk instead of loading it all into memory.

During playback, pausing calls `pause()`/`unpause()`, and muting sets the
volume to 0 and back. The audio is not re-synced after it starts: audio and
video run side by side from the same starting moment, which is why sync is
described as approximate. `close()` stops the mixer and deletes the temporary
folder. It runs from `main()`'s `finally` block, so the WAV file is always
removed, even after a crash.

### 9. Tests

`tests/test_player.py` checks the parts that don't need a real terminal or
video file:

| Test | What it checks |
| --- | --- |
| `test_black_and_white_mapping` | Black becomes the first character, white the last, and `--invert` swaps them |
| `test_truecolor_converts_bgr_to_rgb` | A red pixel (stored by OpenCV as BGR) produces a red escape code |
| `test_fit_respects_both_dimensions` | Landscape and portrait videos both fit inside an 80×24 terminal |
| `test_clock_excludes_pause` | Time spent paused is not counted (uses a fake clock) |

### Project files

| File | Purpose |
| --- | --- |
| `player.py` | The whole player |
| `tests/test_player.py` | Unit tests |
| `requirements.txt` | Video dependencies: NumPy, OpenCV, colorama |
| `requirements-audio.txt` | The above plus pygame-ce for sound |
| `.vscode/launch.json` | The F5 playback configurations |
| `.vscode/tasks.json` | A "Run tests" task |
| `.vscode/settings.json` | Uses `.venv`, enables the tests, and removes extra spacing between terminal lines |
| `media/` | Put your videos here (ignored by Git, except its README) |

## Reference documentation

- OpenCV: https://docs.opencv.org/4.x/dd/d43/tutorial_py_video_display.html
- pygame audio: https://pyga.me/docs/ref/music.html
- FFmpeg: https://ffmpeg.org/ffmpeg.html
- VS Code debugging: https://code.visualstudio.com/docs/python/debugging

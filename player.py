"""Play a local video as ASCII art inside an ANSI terminal."""
import argparse
import math
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import time

import cv2
import numpy as np
from colorama import just_fix_windows_console

RAMP = " .:-=+*#%@"
MODES = ("mono", "256", "truecolor")
RESET = "\033[0m"


def fit_size(width, height, columns, rows, limit=0, ratio=0.5):
    """Account for terminal characters being taller than they are wide."""
    available_width = max(1, columns - 1)
    available_height = max(1, rows - 2)
    w = min(limit or available_width, available_width)
    aspect = height / width * ratio
    h = max(1, round(w * aspect))
    if h > available_height:
        h = available_height
        w = max(1, min(w, int(h / aspect)))
    return w, h


def render(frame, size, mode, ramp=RAMP, invert=False, gamma=1.0):
    small = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
    if gamma != 1.0:
        lut = np.round((np.arange(256) / 255.0) ** gamma * 255)
        small = cv2.LUT(small, lut.astype(np.uint8))

    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    palette = np.array(list(ramp[::-1] if invert else ramp))
    indices = (gray.astype(float) * (len(palette) - 1) / 255).astype(int)
    characters = palette[indices]

    if mode == "mono":
        return ["".join(row) for row in characters]

    rgb = small[:, :, ::-1]
    if mode == "256":
        cube = np.rint(rgb.astype(float) / 255 * 5).astype(int)
        colors = 16 + 36 * cube[:, :, 0] + 6 * cube[:, :, 1] + cube[:, :, 2]

    lines = []
    for y, row in enumerate(characters):
        parts = []
        previous = None
        for x, character in enumerate(row):
            if mode == "truecolor":
                r, g, b = map(int, rgb[y, x])
                escape = f"\033[38;2;{r};{g};{b}m"
            else:
                escape = f"\033[38;5;{colors[y, x]}m"
            if escape != previous:
                parts.append(escape)
                previous = escape
            parts.append(character)
        lines.append("".join(parts) + RESET)
    return lines


class Clock:
    """A monotonic clock that excludes paused time."""

    def __init__(self, now=time.perf_counter):
        self.now = now
        self.started = now()
        self.paused_at = None

    @property
    def paused(self):
        return self.paused_at is not None

    def elapsed(self):
        end = self.paused_at if self.paused else self.now()
        return end - self.started

    def toggle(self):
        if self.paused:
            self.started += self.now() - self.paused_at
            self.paused_at = None
        else:
            self.paused_at = self.now()


class Audio:
    """Extract audio to a temporary WAV and stream it with pygame."""

    def __init__(self, volume):
        self.volume = volume
        self.muted = False
        self.mixer = None
        self.temp = None

    def prepare(self, path):
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return "Audio disabled: install FFmpeg and add it to PATH."

        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        try:
            import pygame
        except ImportError:
            return (
                "Audio disabled: run "
                "python -m pip install -r requirements-audio.txt"
            )

        try:
            self.temp = tempfile.TemporaryDirectory(prefix="ascii-video-")
            wav = Path(self.temp.name) / "audio.wav"
            result = subprocess.run(
                [
                    ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
                    "-y", "-i", str(path), "-map", "0:a:0", "-vn",
                    "-ac", "2", "-ar", "44100",
                    "-af", "aresample=async=1:first_pts=0",
                    "-c:a", "pcm_s16le", str(wav),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=600,
            )
            if result.returncode:
                self.close()
                return "Audio disabled: missing audio track or extraction failed."

            self.mixer = pygame.mixer
            self.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            self.mixer.music.load(str(wav))
            self.mixer.music.set_volume(self.volume)
            return None
        except (OSError, subprocess.TimeoutExpired, pygame.error) as exc:
            self.close()
            return f"Audio disabled: {exc}"

    def start(self):
        if self.mixer:
            self.mixer.music.play()

    def pause(self, paused):
        if self.mixer:
            if paused:
                self.mixer.music.pause()
            else:
                self.mixer.music.unpause()

    def mute(self):
        self.muted = not self.muted
        if self.mixer:
            self.mixer.music.set_volume(0 if self.muted else self.volume)

    def close(self):
        if self.mixer:
            if self.mixer.get_init():
                self.mixer.music.stop()
                self.mixer.music.unload()
                self.mixer.quit()
            self.mixer = None
        if self.temp:
            self.temp.cleanup()
            self.temp = None


class Terminal:
    def __init__(self):
        self.saved = None
        self.last_size = None

    def __enter__(self):
        just_fix_windows_console()
        try:
            if os.name != "nt" and sys.stdin.isatty():
                import termios
                import tty
                self.saved = termios.tcgetattr(sys.stdin.fileno())
                tty.setcbreak(sys.stdin.fileno())
            sys.stdout.write("\033[?1049h\033[?25l\033[0m\033[2J")
            sys.stdout.flush()
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *_):
        try:
            if self.saved is not None:
                import termios
                termios.tcsetattr(
                    sys.stdin.fileno(), termios.TCSADRAIN, self.saved
                )
        finally:
            sys.stdout.write("\033[0m\033[?25h\033[?1049l")
            sys.stdout.flush()

    def key(self):
        if not sys.stdin.isatty():
            return None
        if os.name == "nt":
            import msvcrt
            if msvcrt.kbhit():
                key = msvcrt.getwch()
                if key in ("\x00", "\xe0"):
                    msvcrt.getwch()
                    return None
                return key
        elif select.select([sys.stdin], [], [], 0)[0]:
            return os.read(sys.stdin.fileno(), 1).decode(
                "ascii", errors="ignore"
            )
        return None

    def draw(self, lines, status, size):
        columns, rows = size
        output = []
        if size != self.last_size:
            output.append("\033[2J")
            self.last_size = size
        for y, line in enumerate(lines, 1):
            output.append(f"\033[{y};1H{line}{RESET}\033[K")
        status_row = min(len(lines) + 1, rows)
        output.append(
            f"\033[{status_row};1H{RESET}"
            f"{status[:max(1, columns - 1)]}\033[K\033[J"
        )
        sys.stdout.write("".join(output))
        sys.stdout.flush()


def decode(capture, fps):
    """Prefer frame timestamps; fall back to FPS if unavailable."""
    previous = -1.0
    origin = None
    while True:
        ok, frame = capture.read()
        if not ok:
            return
        timestamp = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
        if origin is None:
            origin = timestamp if math.isfinite(timestamp) else 0.0
        timestamp -= origin
        if (
            not math.isfinite(timestamp)
            or timestamp < 0
            or timestamp <= previous
        ):
            timestamp = 0.0 if previous < 0 else previous + 1 / fps
        previous = timestamp
        yield timestamp, frame


def play(capture, audio, args):
    fps = capture.get(cv2.CAP_PROP_FPS)
    if not math.isfinite(fps) or fps <= 0:
        fps = 30.0
    frames = decode(capture, fps)
    current = next(frames, None)
    if current is None:
        raise ValueError("The video contains no readable frames.")
    upcoming = next(frames, None)
    color = args.color

    with Terminal() as terminal:
        audio.start()
        clock = Clock()
        next_draw = 0.0
        previous_size = None
        dirty = True

        while True:
            key = terminal.key()
            if key in ("q", "Q", "\x03"):
                return
            if key in (" ", "p", "P"):
                clock.toggle()
                audio.pause(clock.paused)
                dirty = True
            elif key in ("m", "M"):
                audio.mute()
                dirty = True
            elif key in ("c", "C"):
                color = MODES[(MODES.index(color) + 1) % len(MODES)]
                dirty = True

            elapsed = clock.elapsed()
            if not clock.paused:
                # Skip late frames without accumulating playback delay.
                # Bound each batch so keyboard input stays responsive.
                skipped = 0
                while (
                    upcoming is not None
                    and upcoming[0] <= elapsed
                    and skipped < 60
                ):
                    current = upcoming
                    upcoming = next(frames, None)
                    skipped += 1
                if upcoming is not None and upcoming[0] <= elapsed:
                    continue
                if upcoming is None and elapsed >= current[0] + 1 / fps:
                    return

            size = shutil.get_terminal_size((100, 30))
            dirty = dirty or size != previous_size
            if dirty or (
                not clock.paused and time.perf_counter() >= next_draw
            ):
                height, width = current[1].shape[:2]
                dimensions = fit_size(
                    width, height, *size, args.width, args.cell_ratio
                )
                lines = render(
                    current[1], dimensions, color,
                    args.chars, args.invert, args.gamma
                )
                state = "PAUSED" if clock.paused else "PLAY"
                sound = (
                    "off" if audio.mixer is None
                    else "muted" if audio.muted else "on"
                )
                status = (
                    f"{state} {elapsed:.1f}s | {color} | audio {sound}"
                    " | Space pause | C color | M mute | Q quit"
                )
                terminal.draw(lines, status, size)
                previous_size = size
                dirty = False
                next_draw = time.perf_counter() + 1 / args.fps
            time.sleep(0.005)


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Must be a positive finite number.")
    return number


def arguments():
    parser = argparse.ArgumentParser(
        description="Play MP4 video as colored ASCII in your terminal."
    )
    parser.add_argument("video", type=Path)
    parser.add_argument(
        "--color", choices=("auto",) + MODES, default="auto"
    )
    parser.add_argument("--audio", action="store_true", help="Enable sound")
    parser.add_argument("--volume", type=float, default=0.7)
    parser.add_argument(
        "--width", type=int, default=0,
        help="Maximum columns; 0 automatically fits the terminal"
    )
    parser.add_argument(
        "--fps", type=positive, default=30,
        help="Maximum display FPS; does not change playback speed"
    )
    parser.add_argument("--cell-ratio", type=positive, default=0.5)
    parser.add_argument("--chars", default=RAMP)
    parser.add_argument("--invert", action="store_true")
    parser.add_argument(
        "--gamma", type=positive, default=1,
        help="Below 1 brightens; above 1 darkens"
    )
    args = parser.parse_args()
    if args.width < 0:
        parser.error("--width must be zero or positive")
    if not math.isfinite(args.volume) or not 0 <= args.volume <= 1:
        parser.error("--volume must be between 0 and 1")
    if len(args.chars) < 2 or any(
        not 32 <= ord(c) <= 126 for c in args.chars
    ):
        parser.error("--chars requires at least two printable ASCII characters")
    args.video = args.video.expanduser().resolve()
    if not args.video.is_file():
        parser.error(f"Video file not found: {args.video}")

    if args.color == "auto":
        if "NO_COLOR" in os.environ:
            args.color = "mono"
        elif (
            os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit")
            or os.environ.get("TERM_PROGRAM") == "vscode"
            or "WT_SESSION" in os.environ
        ):
            args.color = "truecolor"
        elif "256color" in os.environ.get("TERM", ""):
            args.color = "256"
        else:
            args.color = "mono"
    return args


def main():
    args = arguments()
    if not sys.stdout.isatty():
        print(
            "Run in a terminal, not the Debug Console or redirected output.",
            file=sys.stderr
        )
        return 2

    capture = None
    audio = Audio(args.volume)
    try:
        capture = cv2.VideoCapture(str(args.video))
        if not capture.isOpened():
            raise ValueError("Cannot open video. Check the file and its codec.")
        if args.audio:
            print("Preparing audio...", file=sys.stderr)
            warning = audio.prepare(args.video)
            if warning:
                print(warning, file=sys.stderr)
        play(capture, audio, args)
        return 0
    except KeyboardInterrupt:
        return 130
    except (ValueError, OSError, RuntimeError, cv2.error) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        audio.close()
        if capture is not None:
            capture.release()


if __name__ == "__main__":
    raise SystemExit(main())

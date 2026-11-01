"""Match an ASUS TUF laptop's keyboard backlight to the video.

Works like the ambient lighting on some TVs: while the video plays, the
keyboard glows in the overall color of the current frame.

It talks to the keyboard through the ASUS ATKACPI driver that Armoury Crate
and MyASUS install on Windows (the same interface OpenRGB uses). TUF
keyboards have a single lighting zone, so the whole keyboard shows one color.
"""
import colorsys
import ctypes
import math
import struct
import sys

import cv2
import numpy as np

# Tuning: change these to taste.
SMOOTHING = 0.15              # seconds to move about 2/3 of the way to a new color
SATURATION_BOOST = 1.3        # above 1 makes colors more vivid
BRIGHTNESS_BOOST = 1.5        # keyboard brightness = frame brightness x this (max 1)
MAX_UPDATES = 60              # keyboard color changes per second
EXIT_COLOR = (255, 255, 255)  # color left on the keyboard when playback ends

# ASUS ATKACPI driver interface for TUF keyboard lighting.
ATK_DEVICE = r"\\.\ATKACPI"
IOCTL_ATK = 0x0022240C
METHOD_DEVS = 0x53564544      # "DEVS": set a device value
TUF_RGB_DEVICE = 0x00100056   # TUF keyboard RGB mode/color
CMD_SET = 0xB3                # set color (same value OpenRGB sends)
MODE_STATIC = 0
SPEED_MEDIUM = 0xEB


def tuf_packet(r, g, b):
    """Build the driver input: [method][argument size][device][high][low]."""
    high = CMD_SET | (MODE_STATIC << 8) | (r << 16) | (g << 24)
    low = b | (SPEED_MEDIUM << 8)
    arguments = struct.pack("<III", TUF_RGB_DEVICE, high, low)
    return struct.pack("<II", METHOD_DEVS, len(arguments)) + arguments


class AtkDriver:
    """Send one color at a time to the keyboard through ATKACPI."""

    def __init__(self):
        if sys.platform != "win32":
            raise OSError("only supported on ASUS laptops running Windows")
        from ctypes import wintypes

        self.wintypes = wintypes
        k = self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        ]
        k.CreateFileW.restype = wintypes.HANDLE
        k.DeviceIoControl.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
            wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        k.DeviceIoControl.restype = wintypes.BOOL
        k.CloseHandle.argtypes = [wintypes.HANDLE]

        # Read/write access, shared with other programs, open existing device.
        handle = k.CreateFileW(ATK_DEVICE, 0xC0000000, 3, None, 3, 0, None)
        if handle in (None, ctypes.c_void_p(-1).value):
            raise OSError(
                "cannot open the ASUS ATKACPI driver "
                f"(Windows error {ctypes.get_last_error()})"
            )
        self.handle = handle

    def set_color(self, r, g, b):
        packet = tuf_packet(r, g, b)
        inbuf = ctypes.create_string_buffer(packet, len(packet))
        outbuf = ctypes.create_string_buffer(0x400)
        returned = self.wintypes.DWORD(0)
        ok = self.kernel32.DeviceIoControl(
            self.handle, IOCTL_ATK, inbuf, len(packet),
            outbuf, len(outbuf), ctypes.byref(returned), None,
        )
        if not ok:
            raise OSError(f"Windows error {ctypes.get_last_error()}")
        reply = struct.unpack_from("<I", outbuf.raw)[0]
        if reply != 1:
            raise OSError(f"driver replied {reply:#x}")

    def close(self):
        self.kernel32.CloseHandle(self.handle)


def frame_color(frame):
    """Return one RGB color (floats from 0 to 1) that represents a BGR frame.

    Vivid, bright pixels decide the hue, so a red car on a grey street turns
    the keyboard red rather than a muddy brown. The brightness follows the
    whole frame, so dark scenes dim the keyboard.
    """
    small = cv2.resize(frame, (32, 18), interpolation=cv2.INTER_AREA)
    rgb = small[:, :, ::-1].reshape(-1, 3).astype(float) / 255
    high = rgb.max(axis=1)
    low = rgb.min(axis=1)
    saturation = (high - low) / np.maximum(high, 1e-6)
    weight = 0.1 + saturation * high  # the 0.1 keeps grey scenes grey
    mixed = (rgb * weight[:, None]).sum(axis=0) / weight.sum()

    hue, sat, _ = colorsys.rgb_to_hsv(*mixed)
    sat = min(1.0, sat * SATURATION_BOOST)
    value = min(1.0, high.mean() * BRIGHTNESS_BOOST)
    return np.array(colorsys.hsv_to_rgb(hue, sat, value))


class KeyboardLight:
    """Fade the keyboard toward each new frame's color."""

    def __init__(self, driver_factory=AtkDriver):
        self.driver_factory = driver_factory
        self.driver = None
        self.target = None
        self.color = None
        self.sent = None
        self.last_update = None
        self.next_send = 0.0

    @property
    def active(self):
        return self.driver is not None

    def open(self):
        """Connect to the keyboard. Returns a warning if that isn't possible."""
        try:
            self.driver = self.driver_factory()
        except OSError as exc:
            return f"Keyboard lighting disabled: {exc}"
        return None

    def show(self, frame):
        self.target = frame_color(frame)

    def update(self, now):
        """Move the color toward the target and send it, at most MAX_UPDATES/s."""
        if not self.active or self.target is None:
            return
        if self.color is None:
            self.color = self.target.copy()
        elif SMOOTHING > 0:
            step = 1 - math.exp(-(now - self.last_update) / SMOOTHING)
            self.color += (self.target - self.color) * step
        else:
            self.color = self.target.copy()
        self.last_update = now

        if now < self.next_send:
            return
        rgb = tuple(int(round(c * 255)) for c in self.color)
        if rgb == self.sent:
            return
        try:
            self.driver.set_color(*rgb)
        except OSError:
            self.close(restore=False)  # keep playing without lighting
            return
        self.sent = rgb
        self.next_send = now + 1 / MAX_UPDATES

    def close(self, restore=True):
        if not self.driver:
            return
        try:
            if restore:
                self.driver.set_color(*EXIT_COLOR)
        except OSError:
            pass
        finally:
            self.driver.close()
            self.driver = None

"""AniMe Vision HID protocol for ROG Strix SCAR (G835 family, 810-LED STRIX profile).

Protocol extracted from g-helper's AnimeMatrixDevice.cs (STRIX profile:
LedCount=810, UpdatePageLength=490, 34 cols x 68 rows, FullRows=29).

All packets are Feature reports of exactly 640 bytes:
  [0x5E][639 payload bytes, zero-padded]

Init sequence (run once per daemon start):
  1. WakeUp magic ("ASUS Tech.Inc.")
  2. SetDisplayState(false)  x2
  3. SetDisplayState(true)
  4. SetBrightness(mode)
  5. SetBuiltInAnimation(false)
Then for each frame:
  6. Page 0: 490 pixels at start=1
  7. Page 1: 320 pixels at start=491
  8. Latch: 0xC0 0x03
"""

from dataclasses import dataclass

VENDOR_ID = 0x0B05
PRODUCT_ID = 0x193B
# The device has two HID collections; the AniMe one is usage_page=0xFF31, usage=0x80.
# (The other, 0xFF89/0x10, is the 16-byte feature report — unused here.)
ANIME_USAGE_PAGE = 0xFF31
ANIME_USAGE = 0x80

REPORT_ID = 0x5E
REPORT_SIZE = 640
PAYLOAD_SIZE = REPORT_SIZE - 1  # 639 bytes after the report ID

LED_COUNT = 810
UPDATE_PAGE_LENGTH = 490  # STRIX profile page size
PAGE_1_PIXELS = UPDATE_PAGE_LENGTH  # 490
PAGE_2_PIXELS = LED_COUNT - PAGE_1_PIXELS  # 320

# Opcodes (first payload byte)
CMD_DISPLAY_STATE = 0xC3  # 0xC3 0x01 [0x00=on | 0x80=off]
CMD_BUILTIN_STATE = 0xC4  # 0xC4 0x01 [0x00=on | 0x80=off]
CMD_BUILTIN_SELECT = 0xC5  # 0xC5 <animByte>
CMD_PREFIX = 0xC0  # 0xC0 <sub> ...
CMD_SUB_BRIGHTNESS = 0x04  # 0xC0 0x04 <mode 0..3>
CMD_SUB_FRAME = 0x02  # 0xC0 0x02 <start_lo> <start_hi> <len_lo> <len_hi> <pixels>
CMD_SUB_LATCH = 0x03  # 0xC0 0x03

BRIGHTNESS_OFF = 0
BRIGHTNESS_DIM = 1
BRIGHTNESS_MEDIUM = 2
BRIGHTNESS_FULL = 3

# Opcodes considered SAFE (cannot damage display, purely stateful toggles)
SAFE_OPCODES = {CMD_DISPLAY_STATE, CMD_BUILTIN_STATE, CMD_PREFIX}


@dataclass(frozen=True)
class SafetyPolicy:
    allow_rollback: bool = True
    allow_brightness: bool = False
    allow_custom_frames: bool = False

    def check(self, opcode: int, sub: int | None = None) -> None:
        # Wake-up magic starts with ASCII 'A' (0x41). Allowed any time we have
        # rollback or custom-frame rights since it's required to talk to the device.
        if opcode == 0x41 and (self.allow_rollback or self.allow_custom_frames):
            return
        if opcode == CMD_DISPLAY_STATE and self.allow_rollback:
            return
        if opcode == CMD_BUILTIN_STATE and self.allow_rollback:
            return
        if opcode == CMD_PREFIX and sub == CMD_SUB_BRIGHTNESS and self.allow_brightness:
            return
        if opcode == CMD_PREFIX and sub in (CMD_SUB_FRAME, CMD_SUB_LATCH) and self.allow_custom_frames:
            return
        raise PermissionError(
            f"Opcode 0x{opcode:02X} sub=0x{sub:02X} blocked by SafetyPolicy" if sub is not None
            else f"Opcode 0x{opcode:02X} blocked by SafetyPolicy"
        )


DEFAULT_POLICY = SafetyPolicy()


def _pkt(*payload: int) -> bytes:
    """Build a 640-byte Feature report from payload bytes. Pads with zeros."""
    buf = bytearray(REPORT_SIZE)
    buf[0] = REPORT_ID
    for i, b in enumerate(payload, start=1):
        if i >= REPORT_SIZE:
            raise ValueError("payload too long")
        buf[i] = b
    return bytes(buf)


def build_wake_up() -> bytes:
    """Magic wake-up: report ID then ASCII 'ASUS Tech.Inc.', rest zero."""
    buf = bytearray(REPORT_SIZE)
    buf[0] = REPORT_ID
    magic = b"ASUS Tech.Inc."
    buf[1 : 1 + len(magic)] = magic
    return bytes(buf)


def build_display_state(on: bool) -> bytes:
    return _pkt(CMD_DISPLAY_STATE, 0x01, 0x00 if on else 0x80)


def build_builtin_state(on: bool) -> bytes:
    return _pkt(CMD_BUILTIN_STATE, 0x01, 0x00 if on else 0x80)


def build_brightness(mode: int) -> bytes:
    if not 0 <= mode <= 3:
        raise ValueError("brightness mode must be 0..3")
    return _pkt(CMD_PREFIX, CMD_SUB_BRIGHTNESS, mode)


def build_frame_pages(pixels: bytes) -> list[bytes]:
    """Two-page frame encoding for 810 LEDs.

    Page headers are `0xC0 0x02 <start_lo> <start_hi> <len_lo> <len_hi>` where
    `start` is 1-based into the pixel buffer and `len` is the byte count of
    pixel data in this page.
    """
    if len(pixels) != LED_COUNT:
        raise ValueError(f"pixels must be exactly {LED_COUNT} bytes, got {len(pixels)}")

    pages: list[bytes] = []
    cursor = 0
    for start_index, page_len in ((1, PAGE_1_PIXELS), (PAGE_1_PIXELS + 1, PAGE_2_PIXELS)):
        buf = bytearray(REPORT_SIZE)
        buf[0] = REPORT_ID
        buf[1] = CMD_PREFIX
        buf[2] = CMD_SUB_FRAME
        buf[3:5] = start_index.to_bytes(2, "little")
        buf[5:7] = page_len.to_bytes(2, "little")
        buf[7 : 7 + page_len] = pixels[cursor : cursor + page_len]
        cursor += page_len
        pages.append(bytes(buf))
    return pages


def build_latch() -> bytes:
    return _pkt(CMD_PREFIX, CMD_SUB_LATCH)

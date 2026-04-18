"""HID device selection and I/O wrapper for the AniMe Vision lid."""

from __future__ import annotations

# Use the hidraw backend (Linux /dev/hidrawN) rather than hid (libusb). The
# libusb backend requires root or /dev/bus/usb/* ACL; hidraw honors our udev
# rule (TAG+=uaccess on hidraw*) so becky can open the device without sudo.
import hidraw as hid

from . import protocol


class DeviceNotFound(RuntimeError):
    pass


def find_lid_device() -> dict:
    """Locate the vendor-specific HID interface for the lid LED."""
    candidates = hid.enumerate(protocol.VENDOR_ID, protocol.PRODUCT_ID)
    if not candidates:
        raise DeviceNotFound(
            f"No HID device found for {protocol.VENDOR_ID:04x}:{protocol.PRODUCT_ID:04x}. "
            f"Is this machine a Strix SCAR 18 G835LX with the lid LED hardware present?"
        )
    anime = [d for d in candidates
             if d["usage_page"] == protocol.ANIME_USAGE_PAGE
             and d["usage"] == protocol.ANIME_USAGE]
    if not anime:
        # Fall back to any interface — hidraw may not expose usage page per collection
        anime = [candidates[0]]
    return anime[0]


class LidDevice:
    """Context-managed handle to the AniMe Vision HID interface.

    Every write goes through a SafetyPolicy check. The default policy only
    permits the rollback opcode.
    """

    def __init__(self, policy: protocol.SafetyPolicy | None = None) -> None:
        self._policy = policy or protocol.DEFAULT_POLICY
        self._dev: hid.device | None = None
        self._path: bytes | None = None

    def __enter__(self) -> LidDevice:
        info = find_lid_device()
        self._path = info["path"]
        self._dev = hid.device()
        self._dev.open_path(self._path)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._dev is not None:
            self._dev.close()
            self._dev = None

    @property
    def path(self) -> str:
        return self._path.decode() if self._path else "(closed)"

    def write(self, packet: bytes) -> int:
        """Send a Feature report. AniMe Vision payloads are 640-byte Features
        (SET_FEATURE over the control pipe), not Output reports."""
        if self._dev is None:
            raise RuntimeError("LidDevice not opened — use as a context manager")
        if len(packet) < 2:
            raise ValueError("packet too short")
        opcode = packet[1]
        sub = packet[2] if opcode == protocol.CMD_PREFIX and len(packet) > 2 else None
        self._policy.check(opcode, sub=sub)
        return self._dev.send_feature_report(packet)

    def init_sequence(self, brightness: int = protocol.BRIGHTNESS_FULL) -> None:
        """Run the g-helper-style init: wake, toggle display, brightness, disable builtin.

        Must be called before sending frames. Requires a policy that allows
        brightness + custom frames (in addition to rollback)."""
        self.write(protocol.build_wake_up())
        self.write(protocol.build_display_state(False))
        self.write(protocol.build_display_state(False))
        self.write(protocol.build_display_state(True))
        self.write(protocol.build_brightness(brightness))
        self.write(protocol.build_builtin_state(False))

    def restore_default(self) -> None:
        """Hand control back to the firmware's built-in animation."""
        self.write(protocol.build_builtin_state(True))
        self.write(protocol.build_display_state(True))



def read_report_descriptor() -> bytes:
    """Read the HID report descriptor from sysfs.

    Must be called BEFORE opening the device with hidapi/libusb, because the
    open call detaches the kernel hid-generic driver, which removes the
    /sys/class/hidraw/hidrawN symlink for that device.
    """
    import glob
    import os

    target = f"{protocol.VENDOR_ID:08X}:{protocol.PRODUCT_ID:08X}"
    for hidraw in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        uevent = os.path.join(hidraw, "device", "uevent")
        if not os.path.exists(uevent):
            continue
        with open(uevent) as f:
            content = f.read().upper()
        if target in content:
            desc_path = os.path.join(hidraw, "device", "report_descriptor")
            with open(desc_path, "rb") as f:
                return f.read()
    raise DeviceNotFound(
        f"No hidraw node exposes {target}. If hidapi has already opened the "
        f"device, the kernel driver is detached and the sysfs entry is gone — "
        f"unplug/replug or reboot to re-attach, then dump before opening."
    )

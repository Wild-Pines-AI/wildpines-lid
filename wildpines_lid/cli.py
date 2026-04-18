"""wildpines-lid command-line interface."""

from __future__ import annotations

import sys
import time as _t
from pathlib import Path

import click

from . import protocol
from .animations import wildpines
from .daemon import AnimationDaemon
from .framebuffer import Framebuffer
from .hid_io import DeviceNotFound, LidDevice


def _frame_allowed_policy() -> protocol.SafetyPolicy:
    return protocol.SafetyPolicy(allow_rollback=True, allow_brightness=True, allow_custom_frames=True)


@click.group()
def main() -> None:
    """Wild Pines AI driver for the ROG Strix SCAR 18 AniMe Vision lid."""


@main.command("list-devices")
def list_devices() -> None:
    """List HID interfaces for the lid device."""
    import hidraw as hid

    devs = hid.enumerate(protocol.VENDOR_ID, protocol.PRODUCT_ID)
    if not devs:
        click.echo(f"No {protocol.VENDOR_ID:04x}:{protocol.PRODUCT_ID:04x} devices found.", err=True)
        sys.exit(1)
    for d in devs:
        click.echo(
            f"iface={d['interface_number']} "
            f"usage_page=0x{d['usage_page']:04x} "
            f"usage=0x{d['usage']:04x} "
            f"path={d['path'].decode()}"
        )


@main.command("dump-descriptor")
@click.option("--out", type=click.Path(), default="captures/report_descriptor.bin")
def dump_descriptor(out: str) -> None:
    """Dump the HID report descriptor. Reads from sysfs BEFORE opening the
    device, because opening detaches the kernel driver and hides the
    descriptor."""
    from .hid_io import read_report_descriptor

    try:
        desc = read_report_descriptor()
    except DeviceNotFound as e:
        click.echo(str(e), err=True)
        sys.exit(1)

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        f.write(desc)
    click.echo(f"Wrote {len(desc)} bytes to {out}")
    for i in range(0, min(len(desc), 256), 16):
        chunk = desc[i : i + 16]
        click.echo(f"  {i:04x}  {' '.join(f'{b:02x}' for b in chunk)}")


@main.command("restore-default")
def restore_default() -> None:
    """Hand the lid back to the firmware's built-in animation."""
    try:
        with LidDevice(policy=protocol.SafetyPolicy(allow_rollback=True)) as dev:
            dev.restore_default()
        click.echo("Restored firmware default.")
    except Exception as e:
        click.echo(f"Failed: {e}", err=True)
        sys.exit(1)


@main.command("preview-animation")
@click.option("--out-dir", type=click.Path(), default="captures/preview")
@click.option("--every-n-frames", type=int, default=3)
def preview_animation(out_dir: str, every_n_frames: int) -> None:
    """Render previews: upright canvas (what you'd see) + planar LED mapping."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()
    total = 0
    saved = 0
    for i, fb in enumerate(wildpines.frames()):
        total += 1
        if i % every_n_frames == 0:
            fb.to_png(out / f"frame_{i:04d}_upright.png", scale=8)
            if hasattr(fb, "to_planar_preview_png"):
                fb.to_planar_preview_png(out / f"frame_{i:04d}_planar.png", scale=12)
            saved += 1
    click.echo(f"Rendered {total} frames, saved {saved*2} PNGs to {out_dir}")


@main.command("test-pixel")
@click.argument("index", type=int)
@click.option("--brightness", type=int, default=128)
@click.option("--hold", type=float, default=5.0)
@click.option("--confirm", is_flag=True)
def test_pixel(index: int, brightness: int, hold: float, confirm: bool) -> None:
    """Light a single LED by linear index (0..809)."""
    if not confirm:
        click.echo("Refusing to write without --confirm.", err=True)
        sys.exit(2)
    if not 0 <= index < protocol.LED_COUNT:
        click.echo(f"index must be 0..{protocol.LED_COUNT - 1}", err=True)
        sys.exit(1)

    pixels = bytearray(protocol.LED_COUNT)
    pixels[index] = max(0, min(255, brightness))

    try:
        with LidDevice(policy=_frame_allowed_policy()) as dev:
            dev.init_sequence()
            for pkt in protocol.build_frame_pages(bytes(pixels)):
                dev.write(pkt)
            dev.write(protocol.build_latch())
            click.echo(f"Lit LED {index}. Holding {hold}s...")
            _t.sleep(hold)
            dev.restore_default()
            click.echo("Restored default.")
    except Exception as e:
        click.echo(f"Failed: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--duration", type=float, default=None)
def run(duration: float | None) -> None:
    """Run the animation daemon. Ctrl-C / SIGTERM / --duration triggers rollback."""
    sys.exit(AnimationDaemon(duration=duration).run())


@main.command("all-on")
@click.option("--brightness", type=int, default=128)
@click.option("--hold", type=float, default=5.0)
@click.option("--confirm", is_flag=True)
def all_on(brightness: int, hold: float, confirm: bool) -> None:
    """Light every mapped LED at the same brightness."""
    if not confirm:
        click.echo("Refusing to write without --confirm.", err=True)
        sys.exit(2)

    pixels = bytes([max(0, min(255, brightness))] * protocol.LED_COUNT)
    try:
        with LidDevice(policy=_frame_allowed_policy()) as dev:
            dev.init_sequence()
            for pkt in protocol.build_frame_pages(pixels):
                dev.write(pkt)
            dev.write(protocol.build_latch())
            click.echo(f"All LEDs at {brightness}. Holding {hold}s...")
            _t.sleep(hold)
            dev.restore_default()
            click.echo("Restored default.")
    except Exception as e:
        click.echo(f"Failed: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--cycles", type=int, default=3)
@click.option("--period", type=float, default=1.0)
@click.option("--brightness", type=int, default=200)
@click.option("--confirm", is_flag=True)
def blink(cycles: int, period: float, brightness: int, confirm: bool) -> None:
    """Blink all pixels on/off."""
    if not confirm:
        click.echo("Refusing to write without --confirm.", err=True)
        sys.exit(2)

    on = bytes([max(0, min(255, brightness))] * protocol.LED_COUNT)
    off = bytes(protocol.LED_COUNT)

    try:
        with LidDevice(policy=_frame_allowed_policy()) as dev:
            dev.init_sequence()
            latch = protocol.build_latch()
            for _ in range(cycles):
                for pkt in protocol.build_frame_pages(on):
                    dev.write(pkt)
                dev.write(latch)
                _t.sleep(period / 2)
                for pkt in protocol.build_frame_pages(off):
                    dev.write(pkt)
                dev.write(latch)
                _t.sleep(period / 2)
            dev.restore_default()
            click.echo(f"Blinked {cycles} cycles. Restored default.")
    except Exception as e:
        click.echo(f"Failed: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

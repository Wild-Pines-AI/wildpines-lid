# wildpines-lid

Wild Pines AI animation driver for the ROG Strix SCAR 18 (G835LX) AniMe Vision lid LED.

The lid has 810 mini-LEDs through ~9,152 precision-milled holes in a non-rectangular array. `asusctl` doesn't yet support this hardware; this driver is a userspace HID tool that talks to it directly, based on partial protocol mapping from [g-helper](https://github.com/seerge/g-helper).

Custom-frame writes are gated behind the `SafetyPolicy` in `wildpines_lid/protocol.py` until each opcode is verified on hardware.

Repo: `git@github.com:Wild-Pines-AI/wildpines-lid.git`.

## Hardware

ROG Strix SCAR 18 G835LX, AniMe Vision lid array. 810 LEDs in a diagonal parallelogram (slash) shape: a 34 col x 68 row grid, the first 29 rows rectangular (`FULL_ROWS`) and the rest tapering, with pitch computed per row in `wildpines_lid/geometry.py`.

USB HID `0x0b05:0x193b` at interface 0. Vendor-specific HID, report ID `0x5E`, 640-byte feature reports. `/dev/hidraw*` nodes are root-owned, so `/etc/udev/rules.d/99-wildpines-lid.rules` grants access by `uaccess` tag on the matching vendor and product ids.

## Protocol

Confirmed against the g-helper STRIX profile plus our own descriptor dump.

| Command | Bytes |
|---------|-------|
| Wake-up | `0x5E` + ASCII `"ASUS Tech.Inc."` + zeros |
| Display state | `0xC3 0x01 0x00` on, `0xC3 0x01 0x80` off |
| Builtin animation | `0xC4 0x01 0x00` on (the rollback lever), `0xC4 0x01 0x80` off (required before custom frames) |
| Brightness | `0xC0 0x04 <mode 0..3>` |
| Frame | `0xC0 0x02 <start_lo> <start_hi> <len_lo> <len_hi> <pixels>`, paged as 490 + 320 pixels, `start` is 1-based |
| Latch | `0xC0 0x03` |

Init sequence: wake, display-off twice, display-on, brightness, builtin-off, then frames.

All magic numbers live in `wildpines_lid/protocol.py` behind the `SafetyPolicy` gate.

## Geometry: the lattice is diagonal

The planar (row, col) LED buffer is a diamond lattice. Neighboring planar cells are not horizontally adjacent on the physical lid, so content authored directly in planar space renders skewed. Author instead in a `DiagonalCanvas` (`wildpines_lid/canvas.py`, 68x39 for text, 97x63 general) and let it apply g-helper's transform:

```
plX = (x - y) / 2
plY = x + y
```

For a 68x39 canvas with `deltaX=5, deltaY=24`, the valid projection region is `x` in [0, 62] and `y` in [24, 38], a 63x15 band. That band is what constrains how large lid text can be.

## Rollback, three layers

1. `systemctl --user stop wildpines-lid.service`: the daemon exits and the firmware resumes its built-in animation in about two seconds. `daemon.py`'s SIGTERM handler calls `dev.restore_default()` on the way out.
2. `wildpines-lid restore-default`: sends `enable-builtin` and `display-on` explicitly.
3. Cold boot: always reverts.

None of these writes to persistent storage. The firmware's factory animation lives in the controller and isn't touched.

## Workflow

```bash
# 1. Confirm device is reachable (read-only)
.venv/bin/wildpines-lid list-devices

# 2. Capture report descriptor for protocol analysis (read-only)
.venv/bin/wildpines-lid dump-descriptor

# 3. Prove rollback works BEFORE any custom write
.venv/bin/wildpines-lid restore-default

# 4. Preview the animation without touching hardware
.venv/bin/wildpines-lid preview-animation
# open captures/preview/*.png

# 5. Map geometry (one LED at a time, requires --confirm)
.venv/bin/wildpines-lid test-pixel 0 --confirm
.venv/bin/wildpines-lid restore-default
# record which physical LED lit up; repeat for indices 100, 400, 800

# 6. Install as systemd user service
./install.sh
systemctl --user enable --now wildpines-lid.service
```

## Module layout

- `wildpines_lid/protocol.py`: all HID magic numbers and the `SafetyPolicy` gate. Read this before adding any new opcode
- `wildpines_lid/hid_io.py`: device selection and write wrapper
- `wildpines_lid/geometry.py`: the 810-LED coordinate map, per-row pitch derived from the g-helper row layout
- `wildpines_lid/canvas.py`: `DiagonalCanvas`, the upright authoring surface and its projection into planar space
- `wildpines_lid/framebuffer.py`: 2D grayscale buffer, HID packet builder, PNG preview
- `wildpines_lid/font.py`: bitmap font with per-glyph widths, upper-case ASCII subset
- `wildpines_lid/animations/wildpines.py`: the looping Wild Pines animation. Its text stage renders DejaVu Sans Bold from `/usr/share/fonts/truetype/dejavu/`
- `wildpines_lid/daemon.py`: main loop and SIGTERM rollback
- `wildpines_lid/cli.py`: the `wildpines-lid` entrypoint
- `systemd/wildpines-lid.service`: user unit with `ExecStop=restore-default`

## Service

The daemon runs as the `wildpines-lid.service` systemd **user** unit, installed to
`~/.config/systemd/user/` by `install.sh`. It survives reboot only if lingering is enabled for
the user (`loginctl show-user <user> | grep Linger`).

## Reference

Protocol patterns come from [g-helper](https://github.com/seerge/g-helper)'s STRIX profile,
which maps this hardware partially. This driver fills in what was missing for the G835LX.

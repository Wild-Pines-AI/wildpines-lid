# Claude Session Context — wildpines-lid

Userspace Python HID driver for the ROG Strix SCAR 18 (G835LX) AniMe Vision lid display. Built because `asusctl` doesn't support this hardware yet. Displays the Wild Pines branding reading along the diagonal slash of the lid LED array.

Repo: `git@github.com:Wild-Pines-AI/wildpines-lid.git`. Local at `~/workspace/wildpines-lid/`.

## Hardware

ROG Strix SCAR 18 G835LX, AniMe Vision lid array. 810 LEDs in a diagonal parallelogram / slash shape (34 cols × 68 rows grid, FullRows=29, pitch computed per row). USB HID `0x0b05:0x193b` at iface 0, path `5-13:1.0`. Vendor-specific HID, Report ID `0x5E`, 640-byte Feature reports. `/dev/hidraw3` is root-owned mode 600 — udev rule at `/etc/udev/rules.d/99-wildpines-lid.rules` provides non-root access.

## Protocol (confirmed via g-helper STRIX profile + our descriptor dump)

- **Wake-up:** `0x5E` + ASCII `"ASUS Tech.Inc."` + zeros
- **Display state:** `0xC3 0x01 0x00` (on), `0xC3 0x01 0x80` (off)
- **Builtin animation:** `0xC4 0x01 0x00` (on, rollback lever), `0xC4 0x01 0x80` (off, required before custom frames)
- **Brightness:** `0xC0 0x04 <mode 0..3>`
- **Frame:** `0xC0 0x02 <start_lo> <start_hi> <len_lo> <len_hi> <pixels>` — paged as 490 + 320 pixels, `start` is 1-based
- **Latch:** `0xC0 0x03`
- **Init sequence:** wake, display-off×2, display-on, brightness, builtin-off, then frames

All magic numbers live in `wildpines_lid/protocol.py` behind the `SafetyPolicy` gate — custom-frame writes are blocked until each opcode is verified on hardware.

## Critical geometry insight

The planar (row, col) LED buffer is a **diamond lattice**. Neighboring planar cells are NOT horizontally adjacent on the physical lid. To draw upright content, author in a **DiagonalCanvas** (68×39 for text, 97×63 general) and apply g-helper's transform:

```
plX = (x - y) / 2
plY = x + y
```

For a 68×39 canvas with `deltaX=5, deltaY=24`, the valid projection region is `x ∈ [0, 62], y ∈ [24, 38]` — a 63×15 band.

## Font sizes that fit the 63×15 band (DejaVu Sans Bold)

- `"WILD PINES AI"` one line, size 7: 57×5, fits but too small
- `"WILD PINES"` + `"AI"` stacked, size 9: 60×7 per line, 2 lines, readable → **current choice**
- Single-line `"WP AI"`, size 14–16: fits, bigger but loses the full brand

## Rollback layers (none persist to storage)

1. `systemctl --user stop wildpines-lid.service` — daemon exits, firmware resumes built-in animation in ~2s.
2. `wildpines-lid restore-default` — sends `enable-builtin` + `display-on` explicitly.
3. Cold boot — always reverts.

SIGTERM handler in `wildpines_lid/daemon.py` calls `dev.restore_default()` on shutdown.

## Service status

Daemon runs as `wildpines-lid.service` systemd **user** unit (enabled, survives reboot if linger is on). Unit file: `~/.config/systemd/user/wildpines-lid.service` (source at `systemd/wildpines-lid.service`).

```bash
# Status / logs
systemctl --user status wildpines-lid
journalctl --user -u wildpines-lid -f

# Verify reboot persistence
loginctl show-user becky | grep Linger    # expect Linger=yes

# Restart after code changes
systemctl --user restart wildpines-lid
```

## Module layout

- `wildpines_lid/protocol.py` — HID magic numbers + `SafetyPolicy` gate (read this before adding any new opcode)
- `wildpines_lid/hid_io.py` — device selection + write wrapper
- `wildpines_lid/geometry.py` — 810-LED coordinate map
- `wildpines_lid/framebuffer.py` — 2D grayscale buffer + HID packet builder + PNG preview
- `wildpines_lid/font.py` — bitmap font for the Wild Pines text
- `wildpines_lid/animations/wildpines.py` — the 9-second animation sequence
- `wildpines_lid/daemon.py` — main loop + SIGTERM rollback
- `wildpines_lid/cli.py` — `wildpines-lid` entrypoint

## Workflow when changing the animation or protocol

1. `wildpines-lid list-devices` (read-only, confirms device is reachable).
2. `wildpines-lid dump-descriptor` if protocol analysis is needed (read-only).
3. **Prove rollback works first.** `wildpines-lid restore-default` before any custom write.
4. `wildpines-lid preview-animation` renders PNGs to `captures/preview/*.png` without touching hardware.
5. Single-LED tests require `--confirm`: `wildpines-lid test-pixel <idx> --confirm`, then `restore-default`.
6. Service restart after code changes (above).

## Cross-references

- README.md has the high-level pitch + rollback layers.
- Source protocol patterns: [g-helper](https://github.com/seerge/g-helper) STRIX profile (partial mapping; this driver fills in what was missing for the G835LX).

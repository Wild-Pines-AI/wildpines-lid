# wildpines-lid

Wild Pines AI animation driver for the ROG Strix SCAR 18 (G835LX) AniMe Vision lid LED.

The lid has 810 mini-LEDs through ~9,152 precision-milled holes in a non-rectangular array. `asusctl` doesn't yet support this hardware; this driver is a userspace HID tool that talks to it directly, based on partial protocol mapping from [g-helper](https://github.com/seerge/g-helper).

## Status

Protocol discovery phase. Rollback path is in place; custom-frame writes are gated behind the `SafetyPolicy` in `wildpines_lid/protocol.py` until each opcode is verified on hardware.

## Rollback — three layers

1. `systemctl --user stop wildpines-lid.service` — daemon exits, firmware resumes built-in animation.
2. `wildpines-lid restore-default` — sends the `enable-builtin` opcode explicitly.
3. Cold boot — always reverts.

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

# 5. Map geometry (one LED at a time — requires --confirm)
.venv/bin/wildpines-lid test-pixel 0 --confirm
.venv/bin/wildpines-lid restore-default
# record which physical LED lit up; repeat for indices 100, 400, 800

# 6. Install as systemd user service
./install.sh
systemctl --user enable --now wildpines-lid.service
```

## Files

- `wildpines_lid/protocol.py` — all HID magic numbers and the `SafetyPolicy` gate
- `wildpines_lid/hid_io.py` — device selection + write wrapper
- `wildpines_lid/geometry.py` — 810-LED coordinate map (placeholder until calibrated)
- `wildpines_lid/framebuffer.py` — 2D grayscale buffer + HID packet builder + PNG preview
- `wildpines_lid/font.py` — 3x5 bitmap font for "WILD PINES AI"
- `wildpines_lid/animations/wildpines.py` — the 9-second cool animation sequence
- `wildpines_lid/daemon.py` — loop + SIGTERM rollback
- `wildpines_lid/cli.py` — `wildpines-lid` entrypoint
- `systemd/wildpines-lid.service` — user unit with `ExecStop=restore-default`

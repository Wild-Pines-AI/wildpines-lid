# wildpines-lid

**Rules only in this file.** Not architecture, not status, not repo facts, not changelog:
those live in `README.md`. Before adding a line, ask whether it would go stale when the code
changes. If yes, it was never a rule and it belongs somewhere else.

Userspace Python HID driver for the ROG Strix SCAR 18 (G835LX) AniMe Vision lid display.
Hardware, protocol, geometry and module layout are in `README.md`.

## Rules

This driver writes to laptop firmware over raw HID, so the working order is rollback first,
hardware second.

1. **Prove rollback works before any custom write.** Run `wildpines-lid restore-default` and
   confirm the firmware animation comes back, every session, before sending a custom frame.
2. **Single-LED tests require `--confirm`.** `wildpines-lid test-pixel <idx> --confirm`, then
   `restore-default` afterwards. The flag exists so a hardware write cannot happen by
   autocomplete.
3. **Read `SafetyPolicy` in `wildpines_lid/protocol.py` before adding an opcode.** Custom-frame
   writes stay gated there until the opcode has been verified on hardware. Do not widen the
   gate to make something work.
4. Prefer the read-only paths while developing: `list-devices` and `dump-descriptor` touch
   nothing, and `preview-animation` renders to `captures/preview/*.png` without going near the
   device.

General rules that bind here: `~/.claude/CLAUDE.md` and `~/workspace/CLAUDE.md`.

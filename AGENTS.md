# Wildpines Lid working instructions

Follow README.md for device operation.
- Prove rollback with restore-default before custom hardware writes each session.
- Single-pixel writes require explicit --confirm and restoration afterwards.
- Read SafetyPolicy in wildpines_lid/protocol.py before adding opcodes; verify hardware behavior before widening gates.
- Prefer read-only discovery and local previews during development.

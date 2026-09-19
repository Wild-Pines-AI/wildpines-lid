# Wildpines Lid working instructions

Read README.md for protocol and device operation.
- Prove rollback with restore-default before custom hardware writes each session.
- Single-pixel writes require explicit --confirm and restoration afterwards.
- Read SafetyPolicy in wildpines_lid/protocol.py before adding opcodes. Do not widen hardware gates without verification.
- Prefer read-only discovery and local previews while developing.
Validate locally and commit/push completed work to main.

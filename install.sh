#!/usr/bin/env bash
# Install wildpines-lid as a user-level systemd service.
#
# Before running this, make sure you've validated the rollback path:
#   1. .venv/bin/wildpines-lid list-devices           # confirms device found
#   2. .venv/bin/wildpines-lid dump-descriptor        # captures descriptor for RE
#   3. .venv/bin/wildpines-lid restore-default        # verifies rollback opcode
#
# If restore-default works, then the daemon's ExecStop rollback will work too.

set -euo pipefail

PROJ="$(cd "$(dirname "$0")" && pwd)"
BIN="$HOME/.local/bin/wildpines-lid"
UNIT_DIR="$HOME/.config/systemd/user"

mkdir -p "$HOME/.local/bin" "$UNIT_DIR"

cat > "$BIN" <<EOF
#!/usr/bin/env bash
exec "$PROJ/.venv/bin/wildpines-lid" "\$@"
EOF
chmod +x "$BIN"

cp "$PROJ/systemd/wildpines-lid.service" "$UNIT_DIR/wildpines-lid.service"

systemctl --user daemon-reload
echo
echo "Installed. To enable and start:"
echo "  systemctl --user enable --now wildpines-lid.service"
echo
echo "To roll back at any time:"
echo "  systemctl --user stop wildpines-lid.service"
echo "  wildpines-lid restore-default"

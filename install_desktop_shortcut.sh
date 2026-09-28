#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
ICON_PATH="$APP_DIR/genmul_icon.png"
DISTRO_BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_LAUNCH_DIR="$HOME/Desktop"
mkdir -p "$DISTRO_BIN_DIR" "$DESKTOP_DIR" "$DESKTOP_LAUNCH_DIR"

cat > "$DISTRO_BIN_DIR/approx-genmul" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$APP_DIR"
if [[ ! -d build ]]; then
  cmake -S . -B build >/dev/null 2>&1 || true
fi
cmake --build build -j"$(nproc 2>/dev/null || echo 4)" >/dev/null 2>&1 || true
exec python3 src/genmul_gui.py
EOF

chmod +x "$DISTRO_BIN_DIR/approx-genmul"

cat > "$DESKTOP_DIR/ApproxGenmul.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Approx GenMul
Comment=Approximate multiplier generator and tree preview
Exec=$DISTRO_BIN_DIR/approx-genmul
Icon=$ICON_PATH
Terminal=false
Categories=Development;Science;
StartupNotify=true
Path=$APP_DIR
EOF

cp "$DESKTOP_DIR/ApproxGenmul.desktop" "$DESKTOP_LAUNCH_DIR/ApproxGenmul.desktop"
chmod +x "$DESKTOP_DIR/ApproxGenmul.desktop" "$DESKTOP_LAUNCH_DIR/ApproxGenmul.desktop"

echo "Desktop shortcut installed: $DESKTOP_DIR/ApproxGenmul.desktop"
echo "Desktop launcher copied to: $DESKTOP_LAUNCH_DIR/ApproxGenmul.desktop"
echo "Launcher installed: $DISTRO_BIN_DIR/approx-genmul"

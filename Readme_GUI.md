# Approx GenMul – Quick Start for Sharing and Running

This file is meant for anyone who wants to install and run the project on a Linux machine without reading the full development notes.

## 1) Requirements

Install the required system packages:

```bash
sudo apt update
sudo apt install -y build-essential cmake python3 python3-tk python3-pil python3-reportlab
```

If they also want the equivalence-check workflow with Yosys:

```bash
sudo apt install -y yosys
```

## 2) Download the project

```bash
git clone <https://github.com/Thread-t/APPROX_GENMUL.git>
cd APPROX_GENMUL
```

If you are sharing a zip file instead, extract it first and then go into the project directory.

## 3) Install and build

Run:

```bash
cmake -S . -B build
cmake --build build -j"$(nproc 2>/dev/null || echo 4)"
```

## 4) Launch the GUI

You can launch it directly from the project folder:

```bash
python3 src/genmul_gui.py
```

Or use the provided launcher script:

```bash
bash launch_genmul.sh
```

## 5) Desktop shortcut setup

To create a desktop icon and a launcher command for the tool, run:

```bash
bash install_desktop_shortcut.sh
```

This creates:

- a command at ~/.local/bin/approx-genmul
- a desktop entry at ~/.local/share/applications/ApproxGenmul.desktop
- a shortcut on the Desktop folder as well

Then you can click the Desktop shortcut or launch it from the application menu.

```

## 6) Notes

- This tool is intended for Linux-based desktop usage.
- The app can be launched either from a terminal or from a desktop icon once the shortcut is installed.
- Yosys is only required for the formal equivalence check flow feature.

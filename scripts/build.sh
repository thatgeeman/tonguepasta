#!/usr/bin/env bash
set -e

PLATFORM=$(uname)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_DIR="$SCRIPT_DIR/../src"

if [[ "$PLATFORM" == "Darwin" ]]; then
    HIDDEN="pynput.keyboard._darwin pynput.mouse._darwin"
elif [[ "$PLATFORM" == "Linux" ]]; then
    HIDDEN="pynput.keyboard._xorg pynput.mouse._xorg"
else
    echo "Unsupported platform: $PLATFORM"
    echo "On Windows, use scripts/build.ps1 instead."
    exit 1
fi

HIDDEN_ARGS=""
for h in $HIDDEN; do
    HIDDEN_ARGS="$HIDDEN_ARGS --hidden-import $h"
done

cd "$SRC_DIR"
python -m PyInstaller --onefile --noconsole \
    $HIDDEN_ARGS \
    --hidden-import corrector \
    --name tonguepasta \
    main.py

echo ""
echo "Build complete: src/dist/tonguepasta"

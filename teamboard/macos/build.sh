#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
TEAMBOARD_DIR="$(cd "$SCRIPT_DIR/.." && pwd -P)"
APP_DIR="$TEAMBOARD_DIR/Agent Team Board.app"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"

mkdir -p "$MACOS_DIR"
cp "$SCRIPT_DIR/Info.plist" "$CONTENTS_DIR/Info.plist"

xcrun swiftc \
  -parse-as-library \
  -O \
  -target "$(uname -m)-apple-macosx13.0" \
  -framework SwiftUI \
  -framework AppKit \
  "$SCRIPT_DIR/TeamBoardApp.swift" \
  -o "$MACOS_DIR/AgentTeamBoard"

chmod 755 "$MACOS_DIR/AgentTeamBoard"
plutil -lint "$CONTENTS_DIR/Info.plist"
echo "Built $APP_DIR"

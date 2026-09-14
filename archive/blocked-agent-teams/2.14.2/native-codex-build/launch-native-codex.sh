#!/bin/sh
set -eu

APP_ROOT='/Users/uno/.local/share/agent-toolkit/apps/agent-teams-ai/2.14.2/native-codex-build/mac-arm64/Agent Teams AI.app'
APP_BIN="$APP_ROOT/Contents/MacOS/Agent Teams AI"
CODEX_BIN='/Applications/ChatGPT.app/Contents/Resources/codex'
EXPECTED_CODEX_SHA256='ecad78dbf98adb89ec475edac86630406cbe59d9f3070b17d88065f136b94bcb'

if [ ! -x "$APP_BIN" ]; then
  echo "Agent Teams AI build is missing or not executable: $APP_BIN" >&2
  exit 1
fi

if [ ! -x "$CODEX_BIN" ]; then
  echo "Native Codex is missing or not executable: $CODEX_BIN" >&2
  exit 1
fi

actual_codex_sha256=$(/usr/bin/shasum -a 256 "$CODEX_BIN" | /usr/bin/awk '{print $1}')
if [ "$actual_codex_sha256" != "$EXPECTED_CODEX_SHA256" ]; then
  echo 'Native Codex changed since this profile was reviewed; refusing to launch.' >&2
  echo "Expected: $EXPECTED_CODEX_SHA256" >&2
  echo "Actual:   $actual_codex_sha256" >&2
  exit 1
fi

if [ "${1:-}" = '--print-config' ]; then
  echo "app=$APP_ROOT"
  echo "codex=$CODEX_BIN"
  echo "codex_sha256=$actual_codex_sha256"
  echo 'codex_account_profile=modern'
  echo 'default_auto_approve=false'
  echo 'execution=blocked'
  echo 'blocker=bundled runtime creates a temporary CODEX_HOME and links or copies account/auth artifacts'
  exit 0
fi

echo 'Execution is blocked: the bundled closed runtime creates a temporary CODEX_HOME and links or copies account/auth artifacts.' >&2
echo 'A source-controlled runtime seam that uses the existing native Codex home directly is required before this build can be launched.' >&2
echo 'Use --print-config for the reviewed static configuration.' >&2
exit 64

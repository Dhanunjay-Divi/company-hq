#!/usr/bin/env bash
# Install the pinned unsigned Apple Silicon preview from the public GitHub release.
set -euo pipefail

version='0.1.1'
asset="Company_HQ_${version}_aarch64.dmg"
release="https://github.com/Dhanunjay-Divi/company-hq/releases/download/v${version}"
destination="$HOME/Applications"

usage() {
  printf 'Usage: bash install-macos.sh [--destination FOLDER]\n'
  printf 'Installs Company HQ %s for the current macOS user.\n' "$version"
}
while (($#)); do
  case "$1" in
    --destination) [[ $# -ge 2 ]] || { usage >&2; exit 2; }; destination="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

[[ "$(uname -s)" == Darwin ]] || { echo 'Company HQ currently has a macOS build only.' >&2; exit 1; }
if [[ "$(uname -m)" != arm64 && "$(sysctl -n hw.optional.arm64 2>/dev/null || true)" != 1 ]]; then
  echo 'This release requires an Apple Silicon Mac.' >&2
  exit 1
fi
for command in curl shasum hdiutil ditto mktemp; do
  command -v "$command" >/dev/null || { echo "Missing macOS tool: $command" >&2; exit 1; }
done

[[ "$destination" == /* ]] || { echo 'Destination must be an absolute folder path.' >&2; exit 2; }
[[ ! -L "$destination" ]] || { echo 'Destination cannot be a symlink.' >&2; exit 1; }
mkdir -p "$destination"
destination="$(cd "$destination" && pwd -P)"
target="$destination/Company HQ.app"
[[ ! -L "$target" ]] || { echo 'Existing app path cannot be a symlink.' >&2; exit 1; }
if pgrep -x company-hq-app >/dev/null 2>&1; then
  echo 'Quit Company HQ before updating it, then run this installer again.' >&2
  exit 1
fi

work="$(mktemp -d "${TMPDIR:-/tmp}/company-hq-install.XXXXXX")"
mount="$work/mount"
stage=""
backup=""
mounted=0
installed=0
cleanup() {
  if [[ -n "$backup" && -e "$backup" && ! -e "$target" ]]; then mv "$backup" "$target"; fi
  if [[ "$installed" == 1 && -n "$backup" && -e "$backup" ]]; then rm -rf "$backup"; fi
  if [[ "$mounted" == 1 ]]; then hdiutil detach -quiet "$mount" >/dev/null 2>&1 || true; fi
  if [[ -n "$stage" && -d "$stage" ]]; then rm -rf "$stage"; fi
  rm -rf "$work"
}
trap cleanup EXIT

printf 'Downloading Company HQ %s...\n' "$version"
curl -fsSL --retry 3 --connect-timeout 15 "$release/$asset" -o "$work/$asset"
curl -fsSL --retry 3 --connect-timeout 15 "$release/$asset.sha256" -o "$work/$asset.sha256"
expected="$(awk 'NR == 1 {print $1}' "$work/$asset.sha256")"
[[ "$expected" =~ ^[[:xdigit:]]{64}$ ]] || { echo 'Release checksum is invalid.' >&2; exit 1; }
actual="$(shasum -a 256 "$work/$asset" | awk '{print $1}')"
[[ "$actual" == "$expected" ]] || { echo 'Download checksum mismatch; nothing was installed.' >&2; exit 1; }

mkdir "$mount"
hdiutil attach -quiet -nobrowse -readonly -mountpoint "$mount" "$work/$asset"
mounted=1
[[ -d "$mount/Company HQ.app" ]] || { echo 'Release does not contain Company HQ.app.' >&2; exit 1; }
stage="$(mktemp -d "$destination/.company-hq-stage.XXXXXX")"
ditto "$mount/Company HQ.app" "$stage/Company HQ.app"
if [[ -e "$target" ]]; then
  backup="$destination/.company-hq-backup.$$.app"
  mv "$target" "$backup"
fi
mv "$stage/Company HQ.app" "$target"
installed=1
printf 'Installed: %s\n' "$target"
echo 'This preview is unsigned and not notarized. macOS may ask you to approve opening it in System Settings → Privacy & Security.'

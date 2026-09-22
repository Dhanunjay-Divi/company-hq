# Desktop package

`python3 scripts/build_desktop.py` builds the Vite frontend, freezes the transitional Python loopback backend with the pinned PyInstaller version, then asks Tauri to create an unsigned local desktop bundle. The bundled backend listens only on a newly chosen `127.0.0.1` port; the Rust shell accepts only that reported loopback URL.

The application keeps its state in the normal external Company HQ state root. It does not set `HOME`, `CODEX_HOME`, or provider authentication paths, and it does not copy provider credentials or attached project files into the bundle.

The Rust shell owns the packaged child lifecycle and exposes narrow IPC for a native folder picker plus opening and validating paths confined to an approved project root. The existing loopback API remains the backend authority during the Python-to-Rust migration.

Build requirements are Node, Rust, Xcode command-line tools, and a compatible Python build environment. The build script creates the ignored `.desktop-build-venv` and installs `PyInstaller==6.16.0` there. It does not install global dependencies.

The resulting macOS application is unsigned and not notarized. Apple Developer signing and notarization credentials are required before distribution outside local development. A DMG is requested by `python3 scripts/build_desktop.py --dmg` when Tauri can create it; its presence does not imply signing or notarization.

Run `python3 -m unittest -v tests.test_desktop_package` for static packaging-contract checks. A successful package build verifies that the artifact can be created; it does not verify native Codex account access, macOS permissions, every provider adapter, or a signed release.

#!/usr/bin/env python3
"""Install reviewed native tools into the ignored app bundle, never global PATH."""
from pathlib import Path
import hashlib
import io
import json
import os
import platform
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def install_engines():
    system = platform.system().lower()
    arm = platform.machine().lower() in ('arm64', 'aarch64')
    architecture = 'arm64' if arm else 'amd64'
    beads = f'beads_1.3.0_{system}_{architecture}.' + ('zip' if system == 'windows' else 'tar.gz')
    target = {'darwin': f'{"aarch64" if arm else "x86_64"}-apple-darwin.tar.gz',
              'linux': 'aarch64-unknown-linux-gnu.tar.gz' if arm else 'x86_64-unknown-linux-musl.tar.gz',
              'windows': 'x86_64-pc-windows-msvc.zip'}.get(system)
    if not target: raise RuntimeError(f'No reviewed engines for {system}')
    manifest = json.loads((ROOT / 'scripts/engines.lock.json').read_text())
    for name, asset in [('beads', beads), ('rtk', 'rtk-' + target)]:
        spec = manifest[name]
        if asset not in spec['assets']: raise RuntimeError(f'No reviewed {name} build for this platform')
        binary = spec['binary'] + ('.exe' if system == 'windows' else '')
        destination = ROOT / 'build/tools' / binary
        receipt = destination.with_suffix('.receipt.json')
        if destination.is_file() and receipt.is_file():
            old = json.loads(receipt.read_text())
            if old.get('asset') == asset and old.get('binarySha256') == hashlib.sha256(destination.read_bytes()).hexdigest(): continue
        pinned = spec['assets'][asset]
        with urllib.request.urlopen(pinned['url'], timeout=60) as response: content = response.read()
        if hashlib.sha256(content).hexdigest() != pinned['sha256']: raise RuntimeError(f'{name} checksum mismatch')
        if asset.endswith('.zip'):
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                matches = [x for x in archive.infolist() if Path(x.filename).name == binary and not x.is_dir()]
                if len(matches) != 1: raise RuntimeError(f'{name} has an ambiguous archive')
                payload = archive.read(matches[0])
        else:
            with tarfile.open(fileobj=io.BytesIO(content)) as archive:
                matches = [x for x in archive if Path(x.name).name == binary and x.isfile()]
                if len(matches) != 1: raise RuntimeError(f'{name} has an ambiguous archive')
                payload = archive.extractfile(matches[0]).read()
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix('.download')
        temporary.write_bytes(payload); temporary.chmod(0o755); os.replace(temporary, destination)
        receipt.write_text(json.dumps({'asset': asset, 'archiveSha256': pinned['sha256'], 'binarySha256': hashlib.sha256(payload).hexdigest()}))
        print(f'{name} {spec["version"]}: verified and installed')


if __name__ == '__main__': install_engines()

#!/usr/bin/env python3
"""Build an unsigned, local Company HQ desktop bundle without touching account state."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'company-hq'
TAURI = UI / 'src-tauri'
VENV = ROOT / '.desktop-build-venv'
PYTHON = VENV / 'bin' / 'python'
PYINSTALLER = 'PyInstaller==6.16.0'


def run(command: list[str], *, cwd: Path = ROOT) -> None:
    print('+', ' '.join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def host_sidecar_name() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system != 'darwin' or machine not in {'arm64', 'aarch64'}:
        raise RuntimeError(f'unsupported desktop sidecar host: {platform.system()} {platform.machine()}')
    return 'company-hq-backend-aarch64-apple-darwin'


def ensure_build_venv() -> None:
    if not PYTHON.is_file():
        run([sys.executable, '-m', 'venv', str(VENV)])
    run([str(PYTHON), '-m', 'pip', 'install', '--disable-pip-version-check', PYINSTALLER])
    run([str(PYTHON), '-m', 'pip', 'install', '--disable-pip-version-check', '-r', str(ROOT / 'clawteam' / 'requirements.txt')])


def build_sidecar() -> Path:
    ensure_build_venv()
    name = host_sidecar_name()
    work = ROOT / 'build' / 'desktop-sidecar'
    dist = work / 'dist'
    target = TAURI / 'resources' / 'backend' / name
    if target.exists():
        target.unlink()
    entry = work / 'desktop_backend_entry.py'
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text("""import importlib.util
import runpy
import sys
from pathlib import Path

base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
integration = base / 'clawteam' / 'integration'
sys.path.insert(0, str(integration))
sys.path.insert(0, str(base))
spec = importlib.util.spec_from_file_location('runtime_config', integration / 'runtime_config.py')
module = importlib.util.module_from_spec(spec)
sys.modules['runtime_config'] = module
spec.loader.exec_module(module)
if len(sys.argv) == 4 and sys.argv[1] == '--project-context-mcp':
    import os
    os.environ['COMPANY_HQ_CONTEXT_PROJECT'] = sys.argv[2]
    os.environ['COMPANY_HQ_CONTEXT_TEAM'] = sys.argv[3]
    from runtime_config import clawteam_data_dir
    os.environ['CLAWTEAM_DATA_DIR'] = str(clawteam_data_dir())
    os.environ['CLAWTEAM_TRANSPORT'] = 'file'
    from project_context_mcp import main
    raise SystemExit(main())
runpy.run_path(str(integration / 'secure_board.py'), run_name='__main__')
""", encoding='utf-8')
    command = [
        str(PYTHON), '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--name', name,
        '--distpath', str(dist), '--workpath', str(work / 'work'), '--specpath', str(work / 'spec'),
        '--paths', str(ROOT), '--paths', str(ROOT / 'clawteam' / 'integration'),
        '--collect-submodules', 'clawteam',
        '--hidden-import', 'deepseek_connection', '--hidden-import', 'deepseek_runtime',
        '--hidden-import', 'openai_compatible_connection', '--hidden-import', 'openai_compatible_runtime',
        '--hidden-import', 'project_context', '--hidden-import', 'project_context_mcp',
        '--hidden-import', 'hq_api', '--hidden-import', 'company_profile', '--hidden-import', 'runtime_config',
        '--hidden-import', 'provider_connections', '--hidden-import', 'provider_setup', '--hidden-import', 'native_tasks', '--hidden-import', 'folder_picker',
        '--hidden-import', 'context_pipeline',
        '--hidden-import', 'kimi_runtime', '--hidden-import', 'zcode_runtime',
        '--hidden-import', 'native_rpc', '--hidden-import', 'native_provider_connection',
        '--hidden-import', 'chat_management', '--hidden-import', 'shared_tools',
        '--hidden-import', 'routing_policy', '--hidden-import', 'routing_service',
        '--hidden-import', 'provider_handoff', '--hidden-import', 'quota_errors',
        '--add-data', f'{ROOT / "clawteam" / "integration"}:clawteam/integration',
        '--add-data', f'{ROOT / "routing.json"}:.',
        '--add-data', f'{ROOT / "docs"}:docs',
        '--add-data', f'{ROOT / "benchmarks"}:benchmarks',
        '--add-data', f'{ROOT / "licenses"}:licenses',
        '--add-data', f'{ROOT / "roles"}:roles',
        '--add-data', f'{ROOT / "skills"}:skills',
        '--add-data', f'{ROOT / "ruflo-integration"}:ruflo-integration',
        '--add-data', f'{ROOT / "scripts" / "resolve_state_path.py"}:scripts',
        '--add-data', f'{ROOT / "agency-agents"}:agency-agents',
        '--add-data', f'{ROOT / "codebase-memory-mcp-0.10.8"}:codebase-memory-mcp-0.10.8',
        '--add-data', f'{ROOT / "build" / "providers"}:build/providers',
        '--add-data', f'{UI / "SOURCE.zip"}:company-hq',
        '--add-data', f'{ROOT / "LICENSE"}:licenses',
        '--add-data', f'{ROOT / "build" / "tools"}:build/tools',
        '--add-data', f'{UI / "dist"}:company-hq/dist',
        str(entry),
    ]
    run(command)
    built = dist / name
    if not built.is_file():
        raise RuntimeError('PyInstaller did not produce the backend sidecar')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(built, target)
    target.chmod(0o755)
    return target


def build_bundle(*, dmg: bool) -> None:
    sidecar = build_sidecar()
    if not sidecar.is_file() or not os.access(sidecar, os.X_OK):
        raise RuntimeError('backend sidecar is not executable')
    run(['npm', 'run', 'app:build'], cwd=UI)
    if dmg:
        print('Tauri target "all" requests the available unsigned bundle formats; no signing or notarization is attempted.')


def main() -> int:
    parser = argparse.ArgumentParser(description='Build an unsigned local Company HQ desktop app')
    parser.add_argument('--dmg', action='store_true', help='request Tauri all bundle targets, including DMG when available')
    parser.add_argument('--sidecar-only', action='store_true')
    args = parser.parse_args()
    run([sys.executable, 'build-source.py'], cwd=UI)
    run(['npm', 'run', 'build'], cwd=UI)
    if args.sidecar_only:
        build_sidecar()
    else:
        build_bundle(dmg=args.dmg)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

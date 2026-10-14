#!/usr/bin/env python3
"""Advisory source-boundary gate; no application imports, database or networking."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / 'docs/extensions/boundary.json'


def is_owned(path, policy):
    return path in policy['owned_files'] or any(path.startswith(prefix) for prefix in policy['owned_prefixes'])


def ignored_untracked(path, policy):
    return path in policy['preserved_untracked_files'] or any(path.startswith(prefix) for prefix in policy['preserved_untracked_prefixes'])


def exception_valid(path, policy, content):
    exception = policy.get('exceptions', {}).get(path)
    return bool(exception and content is not None and
                all(exception.get(key) for key in ('reason', 'approval_reference', 'tests', 'replacement_plan')) and
                exception.get('sha256') == hashlib.sha256(content).hexdigest())


def violations(changes, policy, reader):
    errors = []
    for status, path in changes:
        if is_owned(path, policy):
            continue
        if status == '?' and ignored_untracked(path, policy):
            continue
        if not exception_valid(path, policy, reader(path)):
            errors.append(path)
    return sorted(set(errors))


def main():
    policy = json.loads(POLICY.read_text())
    # HEAD-relative checks alone miss changes already committed. The approved
    # snapshot stays pinned until a separately reviewed boundary update.
    raw = subprocess.check_output(['git', 'diff', '--no-renames', '--name-status', '-z',
                                   policy['snapshot'], '--'], cwd=ROOT).decode().split('\0')
    changes = list(zip(raw[0:-1:2], raw[1:-1:2]))
    untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    changes += [('?', path) for path in untracked if path]

    def reader(path):
        file = ROOT / path
        if file.is_symlink() or not file.is_file():
            return None
        return file.read_bytes()

    errors = violations(changes, policy, reader)
    if errors:
        print('Boundary review required (do not auto-refresh the snapshot/allowlist):')
        print('\n'.join('  ' + path for path in errors))
        return 1
    print('PASS: changes confined to extension-owned policy paths or exact reviewed exceptions.')
    print('Legacy patches remain; this is not runtime, security or upstream-upgrade acceptance.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

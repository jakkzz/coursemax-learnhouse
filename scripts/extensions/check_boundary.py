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


def violations(changes, policy, reader, upstream_contents=None):
    errors = []
    # An upstream update must never silently replace a retained custom hook.
    protected = {entry['path'] for entry in policy.get('legacy_inventory', [])}
    protected.update(policy.get('exceptions', {}))
    upstream_contents = upstream_contents or {}
    for status, path in changes:
        if is_owned(path, policy):
            continue
        if status == '?' and ignored_untracked(path, policy):
            continue
        content = reader(path)
        if path not in protected and path in upstream_contents:
            expected = upstream_contents[path]
            if (content is not None and content == expected) or (status == 'D' and expected is None):
                continue
        if not exception_valid(path, policy, content):
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

    upstream_contents = {}
    revision = policy.get('accepted_upstream_revision')
    if revision:
        # Exact pinned upstream bytes only, not a new snapshot or path allowlist.
        if len(revision) != 40 or any(c not in '0123456789abcdef' for c in revision):
            raise ValueError('Expected a full pinned upstream commit')
        paths = subprocess.check_output(['git', 'diff', '--name-only', '--no-renames', '-z',
                                         policy['upstream_baseline'], revision, '--'], cwd=ROOT).decode().split('\0')
        for path in filter(None, paths):
            result = subprocess.run(['git', 'show', f'{revision}:{path}'], cwd=ROOT, capture_output=True)
            upstream_contents[path] = result.stdout if result.returncode == 0 else None

    errors = violations(changes, policy, reader, upstream_contents)
    if errors:
        print('Boundary review required (do not auto-refresh the snapshot/allowlist):')
        print('\n'.join('  ' + path for path in errors))
        return 1
    print('PASS: extension-owned paths, exact reviewed exceptions or unchanged pinned upstream content.')
    print('Legacy patches remain; this is not runtime, security or upstream-upgrade acceptance.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

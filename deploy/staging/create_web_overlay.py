"""Create a bounded code-only overlay from a validated web tree and retained image.

Does not run Docker, delete files, read application data or touch host caches.
Old hashed assets remain available for in-flight clients. Every desired file must
resolve to the validated bytes/link after overlay; a type conflict fails closed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def signature(path):
    if path.is_symlink():
        return ('link', str(path.readlink()))
    if path.is_file():
        return ('file', digest(path), path.stat().st_mode & 0o777)
    if path.is_dir():
        return ('dir', path.stat().st_mode & 0o777)
    return None


def create(parent, desired, output):
    if output.exists():
        raise ValueError('Output must be new')
    for name in ('server.js', '.next/BUILD_ID', '.next/server/app-paths-manifest.json'):
        if not (desired / name).is_file() or not (parent / name).is_file():
            raise ValueError('Both inputs must be complete standalone web trees')
    changed = []
    required = {}
    for path in sorted(desired.rglob('*')):
        rel = path.relative_to(desired)
        new = signature(path)
        old = signature(parent / rel)
        # Never overwrite a directory with a symlink (or vice versa).
        if old and new and old[0] != new[0]:
            raise ValueError(f'Requires full-runtime review: type conflict at {rel}')
        if new != old:
            changed.append(path)
        if new and new[0] != 'dir':
            required[str(rel)] = new
    with tarfile.open(output, 'w:gz', dereference=False) as archive:
        for path in changed:
            archive.add(path, arcname=str(path.relative_to(desired)), recursive=False)
    # Includes all desired paths, not just changed ones, for baked-tree validation.
    output.with_suffix('.manifest.json').write_text(json.dumps(required, sort_keys=True, indent=2))
    return {'changed_entries': len(changed), 'required_entries': len(required),
            'archive_bytes': output.stat().st_size,
            'new_regular_bytes': sum(p.stat().st_size for p in changed if p.is_file() and not p.is_symlink())}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--desired', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(create(args.parent, args.desired, args.output), indent=2))

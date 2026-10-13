"""Move only newly generated test dependencies under a fixed disk budget."""
import os
from pathlib import Path
import shutil
import subprocess

web = Path('/scratch/web')
cache = Path('/scratch/cache')
assert web.is_dir() and cache.is_dir()
# All of this cache was created by this disposable build; installed packages
# are hardlinks. This is not host/Docker cache pruning.
shutil.rmtree(cache)
modules = web / 'node_modules'
# Keep relocated packages inside node_modules so Tailwind/TypeScript and
# framework content detection do not scan dependencies as application source.
destination = modules / '.build-deps'
assert destination.is_dir()
packages = []
for path in modules.iterdir():
    if path.name.startswith('@'):
        packages.extend(p for p in path.iterdir() if p.is_dir() and not p.is_symlink())
    elif path.is_dir() and not path.is_symlink() and not path.name.startswith('.'):
        packages.append(path)
sized = []
for package in packages:
    size = int(subprocess.check_output(['du', '-sk', str(package)]).split()[0]) * 1024
    sized.append((size, package))
used = 0
budget = 900 * 1024**2
for size, package in sorted(sized, key=lambda pair: pair[0], reverse=True):
    if used + size > budget or size < 1024**2:
        continue
    stats = os.statvfs(destination)
    if stats.f_bavail * stats.f_frsize - size < 25.1 * 1024**3:
        continue  # Keep this package in tmpfs rather than cross the disk floor.
    target = destination / package.relative_to(modules)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(package, target, symlinks=True)
    shutil.rmtree(package)
    package.symlink_to(os.path.relpath(target, package.parent), target_is_directory=True)
    used += size
# Make copied pages reclaimable before compiling; tmpfs pages cannot be evicted.
for folder, _, files in os.walk(destination):
    for name in files:
        path = Path(folder) / name
        if path.is_symlink():
            continue
        with path.open('rb') as stream:
            os.fsync(stream.fileno())
            os.posix_fadvise(stream.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
print(f'Generated dependency disk budget: {used / 1024**2:.1f}MiB / 900MiB', flush=True)

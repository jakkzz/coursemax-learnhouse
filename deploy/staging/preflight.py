#!/usr/bin/env python3
"""Read-only resource gate. Does not pull, start, stop or prune anything."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

GIB = 1024 ** 3
MIN_FREE_GIB = 25
IMAGE_RESERVE_GIB = 2
MIN_AVAILABLE_MEMORY_GIB = 3


def blockers(free_bytes: int, available_memory: int, before_pull: bool) -> list[str]:
    required = MIN_FREE_GIB + (IMAGE_RESERVE_GIB if before_pull else 0)
    result = []
    if free_bytes < required * GIB:
        result.append(f"Need >= {required} GiB free; have {free_bytes / GIB:.2f} GiB")
    if available_memory < MIN_AVAILABLE_MEMORY_GIB * GIB:
        result.append(f"Need >= {MIN_AVAILABLE_MEMORY_GIB} GiB available memory")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before-pull", action="store_true", help="Reserve an additional 2 GiB for images")
    args = parser.parse_args()
    docker_root = subprocess.check_output(
        ["docker", "info", "--format", "{{.DockerRootDir}}"], text=True
    ).strip()
    free = shutil.disk_usage(docker_root).free
    memory_kib = next(int(line.split()[1]) for line in Path("/proc/meminfo").read_text().splitlines() if line.startswith("MemAvailable:"))
    reasons = blockers(free, memory_kib * 1024, args.before_pull)
    print(json.dumps({"docker_root": docker_root, "free_gib": round(free / GIB, 2),
                      "available_memory_gib": round(memory_kib * 1024 / GIB, 2),
                      "allowed": not reasons, "blockers": reasons}, indent=2))
    return 1 if reasons else 0


if __name__ == "__main__":
    sys.exit(main())

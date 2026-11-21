#!/usr/bin/env python3
"""Offline namespace rehearsal. Writes only a NEW scratch directory; never deploys.

This is syntax/import-reference analysis, NOT runtime/plugin/migration acceptance.
"""
import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import subprocess

BASE = '45cf5d4f78cf537064070dc8e315a64990d14966'
ROOT = Path(__file__).resolve().parents[2]


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def module(path):
    return path.removeprefix('apps/api/').removesuffix('.py').replace('/', '.')


class Relocate(ast.NodeTransformer):
    def __init__(self, mapping):
        self.mapping = mapping

    def visit_ImportFrom(self, node):
        if node.level:
            raise ValueError('Relative imports require explicit review')
        if node.module in self.mapping:
            node.module = self.mapping[node.module]
            return node
        moved, retained = [], []
        for alias in node.names:
            destination = self.mapping.get(f'{node.module}.{alias.name}')
            if destination:
                parent, name = destination.rsplit('.', 1)
                moved.append(ast.ImportFrom(module=parent, names=[ast.alias(name=name, asname=alias.asname)], level=0))
            else:
                retained.append(alias)
        if not moved:
            return node
        return ([ast.ImportFrom(module=node.module, names=retained, level=0)] if retained else []) + moved

    def visit_Import(self, node):
        # Rewriting an unaliased dotted import changes its bound root/name.
        # Refuse rather than claim an unsafe textual rewrite works.
        for alias in node.names:
            if alias.name in self.mapping:
                if not alias.asname:
                    raise ValueError(f'Unaliased dotted import requires review: {alias.name}')
                alias.name = self.mapping[alias.name]
        return node

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            for old in sorted(self.mapping, key=len, reverse=True):
                if node.value == old or node.value.startswith(old + '.'):
                    node.value = self.mapping[old] + node.value[len(old):]
                    break
        return node


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='New scratch path; existing paths refused')
    args = parser.parse_args()
    out = args.out.resolve()
    if out.is_relative_to(ROOT):
        parser.error('Scratch directory must be outside the repository')
    out.mkdir(parents=True, exist_ok=False)
    revision = git('rev-parse', 'HEAD').decode().strip()
    rows = [line.split('\t') for line in git('diff', '--name-status', '--no-renames', BASE, revision).decode().splitlines()]
    paths = [p for status, p in rows if status == 'A' and p.startswith('apps/api/src/') and p.endswith('.py') and '/tests/' not in p]
    mapping = {module(p): module(p).replace('src.', 'src.route66_ext.', 1) for p in paths}
    copies = paths + ['apps/api/src/tests/services/test_attendance_policy.py']
    native_edges = []
    stale = []
    for path in copies:
        tree = Relocate(mapping).visit(ast.parse(git('show', revision + ':' + path).decode()))
        ast.fix_missing_locations(tree)
        text = ast.unparse(tree) + '\n'
        compile(text, path, 'exec')
        destination = out / path.replace('apps/api/src/', 'apps/api/src/route66_ext/', 1)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text)
        directory = destination.parent
        while directory != out / 'apps/api':
            (directory / '__init__.py').touch()
            directory = directory.parent
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith('src.'):
                for alias in node.names:
                    qualified = node.module + '.' + alias.name
                    if node.module in mapping or qualified in mapping:
                        stale.append({'file': path, 'module': qualified})
                if not node.module.startswith('src.route66_ext.') and '/tests/' not in path:
                    native_edges.append({'file': path, 'native_module': node.module})
    report = {
        'baseline': BASE, 'source': revision,
        'scope': 'offline syntax/static import namespace rehearsal; one pure-policy test copied',
        'upstream_delta': dict(Counter(status for status, path in rows)),
        'modified_upstream_files': [path for status, path in rows if status == 'M'],
        'backend_module_mapping': mapping, 'syntax_checked_copies': len(copies),
        'remaining_native_import_edges': native_edges,
        'remaining_native_import_modules': sorted({edge['native_module'] for edge in native_edges}),
        'stale_owned_static_imports': stale,
        'not_validated': ['FastAPI startup/model discovery', 'full runtime import graph/dynamic lookups',
                          'native auth/MFA/refresh/logout', 'PostgreSQL/migrations',
                          'frontend/Next routing/bundle', 'live behavior', 'new upstream merge'],
    }
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ['source', 'upstream_delta', 'syntax_checked_copies', 'stale_owned_static_imports']}, indent=2))
    print(f'Native adapter surface: {len(report["remaining_native_import_modules"])} distinct modules, {len(native_edges)} import statements')
    if stale:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

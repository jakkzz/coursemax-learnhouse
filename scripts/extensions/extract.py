"""One-shot, reviewed namespace extraction from a fixed Git snapshot.

Offline source migration, never executed by application startup. Existing native
security/lifecycle code is not regenerated; only added feature files become shims.
"""
import argparse
import ast
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SOURCE = '76d31480'
POLICY = ROOT / 'docs/extensions/boundary.json'


def original(path):
    return subprocess.check_output(['git', 'show', SOURCE + ':' + path], cwd=ROOT).decode()


def module(path):
    return path.removeprefix('apps/api/').removesuffix('.py').replace('/', '.')


def adapter(module_name):
    return 'src.route66_ext.adapters.' + module_name.removeprefix('src.').replace('.', '_')


def rewrite(text, mapping, native=False):
    # Preserve comments, formatting, docstrings and SQL. Rewrite only AST-located
    # imports and exact module reference strings, not arbitrary business prose.
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line.encode()))
    edits = []
    for node in ast.walk(tree):
        replacement = None
        if isinstance(node, ast.ImportFrom) and node.module:
            destination = mapping.get(node.module)
            if not destination and native and node.module.startswith('src.') and not node.module.startswith('src.route66_ext.'):
                # Parent-module imports of owned modules need per-alias relocation.
                if any(node.module + '.' + a.name in mapping for a in node.names):
                    destination = None
                else:
                    destination = adapter(node.module)
            if destination:
                replacement = 'from ' + destination + ' import ' + ', '.join(a.name + (' as ' + a.asname if a.asname else '') for a in node.names)
            elif any(node.module + '.' + a.name in mapping for a in node.names):
                replacements = []
                for alias in node.names:
                    target = mapping.get(node.module + '.' + alias.name)
                    parent, name = target.rsplit('.', 1) if target else (node.module, alias.name)
                    replacements.append('from ' + parent + ' import ' + name + (' as ' + alias.asname if alias.asname else ''))
                replacement = ('\n' + ' ' * node.col_offset).join(replacements)
        elif isinstance(node, ast.Import):
            if any(a.name in mapping for a in node.names):
                if any(a.name in mapping and not a.asname for a in node.names):
                    raise ValueError('Unaliased dotted import requires individual review: ' + ast.unparse(node))
                replacement = 'import ' + ', '.join(mapping.get(a.name, a.name) + (' as ' + a.asname if a.asname else '') for a in node.names)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            for old in sorted(mapping, key=len, reverse=True):
                if node.value == old or node.value.startswith(old + '.'):
                    replacement = repr(mapping[old] + node.value[len(old):])
                    break
        if replacement is not None:
            start = offsets[node.lineno - 1] + node.col_offset
            end = offsets[node.end_lineno - 1] + node.end_col_offset
            edits.append((start, end, replacement.encode()))
    encoded = text.encode()
    for start, end, replacement in sorted(edits, reverse=True):
        encoded = encoded[:start] + replacement + encoded[end:]
    result = encoded.decode()
    compile(result, '<extracted>', 'exec')
    return result


def write(path, text):
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume', action='store_true', help='Resume an incomplete generation from the SAME immutable snapshot')
    args = parser.parse_args()
    assert not (ROOT / 'docs/extensions/extraction-map.json').exists(), 'Completed extraction cannot be replayed'
    assert args.resume or not (ROOT / 'apps/api/src/route66_ext').exists(), 'Use --resume for incomplete generation only'
    policy = json.loads(POLICY.read_text())
    entries = policy['legacy_inventory']
    py = [e['path'] for e in entries if e['status'] == 'A' and e['path'].startswith('apps/api/src/') and e['path'].endswith('.py')]
    migrations = [e['path'] for e in entries if e['status'] == 'A' and e['path'].startswith('apps/api/migrations/versions/')]
    mapping = {module(path): module(path).replace('src.', 'src.route66_ext.', 1) for path in py}
    mapping.update({module(path): 'src.route66_ext.migrations.' + Path(path).stem for path in migrations})
    native = defaultdict(set)
    for path in py:
        if '/tests/' in path:
            continue
        for node in ast.walk(ast.parse(original(path))):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith('src.') and node.module not in mapping:
                for alias in node.names:
                    if node.module + '.' + alias.name not in mapping:
                        native[node.module].add(alias.name)
    moved = {}
    for path in py + migrations:
        target = 'apps/api/' + mapping[module(path)].replace('.', '/') + '.py'
        text = rewrite(original(path), mapping, native='/tests/' not in path)
        if path.endswith('test_native_google_sessions.py'):
            text = text.replace("Path(__file__).resolve().parents[3] / 'migrations/versions/", "Path(__file__).resolve().parents[4] / 'migrations/versions/")
        text += '\n# Preserve private helper names through legacy compatibility imports.\n__all__ = [name for name in globals() if not name.startswith("__")]\n'
        write(target, text)
        current = ROOT / target
        for parent in current.parents:
            if parent == ROOT / 'apps/api/src':
                break
            init = parent / '__init__.py'
            if not init.exists():
                init.write_text('"""Owned Route66 institutional extension."""\n')
        write(path, '"""Compatibility shim; implementation owned by route66_ext. Do not add logic."""\nfrom ' + mapping[module(path)] + ' import *  # noqa: F401,F403\nfrom ' + mapping[module(path)] + ' import __all__\n')
        moved[path] = target
    for name, symbols in sorted(native.items()):
        write('apps/api/' + adapter(name).replace('.', '/') + '.py',
              '"""Reviewed native adapter: ' + name + '. Preserve native policy and transaction ownership."""\nfrom ._exports import export_native\n\n__all__ = ' + repr(sorted(symbols)) + '\nglobals().update(export_native(' + repr(name) + ', __all__))\n')
    # Own frontend additions only. Preserve framework-discovered pages as wrappers.
    web = [e['path'] for e in entries if e['status'] == 'A' and e['path'].startswith('apps/web/') and Path(e['path']).suffix in ('.tsx', '.ts', '.css')]
    web_mapping = {path: 'apps/web/extensions/route66/' + path.removeprefix('apps/web/') for path in web}
    aliases = {}
    for path, target in web_mapping.items():
        if path.endswith(('.tsx', '.ts')):
            old = path.removeprefix('apps/web/').rsplit('.', 1)[0]
            aliases['@/' + old] = '@/extensions/route66/' + old
            for prefix in ('components', 'services'):
                if old.startswith(prefix + '/'):
                    aliases['@' + old] = '@/extensions/route66/' + old
    for path, target in web_mapping.items():
        text = original(path)
        for old, new in sorted(aliases.items(), key=lambda p: len(p[0]), reverse=True):
            text = text.replace("'" + old + "'", "'" + new + "'").replace('"' + old + '"', '"' + new + '"')
        write(target, text)
        if path.endswith(('.tsx', '.ts')):
            specifier = '@/' + target.removeprefix('apps/web/').rsplit('.', 1)[0]
            wrapper = ("'use client'\n" if re.search(r"^[\s]*['\"]use client['\"]", text) else '')
            wrapper += '// Compatibility/route delegate; no feature logic here.\n'
            if re.search(r'export\s+default\b', text):
                wrapper += "export { default } from '" + specifier + "'\n"
            wrapper += "export * from '" + specifier + "'\n"
            write(path, wrapper)
            moved[path] = target
        # CSS stays as an unchanged legacy stylesheet for old consumers.
    # Record exact shims, not a broad permission to write in native trees.
    for path in moved:
        policy['exceptions'][path] = {
            'reason': 'Extension namespace extraction; exact compatibility/model/route/migration/test delegate only.',
            'approval_reference': 'Owner request: migrate to isolated pattern, rebuild/redeploy, commit/push and rehearse upstream; resumed after approved cleanup.',
            'tests': ['native auth/PostgreSQL/metadata guards', 'extension/static boundary', 'compiled EN/TH task flows and full web bundle/types'],
            'replacement_plan': 'Keep stable public/import discovery compatibility; remove only after all native callers/discovery are migrated and regression accepted.',
            'sha256': hashlib.sha256((ROOT / path).read_bytes()).hexdigest()}
    POLICY.write_text(json.dumps(policy, indent=2) + '\n')
    write('docs/extensions/extraction-map.json', json.dumps({'source': SOURCE, 'backend_modules_and_tests_migrations': len(py) + len(migrations), 'native_adapters': {name: sorted(names) for name, names in native.items()}, 'moved': moved, 'web_owned_copies': web_mapping}, indent=2) + '\n')
    print('Extracted', len(py), 'Python modules/tests,', len(migrations), 'migration implementations,', len(web), 'web files; original upstream files unchanged.')


if __name__ == '__main__':
    main()

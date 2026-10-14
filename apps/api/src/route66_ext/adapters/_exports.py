"""Explicit native facade exports, without changing native globals or policy.

Native dependencies keep their identity for FastAPI dependency overrides. Other
operations dispatch through their native module at call time (also preserving
native instrumentation/test patches). All signatures/annotations are retained.
This module does not accept client-controlled module or symbol names.
"""
from functools import wraps
from importlib import import_module
import inspect

DEPENDENCIES = frozenset({'get_db_session', 'get_current_user'})
NATIVE_VALUES = frozenset({'engine', 'Course', 'Organization', 'Role', 'RoleTypeEnum',
                           'UserAuditEvent', 'UserOrganization', 'PublicUser', 'User', 'UserRead'})


def _operation(module, name, original):
    if inspect.isasyncgenfunction(original):
        @wraps(original)
        async def generator(*args, **kwargs):
            async for value in getattr(module, name)(*args, **kwargs):
                yield value
        return generator
    if inspect.iscoroutinefunction(original):
        @wraps(original)
        async def asynchronous(*args, **kwargs):
            return await getattr(module, name)(*args, **kwargs)
        return asynchronous
    @wraps(original)
    def synchronous(*args, **kwargs):
        return getattr(module, name)(*args, **kwargs)
    return synchronous


def export_native(module_name, names):
    """Export a source-reviewed fixed allowlist; never commit or broaden rights."""
    if (not (module_name.startswith('src.') or module_name == 'config.config')
            or module_name.startswith('src.route66_ext.')):
        raise ValueError('Expected a native LearnHouse adapter target')
    module = import_module(module_name)
    exports = {}
    for name in names:
        original = getattr(module, name)
        exports[name] = (_operation(module, name, original)
                         if name not in DEPENDENCIES and name not in NATIVE_VALUES
                         else original)
    return exports

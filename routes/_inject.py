"""Dependency injection helper for routes/*.py.

Route modules receive the helpers they need from webapp.py at registration time. Plain functions are injected as thin
proxies that look the name up in webapp's live namespace on every call, so ``mock.patch.object(webapp, "_ss_user_id")``
and any later rebinding in webapp.py keep affecting the moved routes exactly as before the split.
"""
import inspect


def dependency(namespace, name):
    value = namespace[name]
    if inspect.isfunction(value):
        def proxy(*args, **kwargs):
            return namespace[name](*args, **kwargs)
        proxy.__name__ = getattr(value, "__name__", name)
        proxy.__doc__ = getattr(value, "__doc__", None)
        proxy.__wrapped__ = value
        return proxy
    return value


def resolve_wrapper(expression, namespace):
    """Turn a ``_WRAPPERS`` entry into a decorator WITHOUT ``eval``.

    Accepted forms (everything else raises ValueError at startup): ``name`` or ``name("literal", ...)`` where ``name``
    exists in ``namespace``. The entries are constants written in the route modules, never request data; this keeps it
    that way by construction instead of by convention.
    """
    import ast
    node = ast.parse(str(expression).strip(), mode="eval").body
    if isinstance(node, ast.Name):
        return namespace[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        args = [ast.literal_eval(a) for a in node.args]
        return namespace[node.func.id](*args)
    raise ValueError("unsupported wrapper expression: %r" % (expression,))

#!/usr/bin/env python3
"""Verify all imports in a Hermes hook directory work in flat-deployment mode.

Usage:
    python3 verify-hook-imports.py <hook-name>
    python3 verify-hook-imports.py hermes-alive

This script simulates the gateway hook loader's import context — it adds the
hook directory to sys.path, imports handler.py, and exercises lazy imports
inside the hook's modules. Pass = safe to restart gateway. Fail = fix imports.
"""

import sys
import os
import importlib.util
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <hook-name>", file=sys.stderr)
        sys.exit(1)

    hook_name = sys.argv[1]
    hermes_home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
    hook_dir = Path(hermes_home) / "hooks" / hook_name

    if not hook_dir.is_dir():
        print(f"ERROR: Hook directory not found: {hook_dir}", file=sys.stderr)
        sys.exit(1)

    handler_path = hook_dir / "handler.py"
    if not handler_path.exists():
        print(f"ERROR: handler.py not found in {hook_dir}", file=sys.stderr)
        sys.exit(1)

    # Simulate gateway hook loader
    hook_dir_str = str(hook_dir)
    if hook_dir_str not in sys.path:
        sys.path.insert(0, hook_dir_str)

    module_name = f"hermes_hook_{hook_name}"
    spec = importlib.util.spec_from_file_location(module_name, str(handler_path))
    if spec is None or spec.loader is None:
        print(f"ERROR: Could not create spec for {handler_path}", file=sys.stderr)
        sys.exit(1)

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        print(f"FAIL: handler.py failed to load: {e}", file=sys.stderr)
        sys.exit(1)

    handle_fn = getattr(module, "handle", None)
    if handle_fn is None:
        print(f"WARN: No 'handle' function in {handler_path}")
    else:
        print(f"✅ handler.py loaded, handle() found")

    # Test importing every .py file in the hook directory
    errors = []
    for py_file in sorted(hook_dir.glob("*.py")):
        if py_file.name == "handler.py" or py_file.name.startswith("_"):
            continue
        mod_name = py_file.stem
        try:
            __import__(mod_name)
            print(f"  ✅ {mod_name}")
        except ImportError as e:
            errors.append((mod_name, str(e)))
            print(f"  ❌ {mod_name}: {e}")

    # Additional lazy-import checks for hermes-alive pattern
    # (extend this section for your specific hook's lazy imports)
    try:
        from proactive_watcher import ProactivePlatformWatcher
        w = ProactivePlatformWatcher({}, None)

        # Mood engine
        m = w._mood()
        if m is not None:
            state = m.tick(0.5)
            print(f"  ✅ mood engine: energy={state.energy:.2f}")
        else:
            print(f"  ⚠️  mood engine returned None (may be disabled)")

        # Cooldown
        c = w._cooldown()
        if c is not None:
            print(f"  ✅ cooldown manager")
        else:
            print(f"  ⚠️  cooldown returned None (may be disabled)")

        # Mood state default
        s = w._mood_state_or_default(None)
        print(f"  ✅ mood_state_or_default: energy={s.energy:.2f}")

        # Template composer
        mt, mc = w._compose_template_message(s)
        print(f"  ✅ template composer: type={mt}, len={len(mc)}")
    except Exception as e:
        errors.append(("lazy-imports", str(e)))
        print(f"  ❌ lazy-import checks: {e}")

    if errors:
        print(f"\n❌ FAILED: {len(errors)} import error(s)")
        for mod, err in errors:
            print(f"  - {mod}: {err}")
        print("\nFix: change 'from .xxx import' → 'from xxx import' in the failing modules.")
        sys.exit(1)
    else:
        print(f"\n✅ ALL IMPORTS PASS — safe to restart gateway")


if __name__ == "__main__":
    main()
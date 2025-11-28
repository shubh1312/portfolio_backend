# portfolio/debug_helpers.py
import os
import debugpy
import sys

def wait_for_debugger(port_env="DEBUGPY_PORT", host="0.0.0.0", should_wait=True):
    """
    Idempotent debugpy helper.
    - No-op unless DEBUG_ATTACH=1 in env.
    - Attempts debugpy.listen(); if it's already called, that's fine.
    - If should_wait True, blocks until a client attaches and triggers a breakpoint.
    """
    if os.environ.get("DEBUG_ATTACH", "") != "1":
        return

    port = int(os.environ.get(port_env, 5678))

    # Try to call listen() once, but ignore the RuntimeError if already listened.
    try:
        debugpy.listen((host, port))
        print(f"[debug_helpers] debugpy listening on {host}:{port} (pid {os.getpid()})", file=sys.stderr)
    except RuntimeError:
        # listen() already called in this process — that's okay.
        print("[debug_helpers] debugpy.listen() already called earlier in this process", file=sys.stderr)

    # Optionally wait for client and break (blocking). If you do this inside tasks,
    # set should_wait=False to avoid blocking subsequent code until a debugger attaches.
    if should_wait:
        try:
            debugpy.wait_for_client()
            # This will cause IDE to stop here once attached.
            debugpy.breakpoint()
        except Exception as exc:
            print(f"[debug_helpers] wait_for_client/breakpoint error: {exc}", file=sys.stderr)

"""Allow ``python -m mta`` (and ``py -m mta`` on Windows) as a PATH-independent way to run
the CLI — the fallback `mta doctor` points novices to when the console script isn't on PATH.
"""
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())

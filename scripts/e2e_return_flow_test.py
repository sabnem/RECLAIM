"""Compatibility entry point: run the return workflow in Django's test database."""

import subprocess
import sys
from pathlib import Path


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    raise SystemExit(subprocess.call([
        sys.executable,
        str(root / "manage.py"),
        "test",
        "FindIt.tests.PortalTests.test_claim_approval_otp_return_and_archives",
        "--settings=lost_and_found.test_settings",
        "--noinput",
    ], cwd=root))

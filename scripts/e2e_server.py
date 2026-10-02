"""Run the API against a temporary migrated database for browser tests."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

with tempfile.TemporaryDirectory(prefix="faculty-e2e-") as directory:
    os.environ["DATABASE_URL"] = f"sqlite:///{Path(directory) / 'test.db'}"
    os.environ["EVIDENCE_ROOT"] = str(Path(directory) / "evidence")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    subprocess.run([sys.executable, "-m", "backend.seed"], check=True)
    # Run in this process so Playwright can stop the test API without orphaning
    # a child server that continues holding port 8011 and the temporary database.
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8011)

"""Run the API against a temporary migrated database for browser tests."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# The desktop test sandbox may not permit SQLite files in the system temporary
# directory. Keep each short-lived e2e database under the writable project
# directory instead, while still assigning a fresh directory to every run.
E2E_TEMP_ROOT = ROOT / ".test-tmp-e2e"
E2E_TEMP_ROOT.mkdir(exist_ok=True)

with tempfile.TemporaryDirectory(prefix="faculty-e2e-", dir=E2E_TEMP_ROOT) as directory:
    os.environ["DATABASE_URL"] = f"sqlite:///{Path(directory) / 'test.db'}"
    os.environ["EVIDENCE_ROOT"] = str(Path(directory) / "evidence")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    subprocess.run([sys.executable, "-m", "backend.seed"], check=True)
    # Run in this process so Playwright can stop the test API without orphaning
    # a child server that continues holding port 8011 and the temporary database.
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8011)

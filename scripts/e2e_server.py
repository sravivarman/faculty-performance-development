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
    test_root = Path(directory).resolve()
    database_path = (test_root / "test.db").resolve()
    evidence_root = (test_root / "evidence").resolve()
    production_database = (ROOT / "data" / "faculty.db").resolve()
    production_evidence = (ROOT / "storage" / "evidence").resolve()
    # Destructive browser tests must fail closed if future configuration changes
    # would point either store at the development/production location.
    if database_path == production_database or evidence_root == production_evidence:
        raise RuntimeError("Refusing to run browser tests against a live database or evidence directory")
    if not database_path.is_relative_to(E2E_TEMP_ROOT.resolve()) or not evidence_root.is_relative_to(E2E_TEMP_ROOT.resolve()):
        raise RuntimeError("Browser test storage must remain below .test-tmp-e2e")
    os.environ["DATABASE_URL"] = f"sqlite:///{database_path}"
    os.environ["EVIDENCE_ROOT"] = str(evidence_root)
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    subprocess.run([sys.executable, "-m", "backend.seed"], check=True)
    # Run in this process so Playwright can stop the test API without orphaning
    # a child server that continues holding port 8011 and the temporary database.
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8011)

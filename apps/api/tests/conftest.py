import os
import tempfile

# Configure the app for tests *before* anything imports the settings module
_TMP = tempfile.mkdtemp(prefix="testscope-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP, 'test.db')}"
os.environ["WORKSPACE_DIR"] = os.path.join(_TMP, "workspace")
os.environ["USE_FAKE_LLM"] = "true"
os.environ["TESTSCOPE_SKIP_MIGRATIONS"] = "true"
os.environ["JWT_SECRET"] = "test-secret"

import pytest  # noqa: E402

from apps.api.app.core.database import Base, engine  # noqa: E402
import apps.api.app.models  # noqa: E402,F401
from apps.api.app.services import run_worker  # noqa: E402

run_worker.RUN_INLINE = True


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

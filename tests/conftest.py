import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.database.session import reset_engine


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + db_path.as_posix())
    monkeypatch.setenv("AUTO_CREATE_TABLES", "true")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("QM_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("ENVIRONMENT", "test")
    get_settings.cache_clear()
    reset_engine()
    from app.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    reset_engine()
    get_settings.cache_clear()

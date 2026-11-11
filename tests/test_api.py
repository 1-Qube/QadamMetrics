def test_health_and_methodology(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["database"] == "up"
    assert health.json()["ai"]["required"] is False
    docs = client.get("/openapi.json")
    assert docs.status_code == 200
    paths = docs.json()["paths"]
    for path in (
        "/api/datasets/import",
        "/api/analytics/topics",
        "/api/knowledge-graph",
        "/api/optimization/scenarios",
        "/api/causal-analysis",
        "/api/recommendations/generate",
        "/api/reports/generate",
        "/api/ai/explain",
    ):
        assert path in paths


def test_import_validation_and_isolation(client):
    bad = client.post(
        "/api/datasets/import",
        data={"name": "bad"},
        files={"responses": ("responses.csv", b"student_id\nS1\n", "text/csv")},
    )
    assert bad.status_code == 200
    body = bad.json()["data"]
    assert body["status"] == "failed"
    assert body["rows_accepted"] == 0

    good_a = """student_id,school_id,grade_level,subject_id,topic_id,topic_name,assessment_id,question_id,is_correct,assessment_date
S1,SCH_A,8,MATH,T06,Factoring,A1,Q1,false,2024-10-15
""".encode()
    good_b = good_a.replace(b"SCH_A", b"SCH_B").replace(b"S1", b"S9")
    first = client.post("/api/datasets/import", data={"name": "A"}, files={"responses": ("responses.csv", good_a, "text/csv")})
    second = client.post("/api/datasets/import", data={"name": "B"}, files={"responses": ("responses.csv", good_b, "text/csv")})
    id_a = first.json()["data"]["dataset_id"]
    id_b = second.json()["data"]["dataset_id"]
    topics_a = client.get("/api/analytics/topics", params={"dataset_id": id_a, "min_students": 1}).json()["data"]
    assert topics_a["overview"]["students"] == 1
    topics_b = client.get("/api/analytics/topics", params={"dataset_id": id_b, "min_students": 1}).json()["data"]
    assert topics_b["overview"]["schools"] == 1
    assert "SCH_A" not in str(topics_b["by_school"])


def test_demo_pipeline_endpoints(client):
    loaded = client.post("/api/datasets/demo", params={"students_per_school_grade": 8})
    assert loaded.status_code == 200
    dataset_id = loaded.json()["data"]["dataset_id"]
    assert loaded.json()["data"]["evidence_class"] == "synthetic"
    assert loaded.json()["data"]["rows_accepted"] > 100

    graph = client.get("/api/knowledge-graph", params={"dataset_id": dataset_id, "min_students": 20})
    assert graph.status_code == 200
    assert graph.json()["data"]["edge_count"] > 0
    assert graph.json()["data"]["verified_edge_count"] > 0

    optimization = client.post("/api/optimization/scenarios", json={"dataset_id": dataset_id, "total_hours": 100})
    assert optimization.status_code == 200
    assert optimization.json()["data"]["assumptions"]["learning_response_estimated_from_data"] is False

    impossible = client.post(
        "/api/optimization/scenarios",
        json={
            "dataset_id": dataset_id,
            "total_hours": 5,
            "topics": [
                {"topic_id": "T06", "hours": 8, "min_hours": 6, "max_hours": 10},
                {"topic_id": "T12", "hours": 8, "min_hours": 6, "max_hours": 10},
            ],
        },
    )
    assert impossible.status_code == 422

    causal = client.post("/api/causal-analysis", json={"dataset_id": dataset_id, "n_bootstrap": 15})
    assert causal.status_code == 200
    assert causal.json()["data"]["causal_conclusion"] == "not_claimed"

    ai = client.post("/api/ai/explain", json={"dataset_id": dataset_id, "task": "diagnostics", "question": "Why is factoring low?"})
    assert ai.status_code == 200
    assert ai.json()["data"]["used_fallback"] is True

    missing = client.post("/api/ai/explain", json={"task": "question", "facts": {}, "question": "What is the secret score?"})
    assert "No analytical facts" in missing.json()["data"]["text"] or "Nothing further" in missing.json()["data"]["text"]

    report = client.post("/api/reports/generate", json={"dataset_id": dataset_id})
    assert report.status_code == 200
    report_id = report.json()["data"]["report_id"]
    download = client.get(f"/api/reports/{report_id}/download", params={"format": "json"})
    assert download.status_code == 200
    assert b"student_id" not in download.content
    pdf = client.get(f"/api/reports/{report_id}/download", params={"format": "pdf"})
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")


def test_api_key_required_when_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + (tmp_path / "k.db").as_posix())
    monkeypatch.setenv("AUTO_CREATE_TABLES", "true")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("QM_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    from app.core.config import get_settings
    from app.database.session import reset_engine

    get_settings.cache_clear()
    reset_engine()
    from app.main import create_app
    from fastapi.testclient import TestClient

    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/datasets").status_code == 401
        assert client.get("/api/datasets", headers={"X-API-Key": "test-key"}).status_code == 200
    reset_engine()
    get_settings.cache_clear()

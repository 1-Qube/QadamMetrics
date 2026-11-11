def test_private_upload_is_hidden_from_another_owner(client):
    csv = (
        "student_id,school_id,grade_level,subject_id,topic_id,assessment_id,question_id,is_correct\n"
        "s1,sch1,8,MATH,T01,A1,Q1,1\n"
    )
    created = client.post(
        "/api/datasets/import",
        data={"name": "Private"},
        files={"responses": ("responses.csv", csv, "text/csv")},
        headers={"X-Owner-Token": "owner-a"},
    )
    assert created.status_code == 200, created.text
    dataset_id = created.json()["data"]["dataset_id"]

    hidden = client.get("/api/datasets", headers={"X-Owner-Token": "owner-b"})
    assert dataset_id not in {row["id"] for row in hidden.json()["data"]}
    assert client.get(f"/api/analytics/topics?dataset_id={dataset_id}", headers={"X-Owner-Token": "owner-b"}).status_code == 404

    visible = client.get("/api/datasets", headers={"X-Owner-Token": "owner-a"})
    assert dataset_id in {row["id"] for row in visible.json()["data"]}


def test_demo_dataset_is_public(client):
    loaded = client.post("/api/datasets/demo", params={"students_per_school_grade": 5})
    assert loaded.status_code == 200, loaded.text
    dataset_id = loaded.json()["data"]["dataset_id"]
    listed = client.get("/api/datasets", headers={"X-Owner-Token": "someone-else"})
    assert dataset_id in {row["id"] for row in listed.json()["data"]}

from app.data_ingestion.csv_loader import parse_allocations_csv, parse_prerequisites_csv, parse_responses_csv


def test_accepts_documented_csv():
    payload = """student_id,school_id,grade_level,subject_id,topic_id,assessment_id,question_id,is_correct,assessment_date
S1,SCH,8,MATH,T06,A1,Q1,true,2024-10-15
S1,SCH,8,MATH,T06,A1,Q2,false,2024-10-15
""".encode()
    result = parse_responses_csv(payload)
    assert result.rows_accepted == 2
    assert result.rows_rejected == 0
    assert result.frame.iloc[0]["credit"] == 1


def test_missing_columns_are_reported_not_discarded_silently():
    result = parse_responses_csv(b"student_id,score\nS1,1\n")
    assert result.rows_accepted == 0
    assert result.issues[0].code == "MISSING_COLUMNS"


def test_invalid_and_duplicate_rows_are_kept_as_issues():
    payload = """student_id,school_id,grade_level,subject_id,topic_id,assessment_id,question_id,is_correct
S1,SCH,8,MATH,T06,A1,Q1,maybe
S2,SCH,8,MATH,T06,A1,Q1,true
S2,SCH,8,MATH,T06,A1,Q1,false
S3,SCH,99,MATH,T06,A1,Q1,true
""".encode()
    result = parse_responses_csv(payload)
    codes = [issue.code for issue in result.issues]
    assert "INVALID_BOOLEAN" in codes
    assert "DUPLICATE_RESPONSE" in codes
    assert "INVALID_GRADE" in codes
    assert result.rows_accepted == 1
    assert result.rows_duplicate == 1


def test_empty_file():
    result = parse_responses_csv(b"")
    assert result.issues[0].code == "EMPTY_FILE"


def test_partial_credit_and_score_ratio():
    payload = """student_id,school_id,grade_level,subject_id,topic_id,assessment_id,question_id,score,max_score
S1,SCH,8,MATH,T06,A1,Q1,1,2
""".encode()
    result = parse_responses_csv(payload)
    assert result.rows_accepted == 1
    assert result.frame.iloc[0]["credit"] == 0.5
    assert any(issue.code == "PARTIAL_CREDIT" for issue in result.issues)


def test_prerequisite_and_allocation_duplicates():
    prereq = parse_prerequisites_csv(b"prerequisite_topic_id,dependent_topic_id\nT04,T06\nT04,T06\nT06,T06\n")
    assert prereq.rows_accepted == 1
    assert prereq.rows_duplicate == 1
    alloc = parse_allocations_csv(b"topic_id,hours\nT06,8\nT06,4\nT05,-1\n")
    assert alloc.rows_accepted == 1
    assert alloc.rows_duplicate == 1

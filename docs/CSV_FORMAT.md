# CSV format

Uploads are UTF-8, UTF-8 with BOM, or Windows-1251. The parser records which encoding worked.

## responses.csv

Required columns:

| Column | Meaning |
| --- | --- |
| student_id | Pseudonymous learner id. Do not upload legal names if you can avoid it. |
| school_id | School code |
| grade_level | Integer 1–13 |
| subject_id | Subject code, for example `MATH` |
| topic_id | Stable curriculum topic code |
| assessment_id | Assessment code |
| question_id | Item code |
| is_correct or score | Outcome. `is_correct` accepts true/false, 1/0, correct/incorrect. If omitted, `score` and `max_score` are required. |

Optional columns: `school_name`, `subject_name`, `topic_name`, `assessment_name`, `assessment_date` (`YYYY-MM-DD`, `YYYY/MM/DD`, or `DD.MM.YYYY`), `material_id`, `answer_text`, `max_score`.

Unknown columns are stored on the response as extra fields. They are not silently deleted. Numeric extras can later be listed as candidate confounders; being stored does not mean they were used.

A row is rejected, and an issue is stored, when a required field is empty, a grade or date or boolean is invalid, the outcome cannot be derived, or the row duplicates an earlier `(student_id, assessment_id, question_id, assessment_date)`. The first duplicate is kept. Rejected rows are not dropped without a message.

Partial credit (`score/max_score` between 0 and 1) is stored as credit and flagged `PARTIAL_CREDIT`. Topic accuracy is the unweighted mean of student-level mean credit.

Cells that start with `=`, `+`, `-`, or `@` are stored as text and flagged. Report exports prefix those characters so a spreadsheet does not evaluate them.

## topics.csv

`topic_id`, optional `topic_name`, `subject_id`, `grade_level`, `description`.

## prerequisites.csv

`prerequisite_topic_id`, `dependent_topic_id`, optional `relation_status` (`verified` or `inferred`), `source`, `notes`, `confidence`.

`verified` means a person asserted the link. It does not mean an experiment proved it.

## allocations.csv

`topic_id`, `hours`, optional `min_hours`, `max_hours`, `importance_weight`, `subject_id`.

Hours are teaching-hour allocations for the flight simulator. They are not inferred from assessment scores.

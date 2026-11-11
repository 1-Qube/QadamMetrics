# Methodology

Version `2026.1`. The same text is served by `GET /api/methodology` from `app/analytics/methodology.py`. If this file and that module disagree, the module is the source of truth.

## Diagnostics

Topic accuracy is the unweighted mean of student-level mean item credit. Each assessed student counts once. Item credit is 1 or 0 when `is_correct` is supplied. Otherwise credit is `score/max_score`, clipped to [0, 1].

A Student-t 95% confidence interval is computed for that mean. It assumes student-level means are independent. It does not adjust for school clustering, so it can still be too narrow.

Labels require at least `min_students` (default 30):

- `insufficient_data` below that count, or `not_assessed` if the catalog has the topic and the file does not.
- `weak` if the 95% CI upper bound is below 0.60.
- `strong` if the 95% CI lower bound is at least 0.75.
- `inconclusive` otherwise.

A topic at 30% with 3 students is not labeled weak. A topic at 30% with 200 students is labeled weak when the interval agrees. With a large sample, a mean near 0.55 can be labeled weak because the interval is narrow. That is a threshold choice, not a validated standard of failure.

The inconsistent-school flag needs two schools with at least 20 students and a range of school means of at least 0.25. It is a disparity flag, not a school effect.

The topic difficulty index is `1 - accuracy`. It is descriptive. It is not an IRT parameter. A shrunk credit toward 0.5 with prior strength 10 is a display aid. Recommendations do not use it.

The item-level Wilson interval treats items as independent and is supplementary. Classification does not use it.

## Knowledge graph

Edges point from prerequisite to dependent topic. `verified` means a person supplied the edge. `inferred` means a co-failure candidate: phi / Matthews correlation of student-level failure at least 0.25, at least 40 overlapping students, and the proposed prerequisite is not from a later grade. Candidates are not saved unless a methodologist posts them.

Importance is 1 plus the number of descendants. Downstream risk multiplies descriptive weakness by descendant count. An upstream gap hypothesis lists verified prerequisites that are themselves weak. It is not a demonstrated cause. Cycles are reported as data errors.

## Textbooks

Chapter, definition, example, exercise, and question lines are detected with keywords. Cognitive demand uses a Bloom-like keyword map (`rule_based_bloom_keywords_v1`). Highest matching demand wins. This is not expert coding and has no reliability estimate.

Structural comparison is not an effectiveness ranking. Linked outcome means are reported as associations in a separate section.

## Optimization

SciPy solves two hypothetical programs. Neither predicts test scores.

1. Linear priority program, `linprog` / HiGHS. Maximize `sum w_i h_i` with `w_i = importance * weakness * (1 + descendants / max_descendants)`. Weakness is `max(0, target_accuracy - accuracy)` only for classifiable topics. Linear objectives hit bounds. That corner behavior is disclosed.
2. Diminishing-returns program, SLSQP. Maximize `sum importance * weakness * (1 - exp(-beta * h / r)) * (1 + tau * upstream_need)`, where `r` is `max(current hours, 1)`. Default `beta` is 0.15 and `tau` is 0.25. These are assumptions.

Constraints are a fixed total and per-topic bounds, plus an optional cap on change from the current plan. Infeasible bounds produce no plan. Both solvers start from the current allocation and are deterministic.

Objective deltas are not percentage-point learning gains. If the two scenarios move a topic in opposite directions by at least 0.5 hours, the comparison is marked objective-sensitive.

## Causal contrast

The implementation is internal IPW and OLS (`internal_ipw_ols_v1`). DoWhy and EconML are detected if installed and are not required. A causal library would not make the assumptions true.

The workflow defines a binary material contrast and a student mean outcome. When two dates exist, the latest date is the outcome and the earliest is a prior score. Candidate confounders are prior score, grade, school, and numeric extra fields present for at least 80% of students. Candidate does not mean sufficient.

If treatment does not vary inside any school, textbook and school are not separable. The result stays an association. Arms under 30 students stay an association. Propensity scores come from L2 logistic regression. Adjusted estimates are attempted only with common support. Weights are stabilized; a trimmed-weight estimate is the robustness check. Balance uses standardized mean differences, with 0.25 as a warning convention, not proof of exchangeability. A percentile bootstrap interval is reported. Sign disagreement between OLS and IPW marks the result fragile.

`causal_conclusion` is never claimed.

## Recommendations and AI

Rules copy numbers from the engines. Observations and hypotheses are separate fields. Intervention confidence is `not_estimated`.

Gemini receives the JSON and is told not to add numbers. Narratives with numbers absent from the facts are discarded. Without an API key, a deterministic template formats the same JSON. Analytics do not call the model.

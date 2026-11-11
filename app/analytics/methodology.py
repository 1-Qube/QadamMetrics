"""Canonical methodology text.

These strings are returned by the API and covered by tests. They describe
what the software computes. They do not claim that custom indexes are
validated psychometric instruments or that optimization predicts learning.
"""

METHODOLOGY_VERSION = "2026.1"

MIN_STUDENTS_DEFAULT = 30
WEAK_CI_UPPER = 0.60
STRONG_CI_LOWER = 0.75
INCONSISTENT_RANGE = 0.25
INCONSISTENT_SCHOOL_MIN_N = 20
CONFIDENCE_LEVEL = 0.95

DIAGNOSTICS = """
Topic accuracy is the unweighted mean of student-level mean item credit.
Each assessed student counts once. Item credit is 1 or 0 when is_correct is
supplied. Otherwise credit is score/max_score, clipped to [0, 1].

A Student-t 95% confidence interval is computed for the mean of student-level
credits. The interval assumes student-level means are independent. It does not
account for school clustering, so it can still be too narrow.

Classification uses the student as the unit and refuses labels when the sample
is small:
- insufficient_data if fewer than min_students (default 30) have a topic score,
  or if the topic was not assessed.
- weak if n >= min_students and the 95% CI upper bound is below 0.60.
- strong if n >= min_students and the 95% CI lower bound is at least 0.75.
- inconclusive otherwise.

A topic with 30% accuracy and 3 students is therefore not labeled weak.
A topic with 30% accuracy and 200 students is labeled weak when the CI agrees.

The inconsistent flag is separate. It requires overall n >= min_students, at
least two schools with at least 20 assessed students each, and a range of
school mean credits of at least 0.25. It is a descriptive disparity flag, not
a causal school effect.

The topic difficulty index (TDI) is 1 minus mean student credit. It is a
descriptive complement of accuracy, not an item-response-theory parameter.
A supplementary shrunk credit pulls the item-level mean toward 0.5 with a
fixed prior strength of 10. Shrinkage is a display aid for small samples.
Recommendations do not use the shrunk value.

Wilson intervals are also reported for the binary indicator credit >= 0.5 at
item level. Item-level intervals treat items as independent and are usually
anti-conservative. They are supplementary. Classification uses the student-level
t interval plus the minimum sample size.

No custom index in this module is presented as a scientifically validated
measure of latent ability.
""".strip()

KNOWLEDGE_GRAPH = """
A node is a curriculum topic. A directed edge prerequisite -> dependent means
the prerequisite is intended to be learned before the dependent topic.

Edge status is either verified or inferred.
- verified: supplied by a curriculum file or entered by a methodologist.
  Verified means a human asserted the relationship. It does not mean the
  relationship has been experimentally proven.
- inferred: a candidate computed from co-failure, not automatically treated
  as curriculum truth. Inference uses the phi / Matthews correlation of
  student-level failure (student mean credit < 0.5) between two topics,
  requires at least 40 students assessed on both, a shared-student count,
  and an earlier-or-equal grade for the proposed prerequisite. Candidates
  are returned for review. They are not silent facts.

Dependency depth is the longest path from a root. Importance is 1 plus the
number of descendants. Downstream risk is descriptive weakness multiplied by
descendant count. Upstream gap flags list verified prerequisites that are
themselves classified weak. These are hypotheses about where to look, not
demonstrated causes of later failure.

Cycles are reported as data errors. The graph remains available, but path
metrics that require an acyclic graph are omitted for nodes inside a cycle.
""".strip()

TEXTBOOKS = """
Textbook structure is extracted with deterministic rules: headings matching
chapter/unit patterns, and paragraphs or lines labeled as definitions,
explanations, examples, exercises, or questions. Mathematical expressions are
detected with surface patterns (powers, equations, simple factored products).
This is not a full mathematical parser.

Cognitive demand uses a keyword map onto a Bloom-like scale
(remember, understand, apply, analyze, evaluate, create). The first highest
matching verb wins. This is a rule-based heuristic, not expert coding, and
no inter-rater reliability is claimed. Short items are often misclassified.

Structural comparison covers topic mention, explanation-proxy counts,
exercise counts, exercise-stem variety, cognitive-keyword mix, and overlap
with the supplied curriculum and assessment topic lists. A structurally richer
textbook is not evidence that students learn more from it.

When student outcomes are linked by material id, the module reports an
unadjusted outcome difference in a separate section and states that it is an
association. Fair comparison requires the causal-analysis module and still
does not produce a causal conclusion.
""".strip()

OPTIMIZATION = """
The curriculum flight simulator reallocates a fixed hour budget. It does not
predict future test scores.

Two explicit objectives are solved with SciPy.

1. Linear priority program (scipy.optimize.linprog, HiGHS).
   Maximize sum_i w_i h_i, where
   w_i = importance_i * weakness_i * (1 + descendants_i / max_descendants).
   weakness_i = max(0, target_accuracy - accuracy_i) if the topic is
   classifiable, else 0. Topics with insufficient data do not pull hours.
   A linear objective has corner solutions: hours move to the highest weight
   until a bound is hit. That behavior is reported, not hidden.

2. Hypothetical diminishing-returns program (SLSQP).
   Maximize sum_i importance_i * weakness_i * (1 - exp(-beta * h_i / r_i))
   * (1 + tau * upstream_need_i).
   r_i is max(current hours, 1). beta and tau are assumptions, default 0.15
   and 0.25. upstream_need_i is 1 when a verified prerequisite is weak, else 0.
   The exponential learning curve is hypothetical. It is not estimated from
   this dataset unless a user replaces it with their own parameters and even
   then the software labels the scenario hypothetical.

Constraints: sum h_i = total hours, and min_i <= h_i <= max_i. Optional
max_change_hours limits movement from the current plan. If the bounds cannot
contain the total, the scenario is infeasible and no fake plan is returned.

Results are reproducible for the same inputs because both solvers are
deterministic from the current allocation. Objective deltas are in objective
units, not percentage-point learning gains. The methodologist remains the
decision maker.
""".strip()

CAUSAL = """
The causal module distinguishes correlation, association, an estimated
contrast under explicit assumptions, and a causal conclusion.

It never emits a causal conclusion. Unmeasured confounding, interference,
and outcome measurement differences cannot be ruled out from a CSV.

Workflow:
1. Define a binary treatment (material A versus material B) and a numeric
   outcome (student mean credit). Default outcome period is the latest
   assessment date when dates exist; earlier dates can form a prior score.
2. List observed candidate confounders: prior score, grade, school, and
   numeric extra fields present for at least 80% of students. Candidate does
   not mean the set is sufficient.
3. Report missingness, arm sizes, and treatment-group overlap.
4. If treatment does not vary, or every school has only one treatment and
   school is the grouping factor, the contrast is not identified separately
   from school. The module stops at a descriptive association and says so.
5. Unadjusted difference in means is an association.
6. OLS adjustment and inverse-probability weighting are computed only when
   both arms have at least 30 students and propensity scores overlap on a
   common-support interval. Propensity scores come from L2-logistic regression.
   Weights are stabilized and trimmed at the 1st and 99th percentiles as a
   robustness check. A percentile bootstrap interval is reported.
7. Covariate balance is summarized with standardized mean differences before
   and after weighting. SMD above 0.25 after weighting is a warning. Passing
   a threshold is not proof of exchangeability.
8. If adjusted estimates disagree in sign, the result is marked fragile.

Libraries such as DoWhy and EconML are not required. The estimator is an
internal, inspectable IPW/OLS implementation so the assumptions stay in this
codebase rather than in an unconfigured causal graph. claim_level is one of
not_comparable, association_only, or estimated_effect_under_untestable_assumptions.
""".strip()

RECOMMENDATIONS = """
Recommendations are rule-based combinations of the analytical modules.
A confirmed observation is only a descriptive finding that passed a sample-size
gate. A possible explanation is labeled as a hypothesis. A recommended action
is a review step for a methodologist. Intervention effects are not estimated,
so intervention confidence is never high and is reported as not estimated.

Rules do not fire on topics with insufficient data except to ask for more
assessment coverage. Optimizer suggestions are included only as hypothetical
hour explorations, and only when the nonlinear scenario is feasible. If the
linear and nonlinear scenarios move a topic in opposite directions, the
recommendation says the result is sensitive to the objective.
""".strip()

AI = """
The copilot receives structured JSON produced by the analytical engines.
The prompt forbids new statistics, invented student results, textbook
effectiveness claims, and causal upgrades of associations. When Gemini is not
configured, times out, or returns numbers that are not present in the supplied
facts (or their percentage-point equivalents), the narrative is replaced by a
deterministic template that only formats engine output. Core analytics do not
depend on the model.
""".strip()


def methodology_catalog() -> dict[str, str]:
    return {
        "version": METHODOLOGY_VERSION,
        "diagnostics": DIAGNOSTICS,
        "knowledge_graph": KNOWLEDGE_GRAPH,
        "textbooks": TEXTBOOKS,
        "optimization": OPTIMIZATION,
        "causal_analysis": CAUSAL,
        "recommendations": RECOMMENDATIONS,
        "ai": AI,
    }

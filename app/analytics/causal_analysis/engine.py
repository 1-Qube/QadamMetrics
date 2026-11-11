"""Association and cautious effect estimation. Never a causal conclusion."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, LogisticRegression

from app.analytics.methodology import CAUSAL, METHODOLOGY_VERSION

MIN_ARM = 30
OVERLAP_LOW = 0.05
OVERLAP_HIGH = 0.95
SMD_WARN = 0.25


def analyze_textbook_contrast(
    students: pd.DataFrame,
    *,
    treatment_col: str = "treatment",
    outcome_col: str = "outcome",
    confounder_cols: list[str] | None = None,
    n_bootstrap: int = 200,
    seed: int = 7,
) -> dict:
    base = {
        "methodology_version": METHODOLOGY_VERSION,
        "implementation": "internal_ipw_ols_v1",
        "libraries": {"dowhy": _available("dowhy"), "econml": _available("econml")},
        "causal_conclusion": "not_claimed",
        "limitations": [CAUSAL],
    }
    if students is None or students.empty:
        return {**base, "status": "insufficient_data", "claim_level": "not_comparable", "message": "No student rows."}

    frame = students.copy()
    if treatment_col not in frame.columns or outcome_col not in frame.columns:
        return {
            **base,
            "status": "insufficient_data",
            "claim_level": "not_comparable",
            "message": "Treatment and outcome columns are required.",
        }
    frame = frame.dropna(subset=[treatment_col, outcome_col])
    treatments = sorted(frame[treatment_col].dropna().unique().tolist())
    if len(treatments) < 2:
        return {
            **base,
            "status": "insufficient_data",
            "claim_level": "not_comparable",
            "message": "Treatment does not vary. A comparison needs two materials.",
            "treatments": [str(value) for value in treatments],
        }
    if len(treatments) > 2:
        return {
            **base,
            "status": "needs_contrast",
            "claim_level": "not_comparable",
            "message": "Specify a binary contrast. More than two materials were found.",
            "treatments": [str(value) for value in treatments],
        }

    treated_label, control_label = str(treatments[1]), str(treatments[0])
    # Prefer a stable order: caller may pass codes. Alphabetical is reproducible.
    treated_label, control_label = sorted(str(value) for value in treatments)[1], sorted(str(value) for value in treatments)[0]
    frame = frame[frame[treatment_col].astype(str).isin([treated_label, control_label])].copy()
    frame["t"] = (frame[treatment_col].astype(str) == treated_label).astype(int)
    frame["y"] = pd.to_numeric(frame[outcome_col], errors="coerce")
    frame = frame.dropna(subset=["y"])

    arm_n = frame["t"].value_counts().to_dict()
    quality = {
        "n_students": int(len(frame)),
        "n_treated": int(arm_n.get(1, 0)),
        "n_control": int(arm_n.get(0, 0)),
        "treated_label": treated_label,
        "control_label": control_label,
        "outcome_missing_dropped": int(students[outcome_col].isna().sum()) if outcome_col in students.columns else 0,
    }
    confounders = list(confounder_cols or [])
    available = [column for column in confounders if column in frame.columns]
    missing_confounders = [column for column in confounders if column not in frame.columns]
    school_nested = _school_nested(frame)

    unadjusted = float(frame.loc[frame["t"] == 1, "y"].mean() - frame.loc[frame["t"] == 0, "y"].mean())
    correlation = float(np.corrcoef(frame["t"], frame["y"])[0, 1]) if frame["y"].nunique() > 1 else 0.0
    association = {
        "claim_level": "association",
        "unadjusted_difference": round(unadjusted, 4),
        "correlation": round(correlation, 4),
        "definition": f"Mean outcome for {treated_label} minus mean outcome for {control_label}.",
    }

    if school_nested:
        return {
            **base,
            "status": "not_identified",
            "claim_level": "association_only",
            "message": (
                "Treatment does not vary inside schools, so textbook and school are perfectly confounded. "
                "No adjustment can separate them from this table."
            ),
            "quality": quality,
            "association": association,
            "confounders_used": [],
            "confounders_unavailable": missing_confounders + ["within-school treatment variation"],
            "estimated_effect": None,
        }

    if min(quality["n_treated"], quality["n_control"]) < MIN_ARM:
        return {
            **base,
            "status": "association_only",
            "claim_level": "association_only",
            "message": f"Each arm needs at least {MIN_ARM} students before an adjusted estimate is attempted.",
            "quality": quality,
            "association": association,
            "confounders_used": available,
            "estimated_effect": None,
        }

    design = _design_matrix(frame, available)
    if design.shape[1] == 0:
        return {
            **base,
            "status": "association_only",
            "claim_level": "association_only",
            "message": "No usable confounders were available. Only the unadjusted association is reported.",
            "quality": quality,
            "association": association,
            "confounders_used": [],
            "estimated_effect": None,
        }

    overlap = _propensity(design, frame["t"].to_numpy())
    if not overlap["ok"]:
        return {
            **base,
            "status": "poor_overlap",
            "claim_level": "association_only",
            "message": overlap["message"],
            "quality": quality,
            "association": association,
            "overlap": overlap,
            "confounders_used": design.columns.tolist(),
            "estimated_effect": None,
        }

    ols = _ols(frame["y"].to_numpy(), frame["t"].to_numpy(), design)
    ipw = _ipw(frame["y"].to_numpy(), frame["t"].to_numpy(), overlap["ps"])
    trimmed = _ipw(frame["y"].to_numpy(), frame["t"].to_numpy(), overlap["ps"], trim=True)
    balance = _balance(design, frame["t"].to_numpy(), overlap["ps"])
    bootstrap = _bootstrap(frame, design, n_bootstrap, seed)
    fragile = bool(np.sign(ols["coefficient"]) != np.sign(ipw["ate"]) and abs(ols["coefficient"]) > 1e-6 and abs(ipw["ate"]) > 1e-6)
    warnings = []
    if any(row["smd_weighted"] is not None and abs(row["smd_weighted"]) > SMD_WARN for row in balance):
        warnings.append("At least one covariate still has standardized mean difference above 0.25 after weighting.")
    if fragile:
        warnings.append("OLS and IPW estimates have different signs. The adjusted result is fragile.")
    if bootstrap["ci_low"] is not None and bootstrap["ci_low"] <= 0 <= bootstrap["ci_high"]:
        warnings.append("The bootstrap interval for the IPW estimate includes zero.")

    return {
        **base,
        "status": "estimated",
        "claim_level": "estimated_effect_under_untestable_assumptions",
        "message": (
            "An adjusted contrast was computed under no-unmeasured-confounding, overlap, and correct outcome measurement. "
            "Those assumptions are not verified. This is not a causal conclusion."
        ),
        "quality": quality,
        "association": association,
        "overlap": {key: overlap[key] for key in ("ps_min", "ps_max", "common_support_n", "message")},
        "confounders_used": design.columns.tolist(),
        "confounders_unavailable": missing_confounders,
        "balance": balance,
        "estimated_effect": {
            "ols_adjusted_difference": ols,
            "ipw_ate": ipw,
            "ipw_trimmed": trimmed,
            "bootstrap": bootstrap,
            "fragile": fragile,
            "warnings": warnings,
        },
        "robustness": {
            "sign_agreement": not fragile,
            "trim": "propensity weights outside the 1st/99th percentile were trimmed in ipw_trimmed",
            "smd_warning_threshold": SMD_WARN,
        },
    }


def _available(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def _school_nested(frame: pd.DataFrame) -> bool:
    if "school_id" not in frame.columns:
        return False
    varied = frame.groupby("school_id")["t"].nunique()
    return bool(len(varied) and (varied == 1).all())


def _design_matrix(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    pieces = []
    for column in columns:
        if column == "school_id":
            continue
        if column not in frame.columns:
            continue
        if pd.api.types.is_numeric_dtype(frame[column]):
            series = pd.to_numeric(frame[column], errors="coerce")
            if series.notna().mean() < 0.8 or series.nunique(dropna=True) < 2:
                continue
            pieces.append(series.fillna(series.median()).rename(column))
        else:
            dummies = pd.get_dummies(frame[column].astype(str), prefix=column, drop_first=True)
            if not dummies.empty:
                pieces.append(dummies)
    if "school_id" in columns and "school_id" in frame.columns:
        # Keep school dummies only if treatment varies in more than one school.
        dummies = pd.get_dummies(frame["school_id"].astype(str), prefix="school", drop_first=True)
        if not dummies.empty and not _school_nested(frame):
            pieces.append(dummies)
    if not pieces:
        return pd.DataFrame(index=frame.index)
    design = pd.concat(pieces, axis=1)
    design = design.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return design.astype(float)


def _propensity(design: pd.DataFrame, treatment: np.ndarray) -> dict:
    model = LogisticRegression(max_iter=500, solver="lbfgs")
    try:
        model.fit(design.to_numpy(), treatment)
    except Exception as exc:
        return {"ok": False, "message": f"Propensity model failed: {exc}"}
    ps = model.predict_proba(design.to_numpy())[:, 1]
    treated = ps[treatment == 1]
    control = ps[treatment == 0]
    if len(treated) == 0 or len(control) == 0:
        return {"ok": False, "message": "Propensity scores could not be split by arm."}
    low = max(float(treated.min()), float(control.min()), OVERLAP_LOW)
    high = min(float(treated.max()), float(control.max()), OVERLAP_HIGH)
    support = int(((ps >= low) & (ps <= high)).sum()) if low < high else 0
    if high - low < 0.02 or support < MIN_ARM:
        return {
            "ok": False,
            "message": "Propensity-score overlap is too thin for a defensible adjusted estimate.",
            "ps_min": round(float(ps.min()), 4),
            "ps_max": round(float(ps.max()), 4),
            "common_support_n": support,
        }
    return {
        "ok": True,
        "message": "Common support exists. Overlap is not proof that all confounders were measured.",
        "ps": ps,
        "ps_min": round(float(ps.min()), 4),
        "ps_max": round(float(ps.max()), 4),
        "common_support_n": support,
    }


def _ols(outcome: np.ndarray, treatment: np.ndarray, design: pd.DataFrame) -> dict:
    matrix = np.column_stack([treatment, design.to_numpy()])
    model = LinearRegression()
    model.fit(matrix, outcome)
    return {
        "coefficient": round(float(model.coef_[0]), 4),
        "interpretation": "OLS coefficient on treatment after linear adjustment for the listed covariates. Association, not a causal effect.",
    }


def _ipw(outcome: np.ndarray, treatment: np.ndarray, ps: np.ndarray, trim: bool = False) -> dict:
    ps = np.clip(ps, 0.01, 0.99)
    treated_p = treatment.mean()
    weights = np.where(treatment == 1, treated_p / ps, (1 - treated_p) / (1 - ps))
    if trim:
        low, high = np.quantile(weights, [0.01, 0.99])
        weights = np.clip(weights, low, high)
    ate = _hajek(outcome, treatment, weights)
    return {"ate": round(float(ate), 4), "weight_max": round(float(weights.max()), 4), "trimmed": trim}


def _hajek(outcome: np.ndarray, treatment: np.ndarray, weights: np.ndarray) -> float:
    treated = treatment == 1
    control = ~treated
    mu1 = np.sum(weights[treated] * outcome[treated]) / np.sum(weights[treated])
    mu0 = np.sum(weights[control] * outcome[control]) / np.sum(weights[control])
    return float(mu1 - mu0)


def _balance(design: pd.DataFrame, treatment: np.ndarray, ps: np.ndarray) -> list[dict]:
    ps = np.clip(ps, 0.01, 0.99)
    treated_p = treatment.mean()
    weights = np.where(treatment == 1, treated_p / ps, (1 - treated_p) / (1 - ps))
    rows = []
    for column in design.columns:
        values = design[column].to_numpy()
        rows.append(
            {
                "covariate": column,
                "smd_unweighted": round(_smd(values, treatment), 4),
                "smd_weighted": round(_smd(values, treatment, weights), 4),
            }
        )
    return rows


def _smd(values: np.ndarray, treatment: np.ndarray, weights: np.ndarray | None = None) -> float:
    if weights is None:
        weights = np.ones_like(values, dtype=float)
    def wmean(mask: np.ndarray) -> float:
        w = weights[mask]
        if w.sum() == 0:
            return 0.0
        return float(np.sum(w * values[mask]) / np.sum(w))
    def wvar(mask: np.ndarray) -> float:
        w = weights[mask]
        if w.sum() == 0:
            return 0.0
        mu = wmean(mask)
        return float(np.sum(w * (values[mask] - mu) ** 2) / np.sum(w))
    pooled = np.sqrt((wvar(treatment == 1) + wvar(treatment == 0)) / 2)
    if pooled < 1e-8:
        return 0.0
    return (wmean(treatment == 1) - wmean(treatment == 0)) / pooled


def _bootstrap(frame: pd.DataFrame, design: pd.DataFrame, n_bootstrap: int, seed: int) -> dict:
    if n_bootstrap <= 0:
        return {"n": 0, "ci_low": None, "ci_high": None}
    rng = np.random.default_rng(seed)
    estimates = []
    index = np.arange(len(frame))
    y = frame["y"].to_numpy()
    t = frame["t"].to_numpy()
    x = design.to_numpy()
    for _ in range(n_bootstrap):
        draw = rng.choice(index, size=len(index), replace=True)
        if len(np.unique(t[draw])) < 2:
            continue
        model = LogisticRegression(max_iter=400, solver="lbfgs")
        try:
            model.fit(x[draw], t[draw])
            ps = model.predict_proba(x[draw])[:, 1]
        except Exception:
            continue
        estimates.append(_hajek(y[draw], t[draw], np.where(t[draw] == 1, t[draw].mean() / np.clip(ps, 0.01, 0.99), (1 - t[draw].mean()) / np.clip(1 - ps, 0.01, 0.99))))
    if len(estimates) < 20:
        return {"n": len(estimates), "ci_low": None, "ci_high": None, "note": "Too few successful bootstrap draws."}
    low, high = np.quantile(estimates, [0.025, 0.975])
    return {"n": len(estimates), "ci_low": round(float(low), 4), "ci_high": round(float(high), 4), "method": "percentile_bootstrap"}

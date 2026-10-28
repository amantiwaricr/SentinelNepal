"""Model pipelines: preprocessing and estimator saved together as one object.

Because the fitted ``Pipeline`` (imputation, encoding, scaling, model) is saved as a single
artifact, inference can never apply different preprocessing from training.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from numpy.typing import NDArray
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from sentinel_ml.schema import FeatureProfile

ModelKind = Literal["logistic_regression", "random_forest"]

# Categories seen fewer times than this in training are grouped as "infrequent"; categories
# never seen in training map to that group too instead of raising errors at inference time.
MIN_CATEGORY_FREQUENCY = 20


def signed_log1p(values: NDArray[np.float64]) -> NDArray[np.float64]:
    """Compress heavy-tailed byte/packet counts so a linear model is not dominated by them."""
    return np.sign(values) * np.log1p(np.abs(values))


def build_preprocessor(profile: FeatureProfile, kind: ModelKind) -> ColumnTransformer:
    numeric_steps: list[tuple[str, object]] = [("impute", SimpleImputer(strategy="median"))]
    if kind == "logistic_regression":
        # Trees are insensitive to monotonic transforms and scale; the linear baseline is not.
        numeric_steps += [
            ("log", FunctionTransformer(signed_log1p, feature_names_out="one-to-one")),
            ("scale", StandardScaler()),
        ]
    categorical = Pipeline(
        [
            ("impute", SimpleImputer(strategy="constant", fill_value="missing")),
            (
                "encode",
                OneHotEncoder(
                    handle_unknown="infrequent_if_exist",
                    min_frequency=MIN_CATEGORY_FREQUENCY,
                    sparse_output=False,
                ),
            ),
        ]
    )
    return ColumnTransformer(
        [
            ("numeric", Pipeline(numeric_steps), list(profile.numeric)),
            ("categorical", categorical, list(profile.categorical)),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def build_estimator(
    kind: ModelKind,
    *,
    seed: int,
    class_weight: Literal["balanced"] | None,
    rf_estimators: int = 200,
    n_jobs: int = -1,
) -> LogisticRegression | RandomForestClassifier:
    if kind == "logistic_regression":
        return LogisticRegression(max_iter=2000, class_weight=class_weight, random_state=seed)
    return RandomForestClassifier(
        n_estimators=rf_estimators,
        class_weight=class_weight,
        random_state=seed,
        n_jobs=n_jobs,
    )


def build_pipeline(
    profile: FeatureProfile,
    kind: ModelKind,
    *,
    seed: int,
    class_weight: Literal["balanced"] | None,
    rf_estimators: int = 200,
    n_jobs: int = -1,
) -> Pipeline:
    return Pipeline(
        [
            ("preprocess", build_preprocessor(profile, kind)),
            (
                "model",
                build_estimator(
                    kind,
                    seed=seed,
                    class_weight=class_weight,
                    rf_estimators=rf_estimators,
                    n_jobs=n_jobs,
                ),
            ),
        ]
    )


def global_feature_importance(pipeline: Pipeline, profile: FeatureProfile) -> dict[str, float]:
    """Importance per original feature, normalised to sum to 1.

    Random Forest: impurity-based importance. Logistic Regression: mean absolute coefficient
    across classes on the scaled inputs. One-hot columns are summed back to their source
    feature. These describe what the model relies on overall — not why a single record was
    flagged, and not causation.
    """
    preprocess = pipeline.named_steps["preprocess"]
    model = pipeline.named_steps["model"]
    if hasattr(model, "feature_importances_"):
        raw = np.asarray(model.feature_importances_, dtype=float)
    else:
        raw = np.abs(np.asarray(model.coef_, dtype=float)).mean(axis=0)
    names = [str(n) for n in preprocess.get_feature_names_out()]

    totals = dict.fromkeys(profile.features, 0.0)
    for name, value in zip(names, raw, strict=True):
        source = name if name in totals else _categorical_source(name, profile)
        totals[source] += float(value)
    total = sum(totals.values())
    if total > 0:
        totals = {k: v / total for k, v in totals.items()}
    return dict(sorted(totals.items(), key=lambda item: item[1], reverse=True))


def _categorical_source(encoded_name: str, profile: FeatureProfile) -> str:
    # OneHotEncoder names columns "<feature>_<category>"; match the longest feature prefix.
    matches = [f for f in profile.categorical if encoded_name.startswith(f"{f}_")]
    if not matches:
        raise ValueError(f"Cannot map encoded column {encoded_name!r} to a feature")
    return max(matches, key=len)

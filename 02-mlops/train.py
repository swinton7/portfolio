"""Train two fraud models on synthetic payments, track them in MLflow, promote the best to @champion."""
import mlflow
import numpy as np
import pandas as pd
from mlflow import MlflowClient
from mlflow.models import infer_signature
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split

MODEL_NAME = "fraud-detector"


def make_dataset(n: int = 20_000, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "amount": rng.lognormal(7, 1.2, n).round(2),
        "hour": rng.integers(0, 24, n),
        "txn_count_24h": rng.poisson(3, n),
        "is_new_device": rng.integers(0, 2, n),
        "merchant_risk": rng.uniform(0, 1, n).round(3),
    })
    logit = (
        -6
        + 0.0003 * df.amount
        + 0.35 * df.txn_count_24h
        + 1.5 * df.is_new_device
        + 2.5 * df.merchant_risk
        + 1.0 * df.hour.isin([0, 1, 2, 3, 4]).astype(int)
    )
    df["is_fraud"] = (rng.uniform(0, 1, n) < 1 / (1 + np.exp(-logit))).astype(int)
    return df


df = make_dataset()
X, y = df.drop(columns="is_fraud"), df.is_fraud
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=7, stratify=y)

mlflow.set_experiment("fraud-detection")
candidates = {
    "logistic_regression": LogisticRegression(max_iter=1000),
    "gradient_boosting": GradientBoostingClassifier(n_estimators=150, max_depth=3),
}

results = {}
for name, model in candidates.items():
    with mlflow.start_run(run_name=name) as run:
        model.fit(X_train, y_train)
        scores = model.predict_proba(X_test)[:, 1]
        metrics = {"roc_auc": roc_auc_score(y_test, scores), "pr_auc": average_precision_score(y_test, scores)}
        mlflow.log_params(model.get_params())
        mlflow.log_metrics(metrics | {"fraud_rate": float(y.mean())})
        mlflow.sklearn.log_model(
            model,
            name="model",
            signature=infer_signature(X_test, scores),
            input_example=X_test.head(3),
            skops_trusted_types=["sklearn.tree._tree.Tree"],
        )
        results[name] = (run.info.run_id, metrics["pr_auc"])
        print(f"{name:<20} roc_auc={metrics['roc_auc']:.3f} pr_auc={metrics['pr_auc']:.3f}")

best, (run_id, pr_auc) = max(results.items(), key=lambda kv: kv[1][1])
version = mlflow.register_model(f"runs:/{run_id}/model", MODEL_NAME)
MlflowClient().set_registered_model_alias(MODEL_NAME, "champion", version.version)
print(f"promoted {best} as {MODEL_NAME} v{version.version} @champion (pr_auc={pr_auc:.3f})")

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def compute_metrics(y_true, y_pred):
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1, tp, fp, fn


def main():
    parser = argparse.ArgumentParser(description="Sweep vest thresholds and compute metrics.")
    parser.add_argument("--csv", required=True, help="CSV with columns: vest_conf,color_cov,label")
    parser.add_argument("--conf-min", type=float, default=0.2)
    parser.add_argument("--conf-max", type=float, default=0.7)
    parser.add_argument("--conf-steps", type=int, default=11)
    parser.add_argument("--cov-min", type=float, default=0.02)
    parser.add_argument("--cov-max", type=float, default=0.3)
    parser.add_argument("--cov-steps", type=int, default=15)
    parser.add_argument("--out", default="reports/threshold_sweep.csv")
    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    for col in ("vest_conf", "color_cov", "label"):
        if col not in df.columns:
            raise SystemExit(f"Missing column: {col}")

    y_true = df["label"].astype(int).to_numpy()
    confs = np.linspace(args.conf_min, args.conf_max, args.conf_steps)
    covs = np.linspace(args.cov_min, args.cov_max, args.cov_steps)

    rows = []
    for conf in confs:
        for cov in covs:
            y_pred = ((df["vest_conf"] >= conf) | ((df["vest_conf"] >= (conf * 0.67)) & (df["color_cov"] >= cov))).astype(int).to_numpy()
            precision, recall, f1, tp, fp, fn = compute_metrics(y_true, y_pred)
            rows.append(
                {
                    "conf": round(float(conf), 3),
                    "cov": round(float(cov), 3),
                    "precision": round(precision, 4),
                    "recall": round(recall, 4),
                    "f1": round(f1, 4),
                    "tp": tp,
                    "fp": fp,
                    "fn": fn,
                }
            )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out_path, index=False)
    print(f"Saved sweep to {out_path}")


if __name__ == "__main__":
    main()

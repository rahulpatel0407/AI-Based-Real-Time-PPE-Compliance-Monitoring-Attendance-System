import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Evaluate PPE model using Ultralytics val.")
    parser.add_argument("--model", required=True, help="Path to model .pt")
    parser.add_argument("--data", required=True, help="Path to data yaml")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--save-json", default="reports/ppe_eval.json")
    args = parser.parse_args()

    try:
        from ultralytics import YOLO
    except Exception as exc:
        raise SystemExit(f"ultralytics not available: {exc}")

    model = YOLO(args.model)
    results = model.val(data=args.data, imgsz=args.imgsz)

    report = {
        "model": args.model,
        "data": args.data,
        "imgsz": args.imgsz,
        "metrics": {
            "mAP50": float(results.box.map50) if results.box else None,
            "mAP50_95": float(results.box.map) if results.box else None,
            "precision": float(results.box.mp) if results.box else None,
            "recall": float(results.box.mr) if results.box else None,
        },
        "per_class": {
            "precision": results.box.p.tolist() if results.box and results.box.p is not None else [],
            "recall": results.box.r.tolist() if results.box and results.box.r is not None else [],
        },
    }

    out_path = Path(args.save_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved evaluation to {out_path}")


if __name__ == "__main__":
    main()

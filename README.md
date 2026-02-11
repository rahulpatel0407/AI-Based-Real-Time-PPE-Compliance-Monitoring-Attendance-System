# AI-Based-Real-Time-PPE-Compliance-Monitoring-Attendance-System

![CI](https://github.com/rahulpatel0407/AI-Based-Real-Time-PPE-Compliance-Monitoring-Attendance-System/actions/workflows/ci.yml/badge.svg)

CI Status: Runs `python -m pytest tests` on Ubuntu after installing `requirements.txt`.

At its core, a YOLOv8 vision engine detects PPE and personnel in real time, enabling automatic, tamper-resistant attendance. Violations trigger timestamped alerts for quick action, while a clean web dashboard presents live feeds, compliance trends, and exportable audit reports.

## Installation

1. Create and activate a virtual environment.
   - Windows:
     ```sh
     python -m venv .venv
     .\.venv\Scripts\activate
     ```
   - macOS/Linux:
     ```sh
     python -m venv .venv
     source .venv/bin/activate
     ```
2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```

## Quick Start (Local Inference)

1. Download models (see Models section).
2. Run a sample video inference:
   ```sh
   python YOLO_Video.py
   ```
3. Start the dashboard backend:
   ```sh
   python backend.py
   ```
4. Open the UI at http://localhost:5000

## Add a Camera / RTSP Source

Use the dashboard's camera management screen to add an RTSP/HTTP stream. Provide the stream URL and any credentials required by the camera. The backend stores camera configuration and uses it for live compliance monitoring.

## Models

Model checkpoints are not committed to Git. Place model weights at:

- YOLO-Weights/ppe.pt (default used by the detector)
- models/ (optional location for additional weights)

Run the download helper:

```sh
scripts/download_models.sh
```

Update the script with your model hosting URL if needed.

## Helper Scripts

- scripts/setup_env.sh: create a venv and install dependencies
- scripts/run_inference.sh: example command to run local inference
- scripts/download_models.sh: fetch model weights

## License

MIT License. See LICENSE.

## Author

Tej Pratap - tejpratapsingh62054@gmail.com
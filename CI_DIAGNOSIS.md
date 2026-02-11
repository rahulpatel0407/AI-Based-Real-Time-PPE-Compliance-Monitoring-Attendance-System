# CI Diagnostics

## Failing run

- Run ID: 21902184558
- Workflow: CI
- Job: test
- Step: Install dependencies
- Exit code: 1

## Error summary

The workflow installs Python 3.11, but requirements pin `torch==1.13.1` and `torchvision==0.14.1`. Those wheels are not available for Python 3.11, so `pip install -r requirements.txt` fails.

## Evidence

From the job log:

- "ERROR: Could not find a version that satisfies the requirement torchvision==0.14.1"
- "ERROR: No matching distribution found for torch==1.13.1"

Full logs are saved in:

- docs/ci-fix/ci-run-21902184558.zip

## Local reproduction

Using Python 3.11 locally:

- `python -m pip install -r requirements.txt`
- Fails with missing `torch==1.13.1` and `torchvision==0.14.1` distributions for Python 3.11.

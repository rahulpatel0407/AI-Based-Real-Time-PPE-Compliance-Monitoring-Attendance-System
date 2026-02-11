# CI Diagnostics

## Failing runs

- Run ID: 21902184558
	- Workflow: CI
	- Job: test
	- Step: Install dependencies
	- Exit code: 1
- Run ID: 21902763253
	- Workflow: CI
	- Job: test (3.10)
	- Step: Install dependencies
	- Exit code: 1
- Run ID: 21902886487
	- Workflow: CI
	- Job: test (3.10)
	- Step: Install dependencies
	- Exit code: 1
- Run ID: 21903025360
	- Workflow: CI
	- Job: test (3.10)
	- Step: Install dependencies
	- Exit code: 1

## Error summary

- Run 21902184558: The workflow installs Python 3.11, but requirements pin `torch==1.13.1` and `torchvision==0.14.1`. Those wheels are not available for Python 3.11, so `pip install -r requirements.txt` fails.
- Run 21902763253: Installing `lap==0.4.0` fails with `ModuleNotFoundError: No module named 'pkg_resources'` during wheel build.
- Run 21902886487: Same `pkg_resources` failure when building `lap==0.4.0`.
- Run 21903025360: Same `pkg_resources` failure when building `lap==0.4.0`.

## Evidence

From the job logs:

- "ERROR: Could not find a version that satisfies the requirement torchvision==0.14.1"
- "ERROR: No matching distribution found for torch==1.13.1"

Full logs are saved in:

- docs/ci-fix/ci-run-21902184558.zip
- docs/ci-fix/ci-run-21902763253.zip
- docs/ci-fix/ci-run-21902886487.zip
- docs/ci-fix/ci-run-21903025360.zip

## Local reproduction

Using Python 3.11 locally:

- `python -m pip install -r requirements.txt`
- Fails with missing `torch==1.13.1` and `torchvision==0.14.1` distributions for Python 3.11.

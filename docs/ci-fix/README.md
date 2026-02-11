# CI Fix Notes

## TL;DR

CI failed during dependency installation because `torch==1.13.1` and `torchvision==0.14.1` do not provide wheels for Python 3.11. The workflow now uses Python 3.10 and caches pip to keep installs consistent and faster.

## Logs

- Raw log archive: docs/ci-fix/ci-run-21902184558.zip
- Extracted log: docs/ci-fix/logs/0_test.txt

## Root cause

The CI workflow used Python 3.11, but the pinned torch/torchvision versions only support Python 3.10 and older. Pip failed before tests started.

## Fix applied

- Updated workflow to run with Python 3.10
- Added pip caching and explicit test command

## Local verification

- `python -m pip install -r requirements.txt` on Python 3.11 failed with the same missing wheel errors.

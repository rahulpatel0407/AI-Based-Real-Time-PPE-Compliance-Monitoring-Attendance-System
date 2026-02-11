# CI Fix Notes

## TL;DR

CI failed during dependency installation because `torch==1.13.1` and `torchvision==0.14.1` do not provide wheels for Python 3.11. The workflow now uses Python 3.10 and caches pip to keep installs consistent and faster.

## Logs

- Raw log archive: docs/ci-fix/ci-run-21902184558.zip
- Raw log archive: docs/ci-fix/ci-run-21902763253.zip
- Raw log archive: docs/ci-fix/ci-run-21902886487.zip

## Root cause

The CI workflow originally used Python 3.11, but the pinned torch/torchvision versions only support Python 3.10 and older. Pip failed before tests started. After switching to Python 3.10, the install failed when building `lap==0.4.0` due to missing `pkg_resources`.

## Fix applied

- Updated workflow to run with Python 3.10
- Ensure setuptools and wheel are installed before requirements
- Disable build isolation so `lap` can access `pkg_resources` from setuptools
- Added pip caching and explicit test command

## Local verification

- `python -m pip install -r requirements.txt` on Python 3.11 failed with the same missing wheel errors.

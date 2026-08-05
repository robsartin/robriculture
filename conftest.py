"""Pytest configuration.

Its mere presence at the repo root puts the root on ``sys.path`` (pytest's
prepend import mode adds the directory of the top-level ``conftest.py``), so the
project packages — ``kaggisim``, ``strategies``, ``harness`` — import whether
tests are run as ``pytest`` or ``python -m pytest``. Without this, a bare
``pytest`` (as CI runs it) fails to import ``kaggisim``.
"""

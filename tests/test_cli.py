"""CLI help works offline (no network)."""

from __future__ import annotations

import pytest

from quantframe.cli import main


def test_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_run_sample_help() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["run-sample", "--help"])
    assert exc.value.code == 0


def test_version() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0

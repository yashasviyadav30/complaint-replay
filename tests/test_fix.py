from pathlib import Path

import pytest

from replay.fix import Patch, apply_patch


def make_shop(tmp_path: Path) -> Path:
    (tmp_path / "static").mkdir(parents=True)
    (tmp_path / "static" / "config.js").write_text("OTP_TIMEOUT_MS: 4000,\n", encoding="utf-8")
    return tmp_path


def test_applies_edit_and_returns_diff(tmp_path: Path) -> None:
    shop = make_shop(tmp_path)
    diff = apply_patch(Patch("x", ({"file": "static/config.js", "find": "4000", "replace": "30000"},)), shop)
    assert (shop / "static" / "config.js").read_text(encoding="utf-8") == "OTP_TIMEOUT_MS: 30000,\n"
    assert "+OTP_TIMEOUT_MS: 30000," in diff


def test_rejects_paths_outside_the_app(tmp_path: Path) -> None:
    shop = make_shop(tmp_path / "shop")
    with pytest.raises(ValueError):
        apply_patch(Patch("x", ({"file": "../evil.py", "find": "a", "replace": "b"},)), shop)


def test_bad_edit_changes_nothing(tmp_path: Path) -> None:
    shop = make_shop(tmp_path)
    edits = ({"file": "static/config.js", "find": "4000", "replace": "30000"},
             {"file": "static/config.js", "find": "not there", "replace": "x"})
    with pytest.raises(ValueError):
        apply_patch(Patch("x", edits), shop)
    assert "4000" in (shop / "static" / "config.js").read_text(encoding="utf-8")

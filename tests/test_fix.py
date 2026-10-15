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


def test_patch_keeps_windows_line_endings(tmp_path) -> None:
    (tmp_path / "a.js").write_bytes(b"const a = 1;\r\nconst b = 2;\r\n")
    apply_patch(Patch("x", ({"file": "a.js", "find": "const a = 1;\nconst b = 2;", "replace": "const a = 3;\nconst b = 2;"},)), tmp_path)
    assert (tmp_path / "a.js").read_bytes() == b"const a = 3;\r\nconst b = 2;\r\n"


def test_patch_refuses_files_outside_the_allowed_paths(tmp_path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.js").write_text("x = 1", encoding="utf-8")
    (tmp_path / "server.js").write_text("y = 1", encoding="utf-8")
    apply_patch(Patch("x", ({"file": "src/a.js", "find": "x = 1", "replace": "x = 2"},)), tmp_path, ("src/*",))
    with pytest.raises(ValueError, match="not in the files"):
        apply_patch(Patch("x", ({"file": "server.js", "find": "y = 1", "replace": "y = 2"},)), tmp_path, ("src/*",))


def test_big_repo_sends_the_files_that_match_the_evidence(tmp_path) -> None:
    from replay import sources

    for i in range(30):
        (tmp_path / f"component{i}.js").write_text(f"export const c{i} = 'filler';\n" * 50, encoding="utf-8")
    (tmp_path / "Checkout.jsx").write_text("<button className='pay-btn'>Pay now</button>\n" + "// x\n" * 50, encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text("Pay now", encoding="utf-8")
    hints = ["'Pay now' is outside the screen (left=400px, screen=360px)"]
    picked = sources.pick(tmp_path, hints, budget=3000)
    assert picked[0] == "Checkout.jsx" and "node_modules/lib.js" not in picked
    assert sources.pick(tmp_path, hints, budget=10**7)[0] == "Checkout.jsx"  # small enough: everything goes

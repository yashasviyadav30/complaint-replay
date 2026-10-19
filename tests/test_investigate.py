from replay.agent import ReplayResult
from replay.browser import Evidence
from replay.investigate import proof_keys

CART = Evidence("E1", "unclear_name", "a button (in the navigation) is announced only as '1'", 2)
PLUS = Evidence("E2", "unclear_name", "a button (near 'Book') is announced only as '+'", 2)


def test_proof_keys_hold_only_the_cited_problem_not_every_item_of_its_kind() -> None:
    keys = proof_keys(ReplayResult("reproduced", "", ("E2",), (CART, PLUS), ()))
    assert keys == {"unclear_name: a button (near 'Book') is announced only as '+'"}


def test_nothing_is_proven_without_cited_evidence() -> None:
    assert proof_keys(ReplayResult("reproduced", "", (), (CART,), ())) == set()


def test_branch_copy_links_nested_dependencies_and_never_deletes_them(tmp_path) -> None:
    from replay.investigate import branch_copy, is_link, remove_branch

    src = tmp_path / "app"
    (src / "node_modules" / "react").mkdir(parents=True)
    (src / "packages" / "web" / "node_modules" / "vite").mkdir(parents=True)
    (src / "packages" / "web" / "index.js").write_text("x", encoding="utf-8")
    branch = branch_copy(src, tmp_path / "branch")
    assert is_link(branch / "node_modules") and is_link(branch / "packages" / "web" / "node_modules")
    assert (branch / "packages" / "web" / "index.js").read_text(encoding="utf-8") == "x"
    remove_branch(branch)
    assert not branch.exists() and (src / "packages" / "web" / "node_modules" / "vite").is_dir()


def test_a_patch_the_proof_rejects_gets_a_second_round_with_what_the_proof_saw(tmp_path, monkeypatch) -> None:
    import asyncio
    from contextlib import contextmanager

    import replay.investigate as inv
    from replay.conditions import CONDITIONS
    from replay.fix import Patch

    app = tmp_path / "app"
    app.mkdir()
    (app / "app.js").write_text("caller(); callee();\n", encoding="utf-8")
    monkeypatch.setattr(inv, "BRANCHES", tmp_path / "branches")
    bug = ReplayResult("reproduced", "amount lost", ("E1",), (CART,), ({"action": {"type": "click"}, "result": "ok"},))

    async def fake_replay(*args, **kwargs):
        return bug

    asked = []

    async def fake_fix(client, model, complaint, cond, before, branch, sources, rejected, allowed, also):
        asked.append(rejected)
        find = "caller();" if len(asked) == 1 else "callee();"
        return Patch("x", ({"file": "app.js", "find": find, "replace": find.replace("()", "(fixed)")},))

    proofs = iter([{"passed": False, "evidence": ["typed_value_lost: amount empty"]}, {"passed": True, "evidence": []}])

    async def fake_guard(url, guard, *args, **kwargs):
        return next(proofs) if url == "fix" else {"passed": False, "evidence": []}

    @contextmanager
    def fake_app(root):
        yield "fix"

    async def fake_model(client):
        return "m"

    async def no_research(evidence):
        return []

    monkeypatch.setattr(inv, "replay", fake_replay)

    async def no_map(*args, **kwargs):
        return []

    monkeypatch.setattr(inv, "build_map", no_map)
    monkeypatch.setattr(inv, "propose_fix", fake_fix)
    monkeypatch.setattr(inv, "run_guard", fake_guard)
    monkeypatch.setattr(inv, "running_app", fake_app)
    monkeypatch.setattr(inv, "pick_fix_model", fake_model)
    monkeypatch.setattr(inv, "research", no_research)
    case = {"id": "c1", "complaint": "amount disappears"}
    cond = CONDITIONS["fast_desktop"]
    result = asyncio.run(inv.investigate(case, inv.with_needs(cond, {"screen_reader": True}), "live", app,
                                         None, None, lambda c: None))
    assert asked[0] is None and "still shows the bug" in asked[1] and "typed_value_lost" in asked[1]
    assert result["stage"] == "guarded" and "callee(fixed)" in result["fix"]["diff"]

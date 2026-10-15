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

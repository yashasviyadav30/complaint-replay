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

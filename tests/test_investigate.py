from replay.agent import ReplayResult
from replay.browser import Evidence
from replay.investigate import fix_proven

ABORTED = Evidence("E1", "request_failed", "POST /api/otp/send failed (net::ERR_ABORTED)", 2)
WRONG_OTP = Evidence("E1", "http_error", "POST /api/otp/verify returned HTTP 400", 4)


def result(verdict: str, evidence: list[Evidence], cited: tuple[str, ...] = ()) -> ReplayResult:
    return ReplayResult(verdict, "", cited, tuple(evidence), ())


BEFORE = result("reproduced", [ABORTED], ("E1",))


def test_fix_proven_when_the_proving_evidence_is_gone_even_if_other_noise_appears() -> None:
    assert fix_proven(BEFORE, result("reproduced", [WRONG_OTP], ("E1",)))


def test_fix_not_proven_when_the_same_failure_comes_back() -> None:
    assert not fix_proven(BEFORE, result("not_reproduced", [ABORTED]))


def test_nothing_is_proven_without_cited_evidence() -> None:
    assert not fix_proven(result("reproduced", [ABORTED]), result("not_reproduced", []))

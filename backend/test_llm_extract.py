"""LLM extraction tests. Run: python test_llm_extract.py

These cover the wrapper around the API call — the deadline, the fallback, and
the guarantee that this function never raises — without calling Gemini. The
network is stubbed out so the suite stays fast and deterministic; whether Gemini
itself returns good symptoms is not something a unit test can assert.
"""

import time

import llm_extract
from llm_extract import (
    HTTP_DEADLINE_SECONDS,
    KNOWN_SYMPTOMS,
    WAIT_BUDGET_SECONDS,
    extract_symptoms_llm,
)


def _with_stub(fn):
    """Swap out the blocking API call, run a check, and put it back."""

    def wrapper():
        original = llm_extract._call_gemini
        original_client = llm_extract._client
        original_failed = llm_extract._client_failed
        # Pretend a client exists so the guard clause does not short-circuit.
        llm_extract._client = object()
        llm_extract._client_failed = False
        try:
            return fn()
        finally:
            llm_extract._call_gemini = original
            llm_extract._client = original_client
            llm_extract._client_failed = original_failed

    wrapper.__name__ = fn.__name__
    return wrapper


@_with_stub
def test_slow_call_gives_up_and_falls_back():
    """A hanging API call must not hold the triage request open.

    This is the whole point of the wrapper: the API's own minimum deadline is
    10s, which is far too long to leave someone staring at a blank screen when
    the offline extractor could have answered immediately.
    """
    llm_extract._call_gemini = lambda text: time.sleep(30)

    start = time.perf_counter()
    result = extract_symptoms_llm("I have a fever", timeout_seconds=0.5)
    elapsed = time.perf_counter() - start

    assert result is None, result
    assert elapsed < 2.0, f"waited {elapsed:.1f}s despite a 0.5s budget"


@_with_stub
def test_fast_call_is_returned():
    llm_extract._call_gemini = lambda text: ["cough", "fever"]
    assert extract_symptoms_llm("fever and cough") == ["cough", "fever"]


@_with_stub
def test_raising_call_returns_none_rather_than_propagating():
    """A triage request must not fail because the LLM did."""
    def boom(text):
        raise RuntimeError("network on fire")

    llm_extract._call_gemini = boom
    assert extract_symptoms_llm("I have a fever") is None


@_with_stub
def test_empty_input_never_calls_the_api():
    called = []
    llm_extract._call_gemini = lambda text: called.append(text)

    assert extract_symptoms_llm("") is None
    assert extract_symptoms_llm("   ") is None
    assert extract_symptoms_llm(None) is None
    assert not called, f"called the API for empty input: {called}"


def test_budget_is_shorter_than_the_api_deadline():
    """The client-side budget must actually bite.

    If it were the longer of the two, the wrapper would do nothing and users
    would still wait the full API deadline.
    """
    assert WAIT_BUDGET_SECONDS < HTTP_DEADLINE_SECONDS, (
        f"budget {WAIT_BUDGET_SECONDS}s does not undercut the "
        f"{HTTP_DEADLINE_SECONDS}s API deadline"
    )


def test_api_deadline_respects_the_documented_minimum():
    """Gemini rejects anything under 10s with a 400.

    Verified against the live API: "Manually set deadline 5s is too short.
    Minimum allowed deadline is 10s." Dropping below it does not make the app
    faster, it makes every call fail.
    """
    assert HTTP_DEADLINE_SECONDS >= 10.0, HTTP_DEADLINE_SECONDS


def test_allowed_symptom_list_is_not_empty():
    assert KNOWN_SYMPTOMS
    assert "chest_pain" in KNOWN_SYMPTOMS


if __name__ == "__main__":
    passed = failed = 0
    checks = [
        test_slow_call_gives_up_and_falls_back,
        test_fast_call_is_returned,
        test_raising_call_returns_none_rather_than_propagating,
        test_empty_input_never_calls_the_api,
        test_budget_is_shorter_than_the_api_deadline,
        test_api_deadline_respects_the_documented_minimum,
        test_allowed_symptom_list_is_not_empty,
    ]
    for check in checks:
        try:
            check()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL | {check.__name__}\n       {exc}")
        else:
            passed += 1
            print(f"PASS | {check.__name__}")

    print(f"\n{passed} passed, {failed} failed")

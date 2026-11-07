"""The case lifecycle: every allowed move has an authority, and the rest are refused."""

import pytest

from cobalt_exceptions.domain.lifecycle import TRANSITIONS, IllegalTransition, move


def test_a_filed_case_closes_only_when_customs_clears_it():
    assert move("filed", "closed") == "customs (the case is cleared)"
    with pytest.raises(IllegalTransition):
        move("action_attempted", "closed")


def test_nothing_reaches_the_store_without_approval():
    with pytest.raises(IllegalTransition):
        move("proposed", "action_attempted")


def test_an_unknown_outcome_is_settled_by_asking_the_store():
    assert {to for (frm, to) in TRANSITIONS if frm == "outcome_unknown"} == {
        "filed",
        "action_attempted",
    }


def test_a_closed_case_stays_closed():
    assert not [to for (frm, to) in TRANSITIONS if frm == "closed"]

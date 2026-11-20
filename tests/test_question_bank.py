from app.question_bank import (
    HOOK,
    ICE,
    PROBE,
    QUESTIONS,
    TOPIC_ORDER,
    pick_next_question,
    questions_of,
    suggest_topic,
)


def test_every_topic_has_full_question_set():
    for key in TOPIC_ORDER:
        ice = questions_of(key, ICE)
        probe = questions_of(key, PROBE)
        hook = questions_of(key, HOOK)
        assert len(ice) >= 3, key
        assert len(probe) >= 2, key
        assert len(hook) >= 1, key


def test_question_ids_are_unique():
    ids = [q.id for q in QUESTIONS]
    assert len(ids) == len(set(ids))


def test_pick_next_question_follows_order_and_skips_answered():
    answered = ["childhood-1", "childhood-2"]
    nxt = pick_next_question("childhood", answered)
    assert nxt is not None
    assert nxt.id == "childhood-3"
    assert nxt.kind == ICE


def test_pick_next_question_returns_none_when_exhausted():
    answered = [q.id for q in questions_of("wisdom")]
    assert pick_next_question("wisdom", answered) is None


def test_suggest_topic_prefers_least_answered():
    answered = ["childhood", "childhood", "childhood", "youth"]
    assert suggest_topic(answered) == "work"


def test_suggest_topic_defaults_to_first_topic():
    assert suggest_topic([]) == TOPIC_ORDER[0]
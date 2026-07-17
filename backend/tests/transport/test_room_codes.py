"""Room code generation: gfycat-style adjective-adjective-noun slugs."""

from app.transport.room_codes import ADJECTIVES, NOUNS, new_code


def test_code_is_two_distinct_adjectives_and_a_noun():
    for _ in range(200):
        first, second, noun = new_code().split("-")
        assert first in ADJECTIVES
        assert second in ADJECTIVES
        assert first != second  # random.sample avoids "sunny-sunny-cat"
        assert noun in NOUNS


def test_codes_are_lowercase_hyphenated_slugs():
    code = new_code()
    assert code == code.lower()
    assert code.count("-") == 2
    assert " " not in code

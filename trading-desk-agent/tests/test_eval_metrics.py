from deskagent.eval.metrics import citation_precision, keyword_recall, tool_usage_recall


def _transcript_with_tool_result(content: str) -> list[dict]:
    return [
        {"role": "user", "content": "a question"},
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "t1", "content": content}],
        },
    ]


def test_citation_precision_is_one_when_every_citation_is_supported() -> None:
    transcript = _transcript_with_tool_result(
        '{"citation": "pm-bayes-pricer/README.md (Headline result)", "text": "..."}'
    )
    answer = "See pm-bayes-pricer/README.md for the headline result."

    result = citation_precision(transcript, answer)

    assert result["precision"] == 1.0
    assert result["unsupported"] == []


def test_citation_precision_flags_a_hallucinated_citation() -> None:
    transcript = _transcript_with_tool_result('{"citation": "pm-bayes-pricer/README.md"}')
    answer = "See pm-bayes-pricer/README.md and also made-up/fake-file.md for details."

    result = citation_precision(transcript, answer)

    assert result["precision"] == 0.5
    assert "made-up/fake-file.md" in result["unsupported"]


def test_citation_precision_is_vacuously_one_with_no_citations_in_the_answer() -> None:
    result = citation_precision([], "I don't have evidence for this.")

    assert result["precision"] == 1.0
    assert result["cited"] == []
    assert result["cited_nothing"] is True


def test_citation_precision_is_zero_when_every_citation_is_unsupported() -> None:
    transcript = _transcript_with_tool_result('{"citation": "pm-bayes-pricer/README.md"}')
    answer = "See totally/fabricated-file.md for details."

    result = citation_precision(transcript, answer)

    assert result["precision"] == 0.0
    assert result["cited_nothing"] is False
    assert result["unsupported"] == ["totally/fabricated-file.md"]


def test_citation_precision_does_not_falsely_flag_a_sentence_ending_citation() -> None:
    # Regression test: a citation immediately followed by a sentence-ending
    # period must not have that period swept into the extracted token,
    # which would make a correctly-supported citation look unsupported.
    transcript = _transcript_with_tool_result('{"citation": "pm-bayes-pricer/README.md"}')
    answer = "The headline result is documented in pm-bayes-pricer/README.md."

    result = citation_precision(transcript, answer)

    assert result["precision"] == 1.0
    assert result["unsupported"] == []


def test_citation_precision_does_not_accept_a_truncated_citation_as_supported() -> None:
    # Regression test: a citation that's a textual substring of a real one
    # (e.g. missing its leading path segment) must not count as supported -
    # matching must be against whole extracted tokens, not raw substrings.
    transcript = _transcript_with_tool_result('{"citation": "foo/bar/baz.md"}')
    answer = "See bar/baz.md for details."

    result = citation_precision(transcript, answer)

    assert result["precision"] == 0.0
    assert result["unsupported"] == ["bar/baz.md"]


def test_tool_usage_recall_matches_hand_worked_example() -> None:
    actual = ["search_corpus", "get_file", "search_corpus"]
    expected = ["search_corpus", "run_stat_test"]

    # only search_corpus (1 of 2 expected types) was actually called
    assert tool_usage_recall(actual, expected) == 0.5


def test_tool_usage_recall_is_one_when_nothing_was_expected() -> None:
    assert tool_usage_recall([], []) == 1.0


def test_tool_usage_recall_is_one_for_a_full_match() -> None:
    assert tool_usage_recall(["a", "b"], ["a", "b"]) == 1.0


def test_keyword_recall_matches_hand_worked_example() -> None:
    answer = "The mean log loss was 0.41, beating the rule of thumb baseline."

    # "log loss" and "rule of thumb" present, "p-value" absent -> 2/3
    assert keyword_recall(answer, ["log loss", "rule of thumb", "p-value"]) == 2 / 3


def test_keyword_recall_is_case_insensitive() -> None:
    assert keyword_recall("BENJAMINI-HOCHBERG correction applied", ["benjamini-hochberg"]) == 1.0


def test_keyword_recall_is_one_with_no_keywords_to_check() -> None:
    assert keyword_recall("anything", []) == 1.0

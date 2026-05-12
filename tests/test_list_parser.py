"""Tests for list parsing strategies and ListParser selection logic."""

from __future__ import annotations

import pytest

from inu.utils.list_parser import (
    EnumerationMarkdownStrategy,
    ListParser,
    MarkdownListStrategy,
    SimpleStringSplitStrategy,
)


@pytest.mark.parametrize(
    ("content", "expected_processed"),
    [
        ("1. one\n2. two", ["one", "two"]),
        ("  1 one\n  2. two", ["one", "two"]),
    ],
)
def test_enumeration_markdown_strategy_parses_and_reassembles(content, expected_processed):
    """Enumeration markdown should parse and reassemble numbered lists."""
    strategy = EnumerationMarkdownStrategy(content)

    assert strategy.is_usable() is True
    assert strategy.bare_list == content.splitlines()
    assert strategy.processed_list == expected_processed
    assert strategy.count == len(expected_processed)
    assert strategy.reassemble(["x", "y"]) == "1. x\n2. y"


def test_enumeration_markdown_strategy_not_usable_with_single_line():
    """Single-line content should not be treated as a markdown list."""
    strategy = EnumerationMarkdownStrategy("1. one")

    assert strategy.is_usable() is False


@pytest.mark.parametrize(
    ("content", "expected_processed"),
    [
        ("- alpha\n- beta", ["alpha", "beta"]),
        ("* alpha\n* beta", ["alpha", "beta"]),
    ],
)
def test_markdown_list_strategy_parses_and_reassembles(content, expected_processed):
    """Bullet list markdown should parse and reassemble with '-' bullets."""
    strategy = MarkdownListStrategy(content)

    assert strategy.is_usable() is True
    assert strategy.bare_list == content.splitlines()
    assert strategy.processed_list == expected_processed
    assert strategy.count == len(expected_processed)
    assert strategy.reassemble(["x", "y"]) == "- x\n- y"


def test_simple_string_split_strategy_parses_and_reassembles():
    """Simple split strategy should trim processed values and keep raw parts."""
    strategy = SimpleStringSplitStrategy("a, b, c", ",")

    assert strategy.is_usable() is True
    assert strategy.bare_list == ["a", " b", " c"]
    assert strategy.processed_list == ["a", "b", "c"]
    assert strategy.count == 3
    assert strategy.reassemble(["x", "y"]) == "x,y"


def test_list_parser_prefers_enumeration_over_markdown_list():
    """Enumeration markdown has higher priority than bullet lists."""
    value = "1. one\n2. two"

    parser = ListParser()
    strategy = parser.parse(value)

    assert isinstance(strategy, EnumerationMarkdownStrategy)
    assert strategy.processed_list == ["one", "two"]


def test_list_parser_uses_markdown_list_strategy():
    """Bullet lists should select the markdown list strategy."""
    value = "- one\n- two"

    parser = ListParser()
    strategy = parser.parse(value)

    assert isinstance(strategy, MarkdownListStrategy)
    assert strategy.processed_list == ["one", "two"]


def test_list_parser_uses_simple_split_when_no_markdown():
    """Plain strings should fall back to simple splitting."""
    value = "one, two, three"

    parser = ListParser()
    strategy = parser.parse(value)

    assert isinstance(strategy, SimpleStringSplitStrategy)
    assert strategy.processed_list == ["one", "two", "three"]


def test_list_parser_count_separators_tracks_identifier_counts():
    """Parsed separator identifiers should be counted per list item."""
    value = "1. one\n2. two\n3. three"

    parser = ListParser()
    parser.parse(value)

    counts = parser.count_seperators
    assert counts
    # Use most_common to avoid ordering assumptions.
    _identifier, count = counts.most_common(1)[0]
    assert count == 3


def test_list_parser_check_if_list():
    """check_if_list should return True only for list-shaped strings."""
    assert ListParser.check_if_list("1. one\n2. two") is True
    assert ListParser.check_if_list("not a list") is False


def test_list_parser_raises_for_unparseable_string():
    """Parser should raise when no strategy is applicable."""
    parser = ListParser(separator_order=[])

    with pytest.raises(ValueError):
        parser.parse("no separators and no markdown")

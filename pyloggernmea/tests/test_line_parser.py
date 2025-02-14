import pytest
from line_parser import LineParser


def test_simple_split():
    parser = LineParser("a-b-c", "~split/-/|~")
    assert parser.parse() == ["a", "b", "c"]


def test_split_and_join():
    parser = LineParser("a-b-c", "~split/-/|join/::/~")
    assert parser.parse() == "a::b::c"


def test_truncate_number():
    parser = LineParser("3.14159", "~truncate/2/|~")
    assert parser.parse() == "3.14"


def test_split_truncate_join():
    parser = LineParser("1.234-5.678-9.101", "~split/-/|truncate/2/|join/,/~")
    assert parser.parse() == "1.23,5.67,9.10"


def test_invalid_double_split():
    parser = LineParser("a-b-c", "~split/-/|split/,/~")
    with pytest.raises(
        ValueError,
        match="template not valid two times split operation"
    ):
        parser.parse()


def test_invalid_join_without_list():
    parser = LineParser("abc", "~join/,/|~")
    with pytest.raises(
        ValueError,
        match="template not valid join operation for not list"
    ):
        parser.parse()


def test_truncate_with_mixed_values():
    parser = LineParser("1.23-abc-4.56", "~split/-/|truncate/1/|join/,/~")
    assert parser.parse() == "1.2,abc,4.5"


def test_empty_separators():
    parser = LineParser("a b c", "~split/ /|join//~")
    assert parser.parse() == "abc"


def test_no_operations():
    parser = LineParser("test", "~")
    assert parser.parse() == "test"


def test_invalid_truncate_on_string():
    parser = LineParser("abc", "~truncate/2/|~")
    with pytest.raises(
        ValueError,
        match="template not valid truncate operation for string"
    ):
        parser.parse()

from __future__ import annotations

from src.processing.salary_parser import parse_salary


def test_parse_annual_salary_range_with_k_suffix() -> None:
    result = parse_salary("$120k-$160k")

    assert result.salary_min == 120000
    assert result.salary_max == 160000
    assert result.salary_midpoint == 140000


def test_parse_annual_salary_range_with_plain_numbers() -> None:
    result = parse_salary("Base salary range: 110000 - 150000")

    assert result.salary_min == 110000
    assert result.salary_max == 150000
    assert result.salary_midpoint == 130000


def test_parse_hourly_salary_as_annualized() -> None:
    result = parse_salary("$65/hour")

    assert result.salary_min == 135200
    assert result.salary_max == 135200
    assert result.salary_midpoint == 135200

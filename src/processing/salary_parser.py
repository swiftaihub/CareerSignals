"""Salary parsing utilities."""

from __future__ import annotations

from dataclasses import dataclass
import re

from src.utils.text_cleaning import clean_text

ANNUAL_HOURS = 40 * 52


@dataclass(frozen=True)
class SalaryParseResult:
    salary_min: float | None
    salary_max: float | None
    salary_midpoint: float | None
    salary_range_text: str | None


EMPTY_SALARY = SalaryParseResult(None, None, None, None)

RANGE_SEPARATOR = r"(?:-|–|—|to)"
HOURLY_UNIT = r"(?:/|\bper\s+)?\s*(?:hour|hr|hourly)\b"
HOURLY_RANGE_RE = re.compile(
    rf"(?P<snippet>(?:\$|usd\s*)?\s*(?P<low>\d{{1,3}}(?:\.\d+)?)\s*"
    rf"{RANGE_SEPARATOR}\s*(?:\$|usd\s*)?\s*(?P<high>\d{{1,3}}(?:\.\d+)?)"
    rf"\s*{HOURLY_UNIT})",
    re.IGNORECASE,
)
HOURLY_SINGLE_RE = re.compile(
    rf"(?P<snippet>(?:\$|usd\s*)?\s*(?P<rate>\d{{1,3}}(?:\.\d+)?)\s*{HOURLY_UNIT})",
    re.IGNORECASE,
)
MONEY_TOKEN = (
    r"(?:\$|usd\s*)?\s*(?:"
    r"\d{2,3}(?:,\d{3})+"
    r"|\d{5,6}"
    r"|\d{2,3}(?:\.\d+)?\s*[kK]"
    r"|\d{2,3}(?:\.\d+)?"
    r")"
)
ANNUAL_RANGE_RE = re.compile(
    rf"(?P<snippet>(?P<low>{MONEY_TOKEN})\s*{RANGE_SEPARATOR}\s*(?P<high>{MONEY_TOKEN}))",
    re.IGNORECASE,
)
ANNUAL_SINGLE_RE = re.compile(
    rf"(?P<snippet>(?:salary|base|compensation|pay range|range)[^$0-9]{{0,40}}"
    rf"(?P<value>{MONEY_TOKEN}))",
    re.IGNORECASE,
)


def _parse_number(token: str, assume_thousands_for_small_numbers: bool = True) -> float:
    normalized = (
        token.casefold()
        .replace("usd", "")
        .replace("$", "")
        .replace(",", "")
        .replace(" ", "")
    )
    is_thousands = normalized.endswith("k")
    if is_thousands:
        normalized = normalized[:-1]

    value = float(normalized)
    if is_thousands:
        return value * 1000
    if assume_thousands_for_small_numbers and 30 <= value < 1000:
        return value * 1000
    return value


def _build_result(low: float, high: float, snippet: str) -> SalaryParseResult:
    salary_min = min(low, high)
    salary_max = max(low, high)
    midpoint = (salary_min + salary_max) / 2
    return SalaryParseResult(
        salary_min=round(salary_min, 2),
        salary_max=round(salary_max, 2),
        salary_midpoint=round(midpoint, 2),
        salary_range_text=clean_text(snippet),
    )


def parse_salary(text: str | None) -> SalaryParseResult:
    """Parse salary text into annualized min/max/midpoint values.

    Hourly rates are annualized with the MVP convention of 40 hours per week
    and 52 weeks per year.
    """

    source = clean_text(text)
    if not source:
        return EMPTY_SALARY

    hourly_range = HOURLY_RANGE_RE.search(source)
    if hourly_range:
        low = float(hourly_range.group("low")) * ANNUAL_HOURS
        high = float(hourly_range.group("high")) * ANNUAL_HOURS
        return _build_result(low, high, hourly_range.group("snippet"))

    hourly_single = HOURLY_SINGLE_RE.search(source)
    if hourly_single:
        annual = float(hourly_single.group("rate")) * ANNUAL_HOURS
        return _build_result(annual, annual, hourly_single.group("snippet"))

    annual_range = ANNUAL_RANGE_RE.search(source)
    if annual_range:
        low = _parse_number(annual_range.group("low"))
        high = _parse_number(annual_range.group("high"))
        if low >= 10000 and high >= 10000:
            return _build_result(low, high, annual_range.group("snippet"))

    annual_single = ANNUAL_SINGLE_RE.search(source)
    if annual_single:
        value = _parse_number(annual_single.group("value"))
        if value >= 10000:
            return _build_result(value, value, annual_single.group("snippet"))

    return EMPTY_SALARY

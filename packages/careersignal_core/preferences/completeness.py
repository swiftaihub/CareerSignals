"""Profile-completeness scoring based on confirmed user choices."""

from __future__ import annotations

from packages.careersignal_core.preferences.models import PreferencesPayload


COMPLETENESS_WEIGHTS = {
    "job_titles": 25,
    "locations_or_country": 15,
    "work_arrangements": 15,
    "skills": 25,
    "industries_or_seniority": 10,
    "match_priorities": 10,
}


def profile_completeness(preferences: PreferencesPayload, *, confirmed: bool) -> int:
    if not confirmed:
        return 0
    search = preferences.search_preferences
    score = 0
    if search.job_titles:
        score += COMPLETENESS_WEIGHTS["job_titles"]
    if search.locations or search.country:
        score += COMPLETENESS_WEIGHTS["locations_or_country"]
    if search.work_arrangements:
        score += COMPLETENESS_WEIGHTS["work_arrangements"]
    if preferences.skills:
        score += COMPLETENESS_WEIGHTS["skills"]
    if search.industries or search.seniority:
        score += COMPLETENESS_WEIGHTS["industries_or_seniority"]
    # A valid MatchPriorities model always represents an explicit usable total.
    score += COMPLETENESS_WEIGHTS["match_priorities"]
    return min(score, 100)

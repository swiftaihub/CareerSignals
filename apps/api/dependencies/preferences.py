from __future__ import annotations

from fastapi import Depends

from packages.careersignal_core.preferences.repository import PreferencesRepositoryProtocol
from packages.careersignal_core.preferences.service import PreferencesService
from packages.careersignal_core.repositories.preferences import PreferencesRepository


def get_preferences_repository() -> PreferencesRepositoryProtocol:
    return PreferencesRepository()


def get_preferences_service(
    repository: PreferencesRepositoryProtocol = Depends(get_preferences_repository),
) -> PreferencesService:
    return PreferencesService(repository)

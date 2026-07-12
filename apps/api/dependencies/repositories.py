from __future__ import annotations

from fastapi import Depends

from apps.api.dependencies.auth import get_current_identity
from apps.api.dependencies.authorization import CurrentUser, require_active_user
from packages.careersignal_core.repositories.activity import ActivityRepository
from packages.careersignal_core.repositories.admin import AdminRepository
from packages.careersignal_core.repositories.bootstrap import BootstrapRepository
from packages.careersignal_core.repositories.configs import ConfigRepository
from packages.careersignal_core.repositories.connector_runs import ConnectorRunRepository
from packages.careersignal_core.repositories.entitlements import EntitlementRepository
from packages.careersignal_core.repositories.jobs import JobRepository, build_job_repository
from packages.careersignal_core.repositories.pipeline_runs import PipelineRunRepository
from packages.careersignal_core.repositories.users import UserRepository


def get_repository(current_user: CurrentUser = Depends(require_active_user)) -> JobRepository:
    return build_job_repository(str(current_user.user_uuid))


def get_user_repository() -> UserRepository:
    return UserRepository()


def get_config_repository() -> ConfigRepository:
    return ConfigRepository()


def get_pipeline_run_repository() -> PipelineRunRepository:
    return PipelineRunRepository()


def get_connector_run_repository() -> ConnectorRunRepository:
    return ConnectorRunRepository()


def get_bootstrap_repository() -> BootstrapRepository:
    return BootstrapRepository()


def get_entitlement_repository() -> EntitlementRepository:
    return EntitlementRepository()


def get_admin_repository() -> AdminRepository:
    return AdminRepository()


def get_activity_repository() -> ActivityRepository:
    return ActivityRepository()

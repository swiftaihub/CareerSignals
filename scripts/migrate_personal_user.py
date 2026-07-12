"""Assign a legacy MotherDuck status partition to an explicit SaaS user UUID."""

from __future__ import annotations

import argparse
from uuid import UUID

from packages.careersignal_core.storage.motherduck import MotherDuckService


def migrate_statuses(*, legacy_user_id: str, user_uuid: str) -> int:
    target = str(UUID(user_uuid))
    service = MotherDuckService()
    with service.connect() as connection:
        count = connection.execute(
            "select count(*) from app.job_application_status where user_id = ?",
            [legacy_user_id],
        ).fetchone()[0]
        connection.execute(
            "update app.job_application_status set user_id = ? where user_id = ?",
            [target, legacy_user_id],
        )
    return int(count)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Assign a legacy application-status partition to an explicit user UUID."
    )
    parser.add_argument("--legacy-user-id", required=True)
    parser.add_argument("--user-uuid", required=True)
    args = parser.parse_args()
    migrated = migrate_statuses(legacy_user_id=args.legacy_user_id, user_uuid=args.user_uuid)
    print(f"Migrated {migrated} application status rows.")


if __name__ == "__main__":
    main()

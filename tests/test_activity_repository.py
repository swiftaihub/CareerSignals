import json
from datetime import datetime, timezone
from uuid import UUID

from packages.careersignal_core.repositories.activity import _json_dumps


def test_audit_json_serializes_database_profile_types() -> None:
    payload = {
        "user_uuid": UUID("11111111-1111-4111-8111-111111111111"),
        "activated_at": datetime(2026, 7, 11, 12, 30, tzinfo=timezone.utc),
    }

    encoded = json.loads(_json_dumps(payload))

    assert encoded == {
        "user_uuid": "11111111-1111-4111-8111-111111111111",
        "activated_at": "2026-07-11T12:30:00+00:00",
    }

from __future__ import annotations

from contextlib import contextmanager

from packages.careersignal_core.tasks.connector_refresh_worker import ConnectorRefreshWorker


class FakeRepository:
    def __init__(self) -> None:
        self.finish_calls = []

    def claim_next(self):
        return {
            "connector_run_uuid": "11111111-1111-4111-8111-111111111111",
            "trigger_type": "manual_cli",
            "scheduled_for": None,
            "next_scheduled_at": None,
        }

    def record_acquisition_audit(self, **kwargs):
        pass

    def upsert_source_result(self, **kwargs):
        pass

    def finish(self, **kwargs):
        self.finish_calls.append(kwargs)

    def requeue(self, *args, **kwargs):
        raise AssertionError("run should not be requeued")


class FakeConfigRepository:
    def active_user_snapshots(self):
        return []


class FakeLocks:
    def __init__(self) -> None:
        self.global_released = False
        self.writer_released = False

    @contextmanager
    def acquire(self, name, *, wait):
        try:
            yield
        finally:
            self.global_released = True

    @contextmanager
    def acquire_writer_slot(self, max_concurrency):
        try:
            yield
        finally:
            self.writer_released = True


class FakeSettings:
    user_pipeline_max_concurrency = 1


def _patch_worker_inputs(monkeypatch) -> None:
    import src.config.loader as config_loader
    import src.pipelines.shared_connector_refresh as shared_refresh

    monkeypatch.setattr(config_loader, "load_configs", lambda path: object())
    monkeypatch.setattr(
        shared_refresh,
        "build_acquisition_inputs",
        lambda configs, snapshots: (object(), [], {"user_snapshots": []}),
    )
    monkeypatch.setattr(shared_refresh, "source_names_from_config", lambda configs: [])
    monkeypatch.setattr(shared_refresh, "build_acquisition_query_plan", lambda **kwargs: [])


def _worker(monkeypatch, runner):
    _patch_worker_inputs(monkeypatch)
    repository = FakeRepository()
    locks = FakeLocks()
    worker = ConnectorRefreshWorker(
        repository=repository,
        config_repository=FakeConfigRepository(),
        locks=locks,
        settings=FakeSettings(),
        runner=runner,
    )
    return worker, repository, locks


def test_worker_records_published_jobs_from_shared_execution(monkeypatch) -> None:
    worker, repository, locks = _worker(
        monkeypatch,
        lambda **kwargs: {
            "status": "completed",
            "jobs_fetched": 12,
            "jobs_retained": 9,
            "jobs_published": 9,
            "shared_dbt_run_completed": True,
            "public_status_message": "Updated successfully",
            "acquisition": {},
        },
    )

    assert worker.process_one() is True
    assert repository.finish_calls[0]["status"] == "completed"
    assert repository.finish_calls[0]["jobs_published"] == 9
    assert repository.finish_calls[0]["shared_dbt_run_completed"] is True
    assert locks.global_released is True
    assert locks.writer_released is True


def test_dbt_failure_uses_worker_lifecycle_status(monkeypatch) -> None:
    worker, repository, _ = _worker(
        monkeypatch,
        lambda **kwargs: {
            "status": "failed",
            "jobs_fetched": 12,
            "jobs_retained": 9,
            "jobs_published": 0,
            "shared_dbt_run_completed": False,
            "public_status_message": "Shared transformation failed.",
            "acquisition": {},
        },
    )

    worker.process_one()

    assert repository.finish_calls[0]["status"] == "failed"
    assert repository.finish_calls[0]["shared_dbt_run_completed"] is False


def test_publication_exception_is_recorded_and_locks_are_released(monkeypatch) -> None:
    def fail_publication(**kwargs):
        raise RuntimeError("publication unavailable")

    worker, repository, locks = _worker(monkeypatch, fail_publication)

    worker.process_one()

    assert repository.finish_calls[0]["status"] == "failed"
    assert repository.finish_calls[0]["jobs_published"] == 0
    assert repository.finish_calls[0]["public_status_message"] == (
        "The shared-data refresh was not completed."
    )
    assert locks.global_released is True
    assert locks.writer_released is True


def test_default_worker_runner_includes_postgresql_publisher(monkeypatch) -> None:
    import packages.careersignal_core.publication.shared_jobs as publication
    import src.pipelines.shared_connector_refresh as shared_refresh

    publisher = object()
    captured = {}
    monkeypatch.setattr(publication, "SharedJobsPublisher", lambda: publisher)
    monkeypatch.setattr(
        shared_refresh,
        "run_shared_connector_refresh",
        lambda **kwargs: captured.update(kwargs) or {},
    )

    ConnectorRefreshWorker._default_runner(connector_run_uuid="run-id")

    assert captured["publisher"] is publisher

from __future__ import annotations

from job import build_job_summary, run_job


def test_build_job_summary_contains_status_and_record_count():
    summary = build_job_summary(records_processed=3, status="success")

    assert summary == {
        "status": "success",
        "records_processed": 3,
        "job_name": "dummy-nightly-import",
    }


def test_run_job_returns_success_summary(monkeypatch):
    monkeypatch.setenv("OPS_BOARD_SERVICE_NAME", "dummy-job-test")

    summary = run_job(records=2, export=False)

    assert summary["status"] == "success"
    assert summary["records_processed"] == 2

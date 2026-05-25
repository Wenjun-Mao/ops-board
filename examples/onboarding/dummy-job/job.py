from __future__ import annotations

import logging
import time

from tenacity import retry, stop_after_attempt, wait_exponential

from shared.ops_observe import bootstrap_observability, observe

LOGGER = logging.getLogger("ops_board.dummy_job")
JOB_NAME = "dummy-nightly-import"


def build_job_summary(records_processed: int, status: str) -> dict[str, int | str]:
    return {
        "status": status,
        "records_processed": records_processed,
        "job_name": JOB_NAME,
    }


@retry(wait=wait_exponential(multiplier=0.1, min=0.1, max=1), stop=stop_after_attempt(3))
def simulate_external_read(record_id: int) -> dict[str, int | str]:
    return {"record_id": record_id, "value": f"record-{record_id}"}


@observe("dummy-job.process-record")
def process_record(record_id: int) -> dict[str, int | str]:
    record = simulate_external_read(record_id)
    time.sleep(0.05)
    LOGGER.info("dummy_job_record_processed", extra={"record_id": record_id})
    return record


@observe("dummy-job.run")
def _run_observed_job(records: int) -> dict[str, int | str]:
    processed = 0
    for record_id in range(records):
        process_record(record_id)
        processed += 1

    summary = build_job_summary(records_processed=processed, status="success")
    LOGGER.info("dummy_job_completed", extra=summary)
    return summary


def run_job(records: int = 5, *, export: bool = True) -> dict[str, int | str]:
    bootstrap_observability(
        export=export,
        service_name="dummy-job",
        service_namespace="ops-board.examples",
        owner="mk",
    )
    return _run_observed_job(records)


def main() -> None:
    summary = run_job()
    print(summary)


if __name__ == "__main__":
    main()

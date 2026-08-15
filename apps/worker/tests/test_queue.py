from jobmatch_worker.queue import retry_delay_seconds


def test_retry_delay_is_bounded_exponential() -> None:
    assert retry_delay_seconds(1) == 5
    assert retry_delay_seconds(2) == 10
    assert retry_delay_seconds(10) == 300
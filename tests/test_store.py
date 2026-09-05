from label_printer_helper.store import QueueStore
from label_printer_helper.config import AppConfig


def report(report_id=12, checked_by="Lewis"):
    return {
        "report_id": report_id,
        "checked_at": "2026-09-05T12:00:00+00:00",
        "checked_by": checked_by,
        "label": {"serial_number": "PF1EX81X", "model": "T14 GEN 2"},
    }


def test_queue_only_marks_selected_operators_for_printing(tmp_path):
    store = QueueStore(tmp_path / "queue.db")

    store.add_reports([report(12, "Lewis"), report(13, "Kyle")], ["Lewis"])

    assert [job["report_id"] for job in store.pending()] == [12]
    assert store.get(13)["status"] == "ignored"


def test_queue_deduplicates_reports_and_persists_cursor(tmp_path):
    store = QueueStore(tmp_path / "queue.db")
    item = report()

    assert store.add_reports([item], ["Lewis"]) == 1
    assert store.add_reports([item], ["Lewis"]) == 0
    store.set_cursor(12)

    reopened = QueueStore(tmp_path / "queue.db")
    assert reopened.get_cursor() == 12


def test_successful_job_is_not_pending_again(tmp_path):
    store = QueueStore(tmp_path / "queue.db")
    store.add_reports([report()], ["Lewis"])

    store.set_status(12, "printed")

    assert store.pending() == []
    assert store.get(12)["attempts"] == 1


def test_label_format_is_part_of_saved_configuration():
    config = AppConfig(label_format="second_checked")

    assert config.label_format == "second_checked"

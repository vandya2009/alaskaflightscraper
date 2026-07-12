from src import csv_output


def test_existing_keys_empty_when_file_missing():
    assert csv_output.existing_keys("Results") == set()


def test_append_then_existing_keys_recognizes_it(sample_row):
    csv_output.append_results([sample_row], tab_name="Results")
    assert csv_output.result_key(sample_row) in csv_output.existing_keys("Results")


def test_deleting_file_resets_dedup_regardless_of_anything_else(sample_row):
    csv_output.append_results([sample_row], tab_name="Results")
    assert csv_output.existing_keys("Results") != set()

    (csv_output.OUTPUT_DIR / "results.csv").unlink()

    assert csv_output.existing_keys("Results") == set()


def test_header_written_once_across_multiple_appends(sample_row):
    csv_output.append_results([sample_row], tab_name="Results")
    csv_output.append_results([{**sample_row, "price_usd": 999.0}], tab_name="Results")

    path = csv_output.OUTPUT_DIR / "results.csv"
    lines = path.read_text().splitlines()
    assert lines[0] == ",".join(csv_output.RESULT_HEADERS)
    assert len(lines) == 3  # header + 2 data rows


def test_append_results_empty_list_is_a_noop():
    csv_output.append_results([], tab_name="Results")
    assert not (csv_output.OUTPUT_DIR / "results.csv").exists()


def test_append_log_writes_header_and_row():
    csv_output.append_log("OK", "All searches completed", 5, 2)
    path = csv_output.OUTPUT_DIR / "log.csv"
    lines = path.read_text().splitlines()
    assert lines[0] == ",".join(csv_output.LOG_HEADERS)
    assert "OK,All searches completed,5,2" in lines[1]


def test_different_tabs_write_different_files(sample_row):
    csv_output.append_results([sample_row], tab_name="Results")
    csv_output.append_results([sample_row], tab_name="Best Deals")
    assert (csv_output.OUTPUT_DIR / "results.csv").exists()
    assert (csv_output.OUTPUT_DIR / "best_deals.csv").exists()

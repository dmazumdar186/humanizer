"""
Tests for humanizer.py --batch mode.

All tests use --dry-run to avoid live LLM calls.
No API keys required to run this file.
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = str(REPO_ROOT / "humanizer.py")
PY = sys.executable

sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

load_dotenv(str(REPO_ROOT / ".env"))

PASS_COUNT = 0
FAIL_COUNT = 0
FAILURES: list[tuple[str, str]] = []


def run(name: str, fn) -> None:
    global PASS_COUNT, FAIL_COUNT
    try:
        fn()
        print(f"PASS  {name}")
        PASS_COUNT += 1
    except Exception as exc:
        print(f"FAIL  {name}")
        print(f"      {exc}")
        FAIL_COUNT += 1
        FAILURES.append((name, str(exc)))


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PY, SCRIPT, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(REPO_ROOT),
    )


def _write_csv(path: Path, rows: list[dict]) -> None:
    """Write a batch input CSV. rows must have 'text_id' and 'text_to_humanize' keys."""
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict]:
    """Read a CSV and return rows as list of dicts."""
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------------
# Test 1: 3-row CSV, all rows succeed
# ---------------------------------------------------------------------------

def test_batch_3_rows_all_succeed(tmp_dir: Path) -> None:
    """3-row CSV with valid texts → output CSV has 3 rows with non-empty humanized."""
    input_csv = tmp_dir / "input_all_good.csv"
    output_csv = tmp_dir / "out_all_good.csv"

    _write_csv(input_csv, [
        {"text_id": "r1", "text_to_humanize": "Certainly! I'd be happy to delve into this robust framework."},
        {"text_id": "r2", "text_to_humanize": "Absolutely! Let's leverage synergies and unlock comprehensive solutions."},
        {"text_id": "r3", "text_to_humanize": "It's worth noting that this is a game-changer for navigating complexities."},
    ])

    result = _run_cli(
        "--batch", str(input_csv),
        "--out", str(output_csv),
        "--dry-run",
    )
    assert result.returncode == 0, (
        f"--batch should exit 0\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert output_csv.exists(), "Output CSV should be created"

    rows = _read_csv(output_csv)
    assert len(rows) == 3, f"Expected 3 output rows, got {len(rows)}"

    for row in rows:
        assert row["humanized"] != "", f"Row {row['text_id']}: humanized should be non-empty (dry-run produces stub)"
        assert row["error"] == "", f"Row {row['text_id']}: error should be empty, got: {row['error']!r}"

    # Summary line in stdout
    assert "BATCH SUMMARY" in result.stdout, f"Expected BATCH SUMMARY in stdout: {result.stdout}"
    assert "3 total" in result.stdout, f"Expected '3 total' in summary: {result.stdout}"
    assert "3 succeeded" in result.stdout, f"Expected '3 succeeded' in summary: {result.stdout}"


# ---------------------------------------------------------------------------
# Test 2: 3-row CSV, 1 row has empty text → per-row failure isolation
# ---------------------------------------------------------------------------

def test_batch_one_row_fails(tmp_dir: Path) -> None:
    """3-row CSV with 1 empty row → batch completes, error captured for failed row only."""
    input_csv = tmp_dir / "input_one_fail.csv"
    output_csv = tmp_dir / "out_one_fail.csv"

    _write_csv(input_csv, [
        {"text_id": "ok1", "text_to_humanize": "Certainly! Let me delve into this."},
        {"text_id": "bad", "text_to_humanize": ""},          # empty text → triggers error path
        {"text_id": "ok2", "text_to_humanize": "Absolutely! Let's leverage this robust system."},
    ])

    result = _run_cli(
        "--batch", str(input_csv),
        "--out", str(output_csv),
        "--dry-run",
    )
    # Batch should still exit 0 — per-row failures don't crash the batch
    assert result.returncode == 0, (
        f"Batch with one failed row should still exit 0\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert output_csv.exists(), "Output CSV should be created even when some rows fail"

    rows = _read_csv(output_csv)
    assert len(rows) == 3, f"Expected 3 output rows (including failed), got {len(rows)}"

    # Map rows by text_id for easy lookup
    by_id = {r["text_id"]: r for r in rows}

    assert by_id["ok1"]["error"] == "", f"ok1 should have no error, got: {by_id['ok1']['error']!r}"
    assert by_id["ok2"]["error"] == "", f"ok2 should have no error, got: {by_id['ok2']['error']!r}"
    assert by_id["bad"]["error"] != "", f"bad (empty text) row should have error captured"

    # Summary should reflect 2 succeeded, 1 failed
    assert "BATCH SUMMARY" in result.stdout
    assert "3 total" in result.stdout
    assert "1 failed" in result.stdout, f"Expected '1 failed' in summary: {result.stdout}"


# ---------------------------------------------------------------------------
# Test 3: Concurrency safety — max_workers=2 with 4 rows, no duplicate writes
# ---------------------------------------------------------------------------

def test_batch_concurrency_no_duplicate_writes(tmp_dir: Path) -> None:
    """max_workers=2, 4 rows → output CSV has exactly 4 rows, no duplicates."""
    input_csv = tmp_dir / "input_concurrent.csv"
    output_csv = tmp_dir / "out_concurrent.csv"

    texts = [
        "Certainly! Let me delve into this first comprehensive analysis.",
        "Absolutely! Let's leverage these robust synergies immediately.",
        "It's worth noting that this is a game-changer for everyone.",
        "In conclusion, let's navigate the complexities and elevate together.",
    ]
    _write_csv(input_csv, [
        {"text_id": f"row{i}", "text_to_humanize": t}
        for i, t in enumerate(texts)
    ])

    result = _run_cli(
        "--batch", str(input_csv),
        "--out", str(output_csv),
        "--max-workers", "2",
        "--dry-run",
    )
    assert result.returncode == 0, (
        f"Concurrent batch should exit 0\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert output_csv.exists()

    rows = _read_csv(output_csv)
    assert len(rows) == 4, f"Expected 4 rows in output, got {len(rows)}"

    # No duplicate text_id values
    ids = [r["text_id"] for r in rows]
    assert len(ids) == len(set(ids)), f"Duplicate text_id detected: {ids}"

    # All rows should have non-empty humanized (dry-run stub)
    for row in rows:
        assert row["humanized"] != "", f"Row {row['text_id']} has empty humanized"

    assert "4 total" in result.stdout, f"Expected '4 total' in summary: {result.stdout}"


# ---------------------------------------------------------------------------
# Test 4: Missing input file → non-zero exit
# ---------------------------------------------------------------------------

def test_batch_missing_input_file(tmp_dir: Path) -> None:
    """Non-existent input CSV → exit non-zero, clear error."""
    result = _run_cli(
        "--batch", str(tmp_dir / "nonexistent.csv"),
        "--out", str(tmp_dir / "out.csv"),
        "--dry-run",
    )
    assert result.returncode != 0, f"Missing input should exit non-zero, got 0"


# ---------------------------------------------------------------------------
# Test 5: Batch + --batch mutually exclusive with --text
# ---------------------------------------------------------------------------

def test_batch_mutually_exclusive_with_text(tmp_dir: Path) -> None:
    """--batch and --text are mutually exclusive → argparse error (exit 2)."""
    input_csv = tmp_dir / "dummy.csv"
    _write_csv(input_csv, [{"text_id": "x", "text_to_humanize": "hello"}])

    result = _run_cli(
        "--batch", str(input_csv),
        "--text", "some text",
        "--dry-run",
    )
    assert result.returncode == 2, (
        f"--batch + --text should produce argparse error (exit 2), got {result.returncode}"
    )


# ---------------------------------------------------------------------------
# Test 6: Default output path convention
# ---------------------------------------------------------------------------

def test_batch_default_output_path(tmp_dir: Path) -> None:
    """Without --out, output is written to humanized_<stem>.csv beside input."""
    input_csv = tmp_dir / "drafts.csv"
    expected_output = tmp_dir / "humanized_drafts.csv"

    _write_csv(input_csv, [
        {"text_id": "d1", "text_to_humanize": "Certainly! I'd be happy to help."},
    ])

    result = _run_cli("--batch", str(input_csv), "--dry-run")
    assert result.returncode == 0, (
        f"Default output path run should exit 0\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert expected_output.exists(), (
        f"Expected output at {expected_output} but it does not exist"
    )


# ---------------------------------------------------------------------------
# Test 7: --batch --help mentions batch flags
# ---------------------------------------------------------------------------

def test_batch_help_mentions_batch_flags() -> None:
    """--help output should document --batch, --max-workers, and --out."""
    result = _run_cli("--help")
    assert result.returncode == 0
    assert "--batch" in result.stdout, "--help should mention --batch"
    assert "--max-workers" in result.stdout, "--help should mention --max-workers"
    assert "--out" in result.stdout, "--help should mention --out"


# ---------------------------------------------------------------------------
# Runner (direct-run style matching existing test files)
# ---------------------------------------------------------------------------

def _make_tmp() -> Path:
    """Create a per-test temp directory in .tmp/ (already gitignored)."""
    import time, os
    tmp = REPO_ROOT / ".tmp" / f"test_batch_{int(time.time() * 1000)}_{os.getpid()}"
    tmp.mkdir(parents=True, exist_ok=True)
    return tmp


if __name__ == "__main__":
    # Tests that need a tmp_dir get one created per-test
    def _wrap_with_tmp(fn):
        def _inner():
            td = _make_tmp()
            try:
                fn(td)
            finally:
                import shutil
                shutil.rmtree(td, ignore_errors=True)
        return _inner

    run("batch 1: 3-row CSV all succeed (dry-run)", _wrap_with_tmp(test_batch_3_rows_all_succeed))
    run("batch 2: 1 empty row - per-row failure isolation", _wrap_with_tmp(test_batch_one_row_fails))
    run("batch 3: concurrency max_workers=2, no duplicate writes", _wrap_with_tmp(test_batch_concurrency_no_duplicate_writes))
    run("batch 4: missing input file - non-zero exit", _wrap_with_tmp(test_batch_missing_input_file))
    run("batch 5: --batch + --text mutually exclusive", _wrap_with_tmp(test_batch_mutually_exclusive_with_text))
    run("batch 6: default output path convention", _wrap_with_tmp(test_batch_default_output_path))
    run("batch 7: --help documents batch flags", test_batch_help_mentions_batch_flags)

    print(f"\n{'='*50}")
    print(f"Results: {PASS_COUNT} passed, {FAIL_COUNT} failed")
    if FAILURES:
        print("\nFailed tests:")
        for name, err in FAILURES:
            print(f"  FAIL  {name}")
            print(f"        {err}")
    sys.exit(0 if FAIL_COUNT == 0 else 1)

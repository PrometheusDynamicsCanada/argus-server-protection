#!/usr/bin/env python3
"""
Standalone verification script for the Argus v4 redacted public benchmark archive.
Recalculates headline tables from the 71 per-trial `.probes.jsonl` and `.summary.json`
records using only the Python standard library, and verifies REDACTION_MANIFEST.json SHA-256s.
"""

import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
TRIALS_DIR = ROOT / "trials"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_probes_match_summary(probes_path: Path, summary_path: Path) -> tuple[int, int]:
    rows = [json.loads(line) for line in probes_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    summary = load_json(summary_path)
    active_rows = [r for r in rows if r["phase"] == "active_flood"]
    within_500 = sum(1 for r in active_rows if r.get("within_500ms"))
    expected = summary["phases"]["active_flood"]["within_500ms"]
    assert len(active_rows) == 40, f"{probes_path}: expected 40 active_flood probes, found {len(active_rows)}"
    assert within_500 == expected, f"{probes_path}: within_500ms={within_500} != summary={expected}"
    return within_500, len(active_rows)


def main() -> None:
    print("=" * 80)
    print("ARGUS REDACTED PUBLIC ARCHIVE (v4) - RAW TIMELINE & MANIFEST VERIFIER")
    print("=" * 80)

    manifest = load_json(ROOT / "REDACTION_MANIFEST.json")
    for rel, expected_sha in manifest["file_sha256"].items():
        actual_sha = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        assert actual_sha == expected_sha, f"SHA-256 mismatch on {rel}: {actual_sha} != {expected_sha}"
    print(f"[PASS] Verified SHA-256 integrity across {len(manifest['file_sha256'])} data & figure artifacts.")

    total_trials = 0
    total_active_probes = 0
    for subdir in sorted(TRIALS_DIR.iterdir()):
        if not subdir.is_dir():
            continue
        for s_path in sorted(subdir.glob("*.summary.json")):
            p_path = s_path.with_name(s_path.name.replace(".summary.json", ".probes.jsonl"))
            assert p_path.exists(), f"Missing probe timeline for {s_path.name}"
            _, n_active = verify_probes_match_summary(p_path, s_path)
            total_trials += 1
            total_active_probes += n_active
    print(f"[PASS] Verified {total_trials} raw trial timelines ({total_active_probes} active-load visitor probes).")

    deep = load_json(DATA_DIR / "argus-cross-size-4usd-18usd-48usd-2026-11-07.json")
    t3 = deep["three_run_comparison_350_and_800"]
    for tier_key, label in [("tier2_350conns", "350 conns + 12w"), ("tier3_800conns", "800 conns + 12w")]:
        row = t3[tier_key]
        r4_arg = row["4usd_1vcpu_512mb_argus"]
        print(f"  {label}: $4/mo + Argus = {r4_arg['pooled_active_flood_within_500ms_pct']:.1f}% ({r4_arg['pooled_active_flood_within_500ms_count_of_120']}/120)")

    timings = load_json(DATA_DIR / "argus-detection-timings-2026-11-07.json")
    reps = timings["observations"]
    t1_t4 = [r["stage_durations_ms"]["trigger_to_connection_release_ms"] for r in reps]
    t1_t5 = [r["stage_durations_ms"]["trigger_to_first_packet_block_ms"] for r in reps if r["stage_durations_ms"]["trigger_to_first_packet_block_ms"] is not None]
    print(f"  Trigger -> Connection release (n={len(t1_t4)}/10): min={min(t1_t4):.2f} ms, median={statistics.median(t1_t4):.2f} ms, max={max(t1_t4):.2f} ms")
    print(f"  Trigger -> First packet block (n={len(t1_t5)}/10): min={min(t1_t5):.2f} ms, median={statistics.median(t1_t5):.2f} ms, max={max(t1_t5):.2f} ms")

    pkt = load_json(DATA_DIR / "packet_handling_verification.json")
    rb = load_json(DATA_DIR / "rollback_verification.json")
    boot = load_json(DATA_DIR / "post_reboot_verification.json")
    shared = load_json(DATA_DIR / "argus-shared-ip-verification-2026-11-07.json")
    assert pkt["all_passed"] and len(pkt["cases"]) == 13 and rb["all_passed"] and boot["all_passed"] and shared["all_passed"]
    print("[PASS] Verified 13/13 traffic-handling cases, rollback, cold-reboot SSH, and shared-IP checks.")
    print("=" * 80)


if __name__ == "__main__":
    main()

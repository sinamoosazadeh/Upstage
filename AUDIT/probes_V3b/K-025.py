"""K-025 probe — page-scoped quality measurement hides cross-page gaps and
pre-delivery drops.

READ-ONLY. Calls the real `apex.ops.engine_context.page_quality_measurements`
with real MarketObservation rows built by the frozen parser. Writes only this
probe's .out file.

1. Two consecutive single-row 1h pages (opens 00:00 and 02:00) — the shape two
   catch-up cycles produce — measured separately, then the same two rows
   measured as one page.
2. A page whose invalid row was dropped BEFORE delivery (the CP-12 hygiene gate
   removes it from the served rows), measured with and without the real
   offered/accepted counts.
3. The production call site: which arguments does it actually pass?
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = pathlib.Path(__file__).with_suffix(".out")
_buf = []


def say(line=""):
    _buf.append(str(line))
    OUT.write_text("\n".join(_buf) + "\n")


def main():
    from apex.data_catalog.ingest.toobit_public import parse_kline_to_observation
    from apex.ops.engine_context import page_quality_measurements

    HOUR = 3_600_000
    T0 = 1_672_531_200_000

    def obs(open_ms, c="100.5"):
        return parse_kline_to_observation(
            "BTCUSDT", "1h",
            [open_ms, "100", "101", "99", c, "10", open_ms + HOUR - 1], 0)

    say("# K-025 — page quality measurement scope")
    say()
    say("1. two single-row pages vs the same rows in one page")
    p1 = page_quality_measurements([obs(T0)], "1h", http_status=200)
    p2 = page_quality_measurements([obs(T0 + 2 * HOUR)], "1h", http_status=200)
    both = page_quality_measurements([obs(T0), obs(T0 + 2 * HOUR)], "1h",
                                     http_status=200)
    say("   page A (open 00:00)      = %r" % p1)
    say("   page B (open 02:00)      = %r" % p2)
    say("   both rows in one page    = %r" % both)
    say("   -> the missing 01:00 bar is invisible when the rows arrive in "
        "separate pages")

    say()
    say("2. a row dropped before delivery (CP-12 hygiene gate)")
    served = [obs(T0), obs(T0 + HOUR)]            # a 3rd row was dropped
    say("   served rows only          = %r"
        % page_quality_measurements(served, "1h", http_status=200))
    say("   with real offered/accepted= %r"
        % page_quality_measurements(served, "1h", http_status=200,
                                    offered=3, accepted=2))

    say()
    say("3. production call site arguments")
    out = subprocess.run(
        ["grep", "-rn", "-A4", "page_quality_measurements(", "--include=*.py",
         "apex"], cwd=str(ROOT), capture_output=True, text=True).stdout
    for line in out.strip().splitlines():
        say("   " + line)

    say()
    say("4. consumers of these numbers (apex/quality/vector.py:120-155)")
    say("   q_seq        = 1 - gap_count/expected_count      -> 1.0 in case 1")
    say("   q_source     = 1.0 if source_health >= 0.8       -> 1.0")
    say("   veto_completeness = completeness_pct < 100       -> never fires")
    say("   veto_source       = source_health < 0.8          -> never fires")


if __name__ == "__main__":
    main()
    sys.stdout.write(OUT.read_text())

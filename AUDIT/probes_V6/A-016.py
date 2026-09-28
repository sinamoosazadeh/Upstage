"""V6 probe A-016: InjectionLedger.inject does not require validation/approval.
A package that validate_package() REJECTED (contains VETO_FRESHNESS_SLA) can
still be written (suggestion file + ledger) via a direct inject call.
Same package_id with a DIFFERENT hash is a silent no-op (cached=True,
identical=False), not an error. Everything happens inside a temp directory.
"""
import sys
import pathlib
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.research import governance as gov

with tempfile.TemporaryDirectory() as td:
    root = pathlib.Path(td)
    ledger = gov.InjectionLedger(path=root / "injection_log.json",
                                 research_root=root)
    pkg = gov.ParameterPackage(
        package_id="pkg-probe", version="1.0.0",
        values={"VETO_FRESHNESS_SLA": 0},      # RED LINE content
        code_revision="a" * 40, feature_version="4.0.0",
        model_version="4.0.0", seed=1, reason="probe")

    verdict = gov.validate_package(pkg)
    print("validate_package ->", verdict["decision"], "red_line_clean=", verdict["red_line_clean"])

    out = ledger.inject(pkg, package_dir=root / "pkgs")
    print("direct inject ->", out)
    print("files written:", sorted(p.name for p in (root / "pkgs").iterdir()))
    print("ledger len:", len(ledger))

    # same package_id, DIFFERENT content (hash) -> ?
    pkg2 = gov.ParameterPackage(
        package_id="pkg-probe", version="1.0.1",
        values={"VETO_FRESHNESS_SLA": 1},      # different value + version
        code_revision="a" * 40, feature_version="4.0.0",
        model_version="4.0.0", seed=1, reason="probe-2")
    out2 = ledger.inject(pkg2, package_dir=root / "pkgs")
    print("re-inject same id, different hash ->", out2)
    print("files written now:", sorted(p.name for p in (root / "pkgs").iterdir()))

    # control: same id + same hash -> no_op identical
    out3 = ledger.inject(pkg, package_dir=root / "pkgs")
    print("re-inject same id + same hash ->", out3)
    print()
    print("real params/ dir untouched:",
          not (REPO / "apex" / "research" / "params_suggestions").exists()
          or "pre-existing")

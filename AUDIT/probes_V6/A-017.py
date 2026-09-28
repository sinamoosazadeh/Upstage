"""V6 probe A-017: the RED LINE guard constrains package_dir/target but NOT
InjectionLedger.path (nor its _flush). The ledger can be pointed at a path
OUTSIDE the allowed research root and the write still happens. An existing
non-JSON file at the ledger path makes _load crash (json.JSONDecodeError).
Everything runs inside temp dirs; the real params/ is never touched.
"""
import sys
import pathlib
import tempfile
import json

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from apex.research import governance as gov

with tempfile.TemporaryDirectory() as td:
    root = pathlib.Path(td)
    allowed = root / "suggestions"          # the allowed research root
    outside = root / "elsewhere"            # OUTSIDE the allowed root

    pkg = gov.ParameterPackage(
        package_id="pkg-p", version="1.0.0", values={"alpha_spread": 0.3},
        code_revision="a" * 40, feature_version="4.0.0",
        model_version="4.0.0", seed=1, reason="probe")

    # ledger path OUTSIDE the allowed research root — accepted and written
    ledger = gov.InjectionLedger(path=outside / "injection_log.json",
                                 research_root=allowed)
    out = ledger.inject(pkg, package_dir=allowed / "pkgs")
    print("inject with ledger path outside allowed root ->", out["cached"], out["no_op"])
    print("ledger file exists at (outside) path:",
          (outside / "injection_log.json").exists())

    # equivalence argument: assert_live_params_untouched is never called on
    # self.path — show by source inspection
    import inspect
    src = inspect.getsource(gov.InjectionLedger)
    print("ledger methods call assert_live_params_untouched on package_dir/target only:",
          src.count("assert_live_params_untouched") == 2)
    flush_src = inspect.getsource(gov.InjectionLedger._flush)
    print("_flush validates path against research root:",
          "assert_live_params_untouched" in flush_src)

    # control: package_dir outside the root IS refused
    try:
        ledger.inject(pkg, package_dir=root / "forbidden")
        print("package_dir outside root -> NOT refused (unexpected)")
    except gov.ResearchRedLineError as e:
        print("control: package_dir outside root -> refused:", e.reason)

    # control: package_dir under the REAL params/ IS refused (no write)
    try:
        ledger.inject(pkg, package_dir=gov.LIVE_PARAMS_DIR)
        print("package_dir under real params/ -> NOT refused (unexpected)")
    except gov.ResearchRedLineError as e:
        print("control: package_dir under real params/ -> refused:", e.reason)

    # existing non-JSON (YAML-like) file at the ledger path -> crash in _load
    yamlish = root / "suggestions2" / "not_a_real_param.yaml"
    yamlish.parent.mkdir(parents=True, exist_ok=True)
    yamlish.write_text("budget_per_trade: 0.005\nk_attn: 0.25\n")
    try:
        gov.InjectionLedger(path=yamlish, research_root=root / "suggestions2")
        print("ledger on YAML file -> constructed (no crash)")
    except json.JSONDecodeError as e:
        print("ledger on YAML file -> json.JSONDecodeError:", str(e)[:80])
    except Exception as e:
        print("ledger on YAML file ->", type(e).__name__, str(e)[:80])

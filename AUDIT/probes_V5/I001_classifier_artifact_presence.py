"""I-001: real config loader reacts to the fixed model-artifact pathname."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import apex.config as config

real_dir = config.PARAMS_DIR
try:
    with TemporaryDirectory(prefix="i001-params-") as td:
        params_dir = Path(td)
        config.PARAMS_DIR = params_dir
        absent = None
        try:
            config.load_params()["e11_classifier"]
        except FileNotFoundError as exc:
            absent = type(exc).__name__
        # Minimal valid YAML mapping is enough for the params loader; this is
        # not a classifier-quality test and does not touch repository params/.
        (params_dir / config.PARAMS_FILES["e11_classifier"]).write_text(
            "artifact_marker: test-only\n", encoding="utf-8")
        present = config.load_params()["e11_classifier"]
        print(json.dumps({"absent_result": absent,
                          "present_result": present,
                          "fixed_repo_params_dir": str(real_dir)},
                         sort_keys=True, indent=2))
finally:
    config.PARAMS_DIR = real_dir

"""I-002: probe actual config parser/Params boundaries without repo writes."""
import json
from apex.config import Params, load_params, _YamlSubsetParser

params = Params()
risk = params["risk_defaults"]
original = risk["budget_per_trade"]
risk["budget_per_trade"] = -123.0
same_instance = params["risk_defaults"]["budget_per_trade"]
fresh_instance = load_params()["risk_defaults"]["budget_per_trade"]
parser_results = {}
for name, text in {
    "valid_flow": "values: [1, 2]\n",
    "anchor_alias": "base: &anchor 1\ncopy: *anchor\n",
    "block_scalar": "value: |\n  content\n",
    "multi_document": "a: 1\n---\nb: 2\n",
}.items():
    try:
        parser_results[name] = {"accepted": True,
                                "value": _YamlSubsetParser(text).parse()}
    except Exception as exc:
        parser_results[name] = {"accepted": False,
                                "error": type(exc).__name__,
                                "message": str(exc)}
print(json.dumps({
    "params_docstring_claims_read_only_view": Params.__doc__ is not None,
    "original_budget": original,
    "same_instance_after_mutation": same_instance,
    "fresh_instance_after_mutation": fresh_instance,
    "parser_cases": parser_results,
}, sort_keys=True, indent=2))

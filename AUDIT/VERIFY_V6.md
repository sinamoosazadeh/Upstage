# VERIFY_V6 — Independent read-only verification of APEX_GEN5_AUDIT.md (Session V6)

- **Verifier scope (mandated):** A-001..A-018, B-001, B-002, J-001..J-024, O-001..O-003, V-001, V-002 — 49 IDs, all covered.
- **Baseline:** `sinamoosazadeh/Upstage` @ `85b2c155d7b054a468379ddfd802eb239d0801f9` (`git rev-parse HEAD` verified at session start; branch `arena/01a0e8b1-upstage`).
- **Audit report under verification:** commit `690e2d8899319a7c7a96456f92c3008878e59346`, `AUDIT/APEX_GEN5_AUDIT.md` (392 rows, Persian). Every row was read in full from the fetched report; the index was used only as a map.
- **Method:** full reads of `apex/config.py` (all 511 lines), `apex/research/governance.py` (627), `apex/research/promotion.py` (563), `pyproject.toml`, `README.md`, `.gitignore`, `tests/unit/test_config.py`, `tests/unit/test_cp1_foundations.py`, `tests/unit/test_research_governance.py`, `tests/conftest.py`, plus every file/line range each row cites (quoted below where governing). Probes import the REAL repository code only; they write only under `AUDIT/probes_V6/` and temp dirs. No source/config/test/doc file was modified; no PR opened; no order placed; no exchange/Telegram endpoint contacted; no secret or `.env` read; `data/` never touched.
- **Environment:** Python 3.11, `pip install --break-system-packages -r requirements.lock pytest` (numpy 1.26.0, pandas 2.2.0, pydantic 2.5.0, pytest 9.1.1 — the nine pins plus dev-only pytest). Tests run with `python3 -m pytest -q -p no:cacheprovider`. The checkout was shallow at start; `git fetch --unshallow origin` was run (read-only history fetch, no working-tree change) to enable the repo's own git-history-dependent tests (see X-V6-002).
- **Severity scale used:** S0 blocks safe/basic operation; S1 serious trading/accounting/recovery/protection impact; S2 limited impact or observability; S3 documentation; S4 informational.

## Summary table

| ID | Verdict | Auditor severity | Independent severity | Frozen? | Cross-ref (D/ISSUE) | Recommended option |
|---|---|---|---|---|---|---|
| A-001 | CONFIRMED | S1 | S1 | config.py CP-1-owned (ISSUE-CP2-006), not in brief's frozen list | — | B |
| A-002 | CONFIRMED | S2 | S2 | config.py CP-1-owned | — | A |
| A-003 | CONFIRMED | S1 | S2 | config.py CP-1-owned | ISSUE-CP1-008 | A |
| A-004 | CONFIRMED | S1 | S2 | config.py CP-1-owned | — | A |
| A-005 | CONFIRMED (strengthened) | S1 | S2 | config.py CP-1-owned | — | A |
| A-006 | CONFIRMED | S2 | S2 | config.py CP-1-owned | — | A |
| A-007 | CONFIRMED | S2 | S2 | config.py CP-1-owned | — | A |
| A-008 | CONFIRMED | S2 | S2 | config.py CP-1-owned | — | B |
| A-009 | CONFIRMED | S2 | S2 | config.py CP-1-owned | — | A |
| A-010 | CONFIRMED | S2 | S2 | config.py CP-1-owned | — | A |
| A-011 | CONFIRMED | S2 | S2 | config.py CP-1-owned | — | B |
| A-012 | CONFIRMED | S2 | S2 | config.py CP-1-owned | — | A |
| A-013 | CONFIRMED | S2 | S2 | `.gitignore` ADR-P2-013-governed | — | A |
| A-014 | CONFIRMED | S1 | S2 | governance.py/promotion.py not frozen | §17.1 change-proposal protocol | A |
| A-015 | CONFIRMED | S1 | S1 | governance.py not frozen | W.5 RED LINE | A |
| A-016 | CONFIRMED | S1 | S2 | governance.py not frozen | T-PKG-001 | A |
| A-017 | CONFIRMED | S2 | S2 | governance.py not frozen | W.5/G6 | A |
| A-018 | CONFIRMED | S2 | S2 | governance.py not frozen | §17.1 EC register | A |
| B-001 | CONFIRMED (strengthened) | S1 | S1 | pyproject.toml not frozen | ADR-P2-002 | A |
| B-002 | CONFIRMED | S2 | S2 | fsm.py not frozen; requirements.lock IS frozen | Ch.1 SBOM | A |
| J-001 | CONFIRMED | S2 | S2 | README non-frozen | G16 | A |
| J-002 | CONFIRMED | S3 | S3 | config.py docstring CP-1-owned | D13, ISSUE-CP8-004 | A |
| J-003 | CONFIRMED | S2 | S2 | catalog.py FROZEN (apex/data_catalog/**) | §3.12/§3.13 | A (owner ruling) |
| J-004 | CONFIRMED | S2 | S2 | catalog.py/contracts.py FROZEN | §3.13 | A |
| J-005 | CONFIRMED | S2 | S2 | matrix non-frozen | D49, D30 | A |
| J-006 | CONFIRMED | S2 | S2 | APEX_GEN5.md (D2-patchable) | Z.8 | A (owner definition) |
| J-007 | CONFIRMED | S1 | S2 | APEX_GEN5.md (D2-patchable) | W.2 vs Z.1/Z.4 | A (owner ruling) |
| J-008 | CONFIRMED | S2 | S2 | handoff non-frozen | — | A |
| J-009 | CONFIRMED | S2 | S2 | APEX_GEN5.md (D2-patchable) | Session-A F3 vs P4; = D58 adjacency | A (owner ruling) |
| J-010 | CONFIRMED | S1 | S2 | APEX_GEN5.md + backup.py non-frozen | = D-021 (wiring); AI.7/SL-12/§2.6 conflict is the increment | A (owner ruling) |
| J-011 | CONFIRMED | S2 | S2 | APEX_GEN5.md (D2-patchable) | AI.0 precedence | A (owner ruling) |
| J-012 | CONFIRMED | S2 | S2 | handoff/matrix non-frozen | PR #24/#25 transport record | A |
| J-013 | CONFIRMED | S2 | S2 | APEX_GEN5.md + logistic.py docstring | = D34 (resolved); residual text | A |
| J-014 | CONFIRMED | S2 | S2 | APEX_GEN5.md (D2-patchable) | AI.0/AI.15 | A |
| J-015 | CONFIRMED | S2 | S2 | APEX_GEN5.md (D2-patchable) | = D59 (resolved); fence stale | A |
| J-016 | CONFIRMED | S2 | S2 | decision log + engine (E10 FROZEN) | ISSUE-CP5-006 | A (owner ruling) |
| J-017 | CONFIRMED | S2 | S2 | APEX_GEN5.md (D2-patchable) | = D34 (PAPER resolved); LIVE unresolved | A (owner ruling) |
| J-018 | CONFIRMED | S2 | S2 | APEX_GEN5.md (D2-patchable) | D50 vs AI.8 | A (owner ruling) |
| J-019 | CONFIRMED | S2 | S2 | APEX_GEN5.md (D2-patchable) | = D29; Y.2 residual; D-030 (L3) separate | A (owner ruling) |
| J-020 | CONFIRMED | S2 | S2 | APEX_GEN5.md (D2-patchable) | §2.6/AI.5 vs W.6; K-007/008 separate | A (owner ruling) |
| J-021 | CONFIRMED | S2 | S2 | APEX_GEN5.md (D2-patchable) | Y.1/Y.3/Y.4 | A (owner ruling) |
| J-022 | CONFIRMED | S2 | S2 | APEX_GEN5.md (D2-patchable) | AI.0/AI.15, AF.1 | A |
| J-023 | CONFIRMED | S2 | S2 | APEX_GEN5.md (D2-patchable) | = ISSUE-CP8-002 (resolved) | A |
| J-024 | CONFIRMED | S2 | S2 | §17 table + risk YAML FROZEN | = D8 / ISSUE-CP8-001 (resolved) | A |
| O-001 | PARTIAL | S4 | S4 | docs/README non-frozen | D2 | A |
| O-002 | CONFIRMED | S4 | S4 | .gitignore ADR-P2-013 | ADR-CP14-021, D3 | A (device evidence) |
| O-003 | CONFIRMED | S4 | S4 | requirements.lock FROZEN | Ch.1 SBOM | A (owner decision) |
| V-001 | CONFIRMED | S4 | S4 | six YAMLs FROZEN | D62 | n/a (keep) |
| V-002 | CONFIRMED (extended) | S4 | S4 | config.py CP-1-owned | ISSUE-CP1-008 | n/a (keep) |
| X-V6-001 | CONFIRMED (new) | — | S4 | catalog.py FROZEN | J-003 adjacent | A |
| X-V6-002 | CONFIRMED (new) | — | S3 | test file non-frozen | O-001 adjacent | A |

Independent counts: **CONFIRMED 48, PARTIAL 1, REJECTED 0, DEVICE-EVIDENCE-NEEDED 0** (device-evidence elements are flagged inside rows where relevant). Severity deltas vs auditor: 6 rows lowered by one level (A-003, A-004, A-005, A-014, A-016, J-007, J-010 — see each row for justification); no increases; B-001 and A-005 strengthened in substance.

---

## A-001

**Auditor claim (short quote).** "فایل تنظیمات صریحِ ناموجود خاموش نادیده گرفته می‌شود… با محیط ارث‌رسیدهٔ `LIVE/1/1` و مسیر ناموجودِ فایل PAPER، Config همچنان `LIVE/True/True` برگرداند" — an explicitly named, non-existent `--env-file` is silently ignored; with inherited env `LIVE/1/1` and a missing PAPER file, Config still returns LIVE/True/True.

**What I read.** `apex/config.py` in full (functions `_load_env` L112–119, `Config.__init__` L151–153, accessors L156–200 — `if path and os.path.exists(path)` silently skips a missing explicit path); `scripts/run_apex.py` L1088–1089 (`--env-file` argparse, default None) and L1132 (`cfg = Config(args.env_file)`); all `Config(` call sites (`grep -rn "Config(" apex/ scripts/` → paper_loop, telegram gateway, fsm, ops modules construct `Config()`/`Config(env_path)`); `tests/unit/test_config.py` (no test passes a non-existent explicit path).

**Reproduction.** `python3 -B AUDIT/probes_V6/A-001.py` → `AUDIT/probes_V6/A-001.out`: `_load_env("/tmp/.../env.paper")` (absent) raises nothing; with process env `APEX_ENV=LIVE, APEX_ALLOW_SIGNED=1, APEX_ECONOMIC_GATE_SIGNED=1, APEX_SQLITE_PATH=data/live.sqlite3` and a **missing** paper env file, `Config(path).apex_env/allow_signed/economic_gate_signed/sqlite_path == ("LIVE", True, True, "data/live.sqlite3")`. Controls: unset env + existing file → PAPER values; unset env + missing file → RESEARCH defaults.

**Verdict and reasoning.** CONFIRMED. The code path is unconditional and my probe reproduces the exact triple. Note a nuance the auditor also implies: even when the file EXISTS the inherited process env wins (no-shadow rule, by design), so the missing-file silence removes the only signal that the operator's chosen file was never read.

**Root cause.** `_load_env` treats "explicit path" and "default path" identically (`os.path.exists` guard, no error for the explicit case); `scripts/run_apex.py` passes the explicit path straight through.

**Direct impact.** A typo'd `--env-file` silently runs with whatever the inherited environment says — potentially LIVE/signed/production DB instead of PAPER. Real order submission was not tested (same boundary as the auditor); downstream transport selection (`apex/execution/toobit_adapter._credentials` requires `APEX_ALLOW_SIGNED=1`) and DB path follow.

**Secondary effects and interactions.** Downstream: transport choice, trading permission, DB isolation. Upstream: `.env`/`APEX_DOTENV_PATH` mechanism unaffected. Interacts with A-013 (custom env file names) and A-002 (misparsed .env values).

**Contract and decisions.** §2.5/§9.5-12 (APEX_GEN5.md L20505, L1151): nine env names, `.env` parsed stdlib-only; G16 "Every surface fails closed: missing credentials … produce a reported refusal, never an invented result" (README L44–47 restates). A silently ignored explicit config path contradicts the fail-closed philosophy but no clause names `--env-file` specifically (it is a CP-7 CLI addition). No decision log entry covers it.

**Frozen status and non-frozen alternative.** `apex/config.py` is not in the session brief's FROZEN list, but ISSUE-CP2-006 calls it "frozen config.py (CP-1 frozen)" — treat as CP-1-owned, changes need a DECISION_LOG entry. Non-frozen alternative exists: validate the explicit path in `scripts/run_apex.py` (composition root, non-frozen) before constructing `Config`.

**Fix options.** A) In `run_apex.py`: if `args.env_file` was supplied and `os.path.exists` is false, exit with a named refusal (e.g. `ENV_FILE_MISSING`). Side effects: none on the nine-name surface; a new test; operators who rely on the current tolerance would now get a hard stop (intended). B) In `config.py`: make `_load_env` raise for a non-existent EXPLICIT path while keeping the default `.env` optional. Side effects: touches a CP-1-owned module (needs decision-log entry); any caller passing speculative paths would now fail; `tests/unit/test_ops_telegram_gateway.py:316` sets `APEX_DOTENV_PATH=/nonexistent/.env` and expects tolerance — that test would need a decision-aware update.

**My recommendation.** A (refusal at the CLI layer, outside the CP-1-owned module), with B reserved for an owner-approved config.py revision.

**Acceptance and regression tests.** New: `--env-file <missing>` exits non-zero with a named reason even under a valid inherited env (probe A-001 as the template). Regression: existing 14 `test_config.py` tests must stay green; add a case that an existing explicit file still cannot shadow real env.

---

## A-002

**Auditor claim (short quote).** "`APEX_ALLOW_SIGNED=1 # comment` رشتهٔ کامل ذخیره می‌شود و flag را False می‌کند؛ quote بسته‌نشده در secret پذیرفته می‌شود؛ نام تکراری بی‌هشدار مقدار قبلی را جایگزین می‌کند" — inline comments stored verbatim (flag becomes False), unbalanced quotes accepted in secrets, duplicate names silently last-win.

**What I read.** `apex/config.py` `parse_dotenv` L86–119 (quote stripping only when `value[0] == value[-1]`; no comment handling after a value; `parsed[name] = value` overwrite with no duplicate check); `Config` accessors; `tests/unit/test_config.py::test_dotenv_parsing_stdlib`, `::test_dotenv_unknown_name_rejected`, `::test_dotenv_malformed_rejected` (none cover comments/quotes/duplicates).

**Reproduction.** `python3 -B AUDIT/probes_V6/A-002.py` → `.out`: `APEX_ALLOW_SIGNED=1 # comment` → value `'1 # comment'` → `Config.allow_signed == False`; `TOOBIT_API_KEY="unbalanced` → accepted, value `'"unbalanced'`; `APEX_ENV=PAPER` then `APEX_ENV=LIVE` → `{'APEX_ENV': 'LIVE'}` with no warning. Bonus: `TOOBIT_API_SECRET=abc=def=` keeps inner `=`; `" PAPER "` keeps inner spaces.

**Verdict and reasoning.** CONFIRMED on all three sub-claims. `#` inside a value without a separator is preserved (`sk#abc` → `sk#abc`) — the over-stripping variant belongs to the YAML parser (A-010), not `.env`.

**Root cause.** `parse_dotenv` implements a minimal grammar: no trailing-comment production, quote stripping without a balance check, dict assignment without duplicate detection.

**Direct impact.** A secret pasted with an unbalanced quote is silently truncated/mangled → runtime auth failure with a misleading cause; a `1 # comment` flag silently disables signed mode; duplicate keys hide conflicts.

**Secondary effects and interactions.** Downstream: adapter credentials, Telegram gateway auth, PAPER permission. Upstream: A-001 (the file may also be silently missing). python-dotenv is forbidden (ADR-P2-002/G16), so the grammar must be fixed in-tree.

**Contract and decisions.** §9.5-12 (L20505) "Parse `.env` without adding python-dotenv"; module docstring promises "Malformed lines raise ValueError (fail-closed: a broken secret file must not silently degrade)" — an unbalanced quote is a malformed line that does NOT raise, contradicting the module's own contract. No decision log entry on the grammar.

**Frozen status and non-frozen alternative.** config.py CP-1-owned (as above). No non-frozen alternative: `parse_dotenv` is the only entry point.

**Fix options.** A) Grammar hardening inside `parse_dotenv`: (i) strip a trailing comment only when preceded by whitespace AND outside balanced quotes, (ii) reject a value whose quotes don't balance, (iii) raise on a duplicate name (first-wins is the common dotenv convention; either is fine if decided). Side effects: stricter acceptance may reject currently-tolerated files (none exist in-repo; `.env` is git-ignored and device-owned — owner should be told before rollout); tests to add for each production.

**My recommendation.** A, gated by a short owner note (device `.env` must be re-validated after the change).

**Acceptance and regression tests.** Parametrized cases: value-with-inline-comment, `#` inside quotes, unbalanced single/double quotes, duplicate name (expect named ValueError), real-env precedence preserved. Existing 14 config tests must stay green.

---

## A-003

**Auditor claim (short quote).** "با وجود وعدهٔ `ValueError`، مقادیر `&base 123`، `*base`، `!!str 123`، `\|` و quote بسته‌نشده به رشته تبدیل می‌شوند. بسته‌شدن `ISSUE-CP1-008` بر ادعای رد همین syntaxها متکی است" — anchors/aliases/tags/pipe/unclosed quotes become strings instead of the promised ValueError.

**What I read.** `apex/config.py` `_parse_scalar` L234–248 (any non-matching text falls through to `return text`), `_strip_comment` L219–231, `_YamlSubsetParser._parse_node/_parse_block_map` L259–343; `PHASE2_DECISION_LOG.md:47` (ISSUE-CP1-008: "strict stdlib parser … anything outside the subset raises ValueError"); all six frozen YAMLs + the four non-frozen params files scanned for the syntax.

**Reproduction.** `python3 -B AUDIT/probes_V6/A-003.py` → `.out`: `k: &base 123` → `{'k': '&base 123'}`; `k2: *base` → string; `k3: !!str 123` → string; `k4: |` → `{'k4': '|'}` (multi-line variant fails only with a misleading "bad indentation"); unclosed `'`/`"` → strings. `---` and `? complex` DO raise ValueError. All 10 existing params YAMLs are clean of this syntax; `params/e11_classifier_v1.yaml` is absent (device-only).

**Verdict and reasoning.** CONFIRMED as to the parser behaviour. Severity lowered S1→S2: no repository file uses the syntax; the concrete exposure is a future/edited params file, and those are hash-locked by `tests/conftest.py` (six frozen YAMLs) and the content-lock test; the auditor's own status column says "reproduction limited; effects conditional".

**Root cause.** `_parse_scalar` has no reject-list for YAML sigils (`&*!|>%@``) and no unclosed-quote detection; the subset is enforced only structurally (indent/nodes), not lexically.

**Direct impact.** A corrupted or tool-generated params file loads "successfully" with wrong string values; the failure surfaces late at consumers (or never, for string-tolerant consumers).

**Secondary effects and interactions.** Downstream: any consumer of params values (risk sizing, quality tables, wire maps); interacts with A-004/A-005/A-011 (same permissive scalar path). Upstream: ISSUE-CP1-008's closure evidence is weaker than its text.

**Contract and decisions.** ISSUE-CP1-008 (decision log L47) is the governing decision and promises fail-closed rejection. Precedence: decision log > module docstring; the code currently satisfies neither.

**Frozen status and non-frozen alternative.** config.py CP-1-owned; parser fix is in-file; no external alternative (every consumer funnels through `_load_yaml`).

**Fix options.** A) Add a lexical gate in `_parse_scalar`: reject values beginning with `&`, `*`, `!`, `|`, `>` (when unquoted), and reject unbalanced quotes (mirroring A-002). Side effects: strictly narrower acceptance — all 10 in-repo YAMLs re-verified clean by probe (no semantic change); the device-only classifier artifact must be re-validated on the phone after rollout; new tests per sigil.

**My recommendation.** A (single path — the promise is already in the decision log; the code must match it).

**Acceptance and regression tests.** Each sigil and each unclosed-quote form must raise ValueError naming the line; the six frozen YAMLs must parse byte-identically (compare parsed dicts before/after — probe A-003/A-004b outputs are the baseline); full `test_config.py`/`test_cp1_foundations.py` green.

---

## A-004

**Auditor claim (short quote).** "کلید تکراری YAML بی‌هشدار overwrite می‌شود… دو تعریف `budget_per_trade: 0.005` و `budget_per_trade: 0.50` به مقدار `0.5` ختم می‌شوند؛ هم block و هم flow map. پذیرش از مسیر عمومی `_load_yaml("risk_defaults")` نیز در حافظه بازتولید شد."

**What I read.** `apex/config.py` `_parse_block_map` L317–357 (`result[key] = ...` overwrite), `_parse_flow` L397–441 (same), `_load_yaml` L444–460; callers of the loaded dicts (risk kernel `frozen_risk_params` L165–175, decision pipeline, engines/base, catalog, ingest).

**Reproduction.** `python3 -B AUDIT/probes_V6/A-004.py` (+ `A-004b.py` parent-aware scan) → `.out`s: root block duplicate → `{'budget_per_trade': 0.5}`; nested block → same; flow map `{a: 1, a: 2}` → `{'a': 2}`; via public `_load_yaml("risk_defaults")` with a temp PARAMS_DIR → `{'budget_per_trade': 0.5, 'k_attn': 0.25}`. Control: **no real params file contains a duplicate key in any mapping** (parent-aware scan of all 10 files: clean; the naive scan's hits were cross-parent false positives, e.g. `1m` under different tables).

**Verdict and reasoning.** CONFIRMED as to the parser. Severity lowered S1→S2: the six frozen YAMLs are hash-locked (`tests/conftest.py` pytest_configure/unconfigure) and content-locked (test_research_governance), so today's runtime values cannot be silently changed by an in-repo edit; the exposure is future edits and the device-produced classifier artifact.

**Root cause.** Dict assignment without a seen-key check at both mapping sites.

**Direct impact.** If a future governed edit introduces a duplicate, the silently winning value is the LAST one — the opposite of the visible-first-definition reading a reviewer would apply.

**Secondary effects and interactions.** Downstream: sizing/threshold values; upstream: governance change-proposal protocol (§17.1) whose whole point is versioned, reviewable changes.

**Contract and decisions.** §9.5-10 "params live ONLY in `params/*.yaml`" + ISSUE-CP1-008 fail-closed; no explicit duplicate-key decision. (YAML 1.2 itself treats duplicate keys as an error.)

**Frozen status and non-frozen alternative.** config.py CP-1-owned; no external alternative.

**Fix options.** A) Track seen keys per mapping scope in `_parse_block_map`/`_parse_flow` and raise ValueError with file/line. Side effects: no in-repo file is affected (verified); the classifier artifact must round-trip; a few new tests.

**My recommendation.** A.

**Acceptance and regression tests.** Duplicates at root, nested block, and flow map must raise with line info; all 10 real YAMLs parse unchanged (dict-equality baseline); existing suites green.

---

## A-005

**Auditor claim (short quote).** "تبدیل عدد بسیار بزرگ به Infinity؛ اثبات‌شده در parser؛ `x: 1e9999` به `{"x": inf}` تبدیل و در لایهٔ loader رد نمی‌شود. عبور از تمام validationهای downstream اثبات نشده است."

**What I read.** `apex/config.py` `_parse_scalar` L244–247 (`_FLOAT_RE` matches `1e9999`; `float()` → inf, no finite check), `_load_yaml` (no numeric validation); `apex/risk/kernel.py` `frozen_risk_params` L165–175 and `size` L360–432 (R_allowed = budget·capital; `q = math.floor(q / min_quantity)·min_quantity`; attention bound `k·atr_cap·capital`).

**Reproduction.** `python3 -B AUDIT/probes_V6/A-005.py` → `.out`: `_parse_scalar("1e9999") == inf`, `-1e9999 == -inf`; full document `x: 1e9999` → `{'x': inf}`; public `_load_yaml` (temp dir) returns `{'budget_per_trade': inf, ...}` with no rejection. **Beyond the auditor:** feeding that inf through the REAL sizing machine: `size(capital=10000, budget_per_trade=inf, stop_distance=100, min_quantity=0.001)` raises `OverflowError: cannot convert float infinity to integer` at kernel.py:407; `k_attn=inf` with `atr_cap=50` returns `ALLOW` with `q_attention_bound=inf` — the attention cap is silently disabled (`min` picks `q_risk`).

**Verdict and reasoning.** CONFIRMED and strengthened: the loader passes inf (as claimed), and I additionally proved two concrete downstream effects (hard crash for inf budget; silent cap disablement for inf k_attn). Severity kept at S2 (auditor S1): reaching this requires a value in a frozen, hash-locked YAML — no current file contains it (verified: all YAML values finite) — so the impact is contingent on a future governed edit or the device artifact; the crash variant is at least loud.

**Root cause.** `_parse_scalar` performs no `math.isfinite` gate after `float()`; no per-file schema/range validation exists in the loader layer.

**Direct impact.** Inf budget → `OverflowError` inside the Risk Kernel sizing path (decision-time crash); inf k_attn → attention cap neutralised (protection silently weakened).

**Secondary effects and interactions.** Downstream: sizing, hashing/serialization (`canonical_json` forbids NaN/Inf per §9.5/AI.3 — an inf value would fail later hashing); upstream: A-003 (same scalar path). Interacts with J-024 (governed-vs-YAML numbers): a "corrected" YAML typed with `1e3`-style overflows would hit this.

**Contract and decisions.** §9.5 canonical_json "forbid NaN/Inf" (L20502); §9.5-7 fail-closed; ISSUE-CP1-008 subset parser. The contract's own JSON rule implies non-finite config values are unlawful.

**Frozen status and non-frozen alternative.** config.py CP-1-owned (finite gate in `_parse_scalar`); alternative outside: per-consumer validation (risk kernel already guards `capital<=0`, `stop_distance<=0` but not inf budget) — defence-in-depth only, not a substitute.

**Fix options.** A) `math.isfinite` check in `_parse_scalar` (raise `ValueError` on non-finite results). Side effects: none for current files (all finite, verified); new tests. B) Additionally range-check the risk YAML keys in `frozen_risk_params` (non-frozen file? kernel.py is not in the frozen list — but it is risk-critical; a decision-log entry is appropriate). Side effects: a handful of validation tests; guards against any future producer of these dicts.

**My recommendation.** A now; B as a follow-up hardening.

**Acceptance and regression tests.** `1e9999`/`-1e9999`/`nan` spellings rejected at parse; `size()` unit tests for inf budget (named error, not OverflowError) and inf k_attn (cap not silently inf); all real YAMLs parse unchanged.

---

## A-006

**Auditor claim (short quote).** "flow map در ریشه اشتباه خوانده می‌شود؛ `{a: 1, b: 2}` به `{"{a": "1, b: 2}"}` تبدیل می‌شود؛ تشخیص `:` پیش از تشخیص flow node است."

**What I read.** `apex/config.py` `_parse_node` L273–304 (the `":" in content` branch runs before the `content.startswith(("[", "{"))` branch, so a root flow map is partitioned on its first colon and re-enters `_parse_block_map`).

**Reproduction.** `python3 -B AUDIT/probes_V6/A-006.py` → `.out`: `{a: 1, b: 2}` → `{'{a': '1, b: 2}'}`; `{a:1,b:2}` → `{'{a': '1,b:2}'}`; `{a: 1}` → `{'{a': '1}'}`; controls: `[1, 2, 3]` → list, `{}` → `{}`, flat flow as a VALUE (`x: {a: 1, b: 3}`) parses correctly. First content line of every real params file is a block mapping key — no practical exposure today.

**Verdict and reasoning.** CONFIRMED exactly, including the cause (order of checks).

**Root cause.** Node-type detection order in `_parse_node`; flow-collection detection happens only after the colon check.

**Direct impact.** A root-level flow mapping (valid YAML) yields a garbage single key without error → missing-key failures downstream.

**Secondary effects and interactions.** Same consumer surface as A-003; complements A-008 (nested flow) — flat flow under a key works, root flow and nested flow do not.

**Contract and decisions.** ISSUE-CP1-008 (subset includes "flow mappings"); the code accepts the token but misparses it — worse than rejecting.

**Frozen status and non-frozen alternative.** config.py CP-1-owned; no alternative.

**Fix options.** A) In `_parse_node`, test `content.startswith(("[", "{"))` FIRST and route to `_parse_flow`. Side effects: root flow maps/seqs become correct; no real file starts with one (verified); small test additions. B) Reject root-level flow collections outright (subset narrowing). Side effects: stricter; a valid-but-unused form is refused loudly.

**My recommendation.** A (subset already promises flow maps).

**Acceptance and regression tests.** `{a: 1, b: 2}` → `{'a': 1, 'b': 2}`; `{}` → `{}`; `[1,2]` → list; all 10 real YAMLs byte-identical parse.

---

## A-007

**Auditor claim (short quote).** "null نخستین کلید، ادامهٔ mapping را می‌شکند؛ ورودی دوخطی `a:` سپس `b: 2` با `trailing content` رد می‌شود؛ شاخهٔ null فقط mapping تک‌عضوی برمی‌گرداند."

**What I read.** `apex/config.py` `_parse_node` L288–301 (the `"key:"` empty-rest branch does `self._next(); return {key_part.strip(): None}` — a single-entry return that abandons sibling lines); `parse()` L265–272 (leftover line → "trailing content" ValueError).

**Reproduction.** `python3 -B AUDIT/probes_V6/A-007.py` → `.out`: `a:\nb: 2` → `ValueError: trailing content 'b: 2'`; `a: 1\nb:\nc: 3` → `{'a': 1, 'b': None, 'c': 3}` (mid/last nulls fine); `outer:\n  a:\n  b: 2` → ValueError "bad indentation" (nested variant also broken). Real files: every null-valued key (`p_min_tf:`, `freshness_threshold_seconds:`, `weights:`, `public_endpoints:`, `tick_size:`, …) is followed by a MORE-indented block, so none hit the branch.

**Verdict and reasoning.** CONFIRMED exactly (the single-entry return is the mechanism). No real file is affected.

**Root cause.** The null-value branch returns immediately instead of continuing the mapping loop.

**Direct impact.** A valid YAML file with a null key followed by a same-indent sibling is rejected with a confusing "trailing content"/"bad indentation" error.

**Secondary effects and interactions.** Parser-family cluster A-003/A-006/A-008; fail-closed direction (loud, not silent), which limits impact.

**Contract and decisions.** ISSUE-CP1-008 subset includes null scalars; the code supports them only as last/nested-block keys.

**Frozen status and non-frozen alternative.** config.py CP-1-owned; no alternative.

**Fix options.** A) In `_parse_node`, when the value is empty and the next line is NOT more indented, record `{key: None}` and continue parsing siblings at the same indent (i.e., delegate to `_parse_block_map` instead of returning early). Side effects: the branch's early `return` also serves the single-key document case — covered by the loop; no real file changes parse (verified by scan); new tests.

**My recommendation.** A.

**Acceptance and regression tests.** `a:\nb: 2` → `{'a': None, 'b': 2}`; nested variant; single `a:` → `{'a': None}`; all real YAMLs unchanged.

---

## A-008

**Auditor claim (short quote).** "nesting در flow ساختار را خراب می‌کند؛ `x: {a: [1, 2], b: 3}` خطا می‌دهد؛ `x: [[1, 2], [3, 4]]` به چهار رشتهٔ تکه‌تکه تبدیل می‌شود. split، عمق bracket/brace را دنبال نمی‌کند."

**What I read.** `apex/config.py` `_parse_flow` L397–441 and `_split_flow` L413–441 (quote-aware, bracket-depth-blind); `_parse_block_map` flow-value branch L353–355.

**Reproduction.** `python3 -B AUDIT/probes_V6/A-008.py` → `.out`: `x: {a: [1, 2], b: 3}` → `ValueError: flow map entry without ':' ' 2]'`; `x: [[1, 2], [3, 4]]` → `{'x': ['[1', '2]', '[3', '4]']}` (four string fragments, no error); `x: [{a: 1}, {b: 2}]` → strings `'{a: 1}'`; controls (flat flow) correct; unterminated flow raises. No real params file nests flow collections (verified scan).

**Verdict and reasoning.** CONFIRMED. Note the two failure shapes: nested-in-map errors (loud), nested-in-seq silently degrades to strings (the dangerous half).

**Root cause.** `_split_flow` splits on commas without tracking `[`/`{` depth; `_parse_flow` never recurses.

**Direct impact.** A tool-generated weights/vector file using nested flow silently becomes a list of junk strings consumed as scalars.

**Secondary effects and interactions.** Classifier artifact (device-produced) is the realistic future producer of structured YAML; interacts with A-003's "tool-generated file looks healthy" theme.

**Contract and decisions.** ISSUE-CP1-008: subset = flat flow maps/sequences. Nested flow is OUTSIDE the promised subset, so the correct behaviour is a loud rejection — the current silent fragmentation violates the fail-closed promise for the sequence case.

**Frozen status and non-frozen alternative.** config.py CP-1-owned; no alternative.

**Fix options.** A) Depth-aware `_split_flow` + recursive `_parse_flow`. Side effects: broadens the subset beyond the decision's text (needs a one-line decision-log addendum); more tests; risk of subtle behaviour change is low (no real file nests). B) Reject nested flow before splitting (detect `[`/`{` inside a chunk after quote-aware scan). Side effects: strictly narrower, loud; matches the current decision text exactly; no real file affected.

**My recommendation.** B first (matches ISSUE-CP1-008 verbatim, minimal risk); A only if the owner wants nested flow supported.

**Acceptance and regression tests.** Both nested forms raise ValueError; flat forms unchanged; 10 YAMLs unchanged.

---

## A-009

**Auditor claim (short quote).** "colon داخل آیتم quoted به mapping تبدیل می‌شود؛ آیتم `- "https://example.invalid"` در block sequence به دیکشنری با کلید `"https` تبدیل شد، نه رشته."

**What I read.** `apex/config.py` `_parse_block_seq` L359–395, specifically L389–392 (`elif ":" in rest:` → single-entry map, quote-blind).

**Reproduction.** `python3 -B AUDIT/probes_V6/A-009.py` → `.out`: `- "https://example.invalid"` → `{'"https': '//example.invalid"'}`; plain `- https://example.invalid` → `{'https': '//example.invalid'}` (the unquoted variant is equally broken — a nuance beyond the auditor's claim); `- "example.com:8443"` → `{'"example.com': '8443"'}`; controls `- "plain"` → `'plain'`, `- "GET /path"` → `'GET /path'`. The real `toobit_wire_v1.yaml` endpoint items (`- GET /api/v1/time` … 17 items) contain NO colon → all parse as strings.

**Verdict and reasoning.** CONFIRMED, and strengthened: even unquoted colon items degrade to maps.

**Root cause.** Inline `key: value` detection inside sequence items is quote-unaware (and unordered-vs-YAML: a plain scalar containing `: ` should not become a map without the `: ` separator rule).

**Direct impact.** Any future sequence of URL/host:port/identifier items silently becomes a list of single-entry dicts.

**Secondary effects and interactions.** `toobit_wire`-style files are the natural consumer; today's file is safe (verified item-by-item).

**Contract and decisions.** ISSUE-CP1-008 subset (quoted scalars + block sequences); the code mishandles their intersection.

**Frozen status and non-frozen alternative.** config.py CP-1-owned; no alternative.

**Fix options.** A) In the `":" in rest` branch, first check `rest` is a quoted scalar (`_parse_scalar`-style boundary detection) and treat it as a string; apply YAML's "colon followed by space/EOL" rule for the map case. Side effects: `- GET /path: x` style inline maps still work; real wire file unchanged; new tests.

**My recommendation.** A.

**Acceptance and regression tests.** Quoted/unquoted colon items stay strings; genuine inline `- k: v` items still parse as maps; `toobit_wire_v1.yaml` parse identical.

---

## A-010

**Auditor claim (short quote).** "comment در plain scalar بیش‌ازحد حذف می‌شود؛ `x: abc#def` به `{"x": "abc"}` تبدیل می‌شود؛ `#` بدون جداکننده نیز comment فرض می‌شود."

**What I read.** `apex/config.py` `_strip_comment` L219–231 (breaks at ANY unquoted `#`, no preceding-whitespace test).

**Reproduction.** `python3 -B AUDIT/probes_V6/A-010.py` → `.out`: `x: abc#def` → `{'x': 'abc'}`; `x: abc #def` → `{'x': 'abc'}`; `"ab#cd"` (quoted) → preserved; `a#b: 1` → ValueError (unsupported node 'a'); `x: {a: b#c, d: 1}` → "unterminated flow map" (a second, distinct breakage in flow+comment interaction). No real file has `#` inside a quoted value (verified).

**Verdict and reasoning.** CONFIRMED; the flow+comment case adds a second wrong-error-mode not mentioned by the auditor (still within the same root cause).

**Root cause.** Comment stripping without YAML's "preceded by whitespace" rule, applied before parsing rather than per-scalar.

**Direct impact.** Silent value truncation for any value containing `#`.

**Secondary effects and interactions.** Identifiers/metadata/hashes are the realistic victims; interacts with A-011 (same scalar handling).

**Contract and decisions.** ISSUE-CP1-008 subset includes comments — per YAML semantics a non-whitespace-preceded `#` is data.

**Frozen status and non-frozen alternative.** config.py CP-1-owned; no alternative.

**Fix options.** A) In `_strip_comment`, break only when `#` is at line start or preceded by whitespace, outside quotes. Side effects: comments glued to values become data (may surprise authors who relied on it — no in-repo instance); flow+comment then works; new tests.

**My recommendation.** A.

**Acceptance and regression tests.** `abc#def` preserved; `abc #def` stripped; quoted `#` preserved; flow map with trailing comment parses; 10 YAMLs unchanged.

---

## A-011

**Auditor claim (short quote).** "escape رشته‌های quoted اعمال نمی‌شود؛ `'it''s'` به `it''s` تبدیل می‌شود، نه `it's`؛ escape دابل‌کوت مانند `\n` نیز به همان کاراکترهای خام باقی می‌ماند."

**What I read.** `apex/config.py` `_parse_scalar` L234–237 (outer-quote strip only, no escape decoding).

**Reproduction.** `python3 -B AUDIT/probes_V6/A-011.py` → `.out`: `x: 'it''s'` → `"it''s"`; `x: "a\nb"` → literal backslash-n; `"a\\b"`, `"a\"b"` similarly raw. No real params file contains `''` or `\` (verified scan).

**Verdict and reasoning.** CONFIRMED.

**Root cause.** No escape production in the scalar parser.

**Direct impact.** String values differ from real-YAML semantics; text/identity metadata would mismatch expectations (and any hash computed over the value).

**Secondary effects and interactions.** Hash/serialization consumers; no current file uses escapes.

**Contract and decisions.** ISSUE-CP1-008 subset includes "double- and single-quoted scalars" — implicit standard escape semantics.

**Frozen status and non-frozen alternative.** config.py CP-1-owned; no alternative.

**Fix options.** A) Decode the standard minimal set: single-quote `''` → `'`; double-quote `\\ \" \n \t` (others rejected, mirroring the fail-closed style). Side effects: values change only for files using escapes (none in-repo); new tests. B) Reject any quoted scalar containing a backslash or doubled quote (narrow, loud). Side effects: stricter; blocks future legitimate use of apostrophes in single-quoted values.

**My recommendation.** A.

**Acceptance and regression tests.** `'it''s'` → `it's`; `"a\nb"` → newline; unknown escapes rejected; 10 YAMLs unchanged.

---

## A-012

**Auditor claim (short quote).** "`Params` واقعاً read-only نیست… دیکشنری cache مستقیماً برگردانده می‌شود. تغییر حافظه‌ای budget به `0.5` در همان نمونه ماند؛ نمونهٔ جدید از فایل `0.005` خواند. cache فقط per-instance است."

**What I read.** `apex/config.py` `Params.__getitem__` L463–478 (returns `self._cache[name]` directly), `load_params` L509–511 (fresh instance per call); all 38 consumer sites of `load_params()`/`Params()` (grep in apex/ + scripts/ — risk kernel, decision pipeline, engines/base, catalog, ingest, telegram, ops); mutation-assignment scan over those call sites (no `params[...] =` found).

**Reproduction.** `python3 -B AUDIT/probes_V6/A-012.py` → `.out`: `p1.risk_defaults()["budget_per_trade"] = 0.5` persists on the same instance; `load_params()` (new instance) reads 0.005; caches are per-instance; the file's sha256 unchanged. Consumer scan: no mutating consumer exists.

**Verdict and reasoning.** CONFIRMED exactly as claimed, including the "no real misuse found" caveat.

**Root cause.** The cached dict is returned by reference; no immutable view/copy; no module-level singleton (so cross-instance pollution is impossible — the audit correctly notes this).

**Direct impact.** Any future consumer that mutates a returned dict poisons every later reader within that instance (e.g. a `Params` object held for a whole run).

**Secondary effects and interactions.** Provenance: two consumers of one instance could see different values without any disk change; interacts with J-024 (governed-vs-YAML numbers) — a mutation would be invisible to `assert_yaml_consistency`.

**Contract and decisions.** Docstring: "Read-only view of the six frozen parameter YAMLs … the loader never mutates" (the loader doesn't; the VIEW is mutable). §9.5-10 values exist only in params/*.yaml — an in-memory mutation breaks that invariant silently.

**Frozen status and non-frozen alternative.** config.py CP-1-owned. Non-frozen alternative: consumers can deep-copy at their boundary (e.g. `frozen_risk_params()` already copies selected keys into a NEW dict — a partial mitigation that exists today).

**Fix options.** A) Return a defensive deep copy (or a `MappingProxyType`-over-deep-copy) from `__getitem__`. Side effects: per-access copy cost (params are small — negligible); any consumer relying on identity (`p["x"] is p["x"]`) would change (none exists); tests unaffected. B) Document mutation as forbidden + add a runtime canary (hash check on each access). Side effects: cheaper but weaker.

**My recommendation.** A.

**Acceptance and regression tests.** Mutating a returned dict must not affect a subsequent access on the same instance; `load_params()` twice still reads the file values; existing suites green.

---

## A-013

**Auditor claim (short quote).** "فایل اسرار با نام سفارشی الزاماً ignore نمی‌شود… `.env` ignored است؛ `.env.paper`، `.env.live` و `config/production.env` نیستند. افشای واقعی مشاهده نشد."

**What I read.** `.gitignore` L1–12 in full; `README.md` L52–53 ("`--env-file PATH` selects another file explicitly"); `scripts/run_apex.py` L1088–1089; ADR-P2-013 (decision log L39: nothing else may be added to `.gitignore` without a DECISION_LOG note).

**Reproduction.** `python3 -B AUDIT/probes_V6/A-013.py` → `.out` (uses `git check-ignore -v`, read-only): `.env` IGNORED (`.gitignore:4:.env`); `.env.paper`, `.env.live`, `.env.production`, `config/production.env`, `secrets/env.txt`, `params/env.local`, `prod.env`, `.envrc` all NOT ignored. No such file exists in the worktree (disclosure not observed — as the auditor said).

**Verdict and reasoning.** CONFIRMED. The pattern `.env` matches exactly one name; the documented `--env-file` feature invites custom names.

**Root cause.** Single-name ignore pattern combined with an arbitrary-path CLI option.

**Direct impact.** A credential file with a custom name inside the repo can be `git add`ed accidentally.

**Secondary effects and interactions.** Exposure paths: PRs, history, snapshots, hand-off to other agents; interacts with A-001 (custom path silently missing) and J-002/D17 (secrets live ONLY in the phone's `.env`).

**Contract and decisions.** §2.5 key custody ("never in the repository"); D17 ("Secrets … live ONLY in the phone's .env (git-ignored)"); ADR-P2-013 governs `.gitignore` changes (needs a log note).

**Frozen status and non-frozen alternative.** `.gitignore` is not frozen but is ADR-P2-013-governed (change requires a DECISION_LOG note — that is the mechanism, not a blocker).

**Fix options.** A) Add `.env*` (or an explicit allow-listed negative pattern) to `.gitignore` with the ADR-P2-013 log note; optionally enforce secrets-outside-repo in `run_apex.py` (warn/refuse when `--env-file` resolves inside the repo). Side effects: `.env.example`-style docs would need `!` negation; the run_apex guard is a behaviour change for anyone legitimately keeping an env file in-repo (should be refused anyway).

**My recommendation.** A.

**Acceptance and regression tests.** `git check-ignore` must cover `.env.*`/`.env*` variants; a test that a repo-root env file triggers the CLI warning/refusal.

---

## A-014

**Auditor claim (short quote).** "اعتبارسنجی change-proposal فقط presence-check است؛ approval با `OOS=False` و دورهٔ صفر و رشتهٔ `NA` پذیرفته می‌شود… عدم ارائهٔ evidence اصلاً بررسی نمی‌شود."

**What I read.** `apex/research/governance.py` `validate_change_proposal` L237–283 (checks keys presence, `approval is True`, `rollout_period >= 1`, `risk_check in {None,"",[]}` missing-detection — none check quality); `ApeXChangeProposal` dataclass L139–166; `draft_package` L285–330 (validation NOT required: `if validate: ...`); callers: `tests/unit/test_research_governance.py` and probe-only usage in the repo (no runtime/ops caller). `APEX_GEN5.md` L17100–17124 (§17.1 change-proposal protocol: "evidence table", "one OOS round of hard evidence", "max 30-day rollout").

**Reproduction.** `python3 -B AUDIT/probes_V6/A-014.py` → `.out`: a proposal with `approval="yes"` (string, not bool) passes; `approval=None` fails; `rollout_period=0` passes; `rollout_period="NA"` passes; `rollout_period=""` fails; `oos=False` passes (bool False is "present"); `risk_check="NA"` passes; `evidence=[]` passes; `evidence` missing key passes (key not required at all). A fully unevidenced proposal → `DRAFT` package written under `params_suggestions/`.

**Verdict and reasoning.** CONFIRMED. Severity lowered S1→S2: the reach of this row alone is the research seam — `draft_package` writes a SUGGESTION file under `params_suggestions/` and never the live `params/` directory (enforced by `assert_live_params_untouched` L97–108 and the injection ledger flow). The combination A-014+A-015+A-016 is what makes an unevidenced package injectable — each row's own increment is bounded accordingly (A-015 carries the S1).

**Root cause.** The validator implements presence/emptiness checks (`None, "", [], {}` are the only "missing" markers) rather than typed quality assertions; booleans and strings pass truthiness-free presence tests.

**Direct impact.** A garbage proposal reaches DRAFTED; a reviewer trusting "VALIDATED" downstream may treat it as evidence-backed when nothing was checked.

**Secondary effects and interactions.** Downstream: `promote_package`'s paper-trial gate (T-PKG-001) at least requires a paper trial record; A-015's nested RED LINE gap can neutralise even that; A-016 makes injection possible without validation. Upstream: §17.1 protocol assumes the proposal's evidence table is meaningful.

**Contract and decisions.** §17.1 (L17100–17124) is the governing contract: proposal must include "an evidence table" and OOS hard evidence; rollout "max 30 days". The code enforces presence, not content — a contract-compliance gap rather than a decision conflict (no decision relaxes §17.1).

**Frozen status and non-frozen alternative.** `governance.py`/`promotion.py` are NOT among the frozen files (frozen research files are `bootstrap.py` and `backtest.py` only). Direct fix is in-file.

**Fix options.** A) Tighten `validate_change_proposal`: require `approval is True` (bool identity), `isinstance(rollout_period, int) and 1 <= rollout_period <= 30`, `isinstance(oos, bool)`, non-empty `evidence` list of dicts with required fields, `risk_check` present with at least one entry. Side effects: `tests/unit/test_research_governance.py::test_change_proposal_validation_*` fixtures must be updated (several use `rollout_period=7`, real booleans — mostly compatible); stricter behaviour is exactly the intent; add rejection tests.

**My recommendation.** A.

**Acceptance and regression tests.** Every probe case must flip to rejection; existing governance tests updated and green; draft still possible with `validate=False` (explicit escape hatch preserved for tests).

---

## A-015

**Auditor claim (short quote).** "RED LINE با اضافه‌کردن یک لایه nesting دور مقدار مجاز bypass می‌شود؛ `risk_check: - {line_id: PAPER_ONLY, value: [BYPASS]}` … `red_line_clean=True` برمی‌گردد؛ هم‌زمان کلیدهای ناشناخته پاس می‌شوند."

**What I read.** `apex/research/governance.py` `validate_package` L332–431: `red_line_clean` computed by flattening `risk_check` and testing leaf values against RED LINE strings/numerics (L370–381: membership on leaf strings like "PAPER_ONLY", "NEVER"), nested lists containing forbidden tokens are not flattened to those tokens — a wrapped `[BYPASS]` leaf is checked as a list, not as the string `BYPASS`; `params_flat = flatten(params)` and unknown-key check exists for params but the audit's point is the risk_check side; `promote_package` L536–562 AND-gates on `validation["red_line_clean"]`.

**Reproduction.** `python3 -B AUDIT/probes_V6/A-015.py` → `.out`: flat forbidden values (`{line_id: PAPER_ONLY, value: BYPASS}` with `value: PAPER_ONLY`-style literal, `risk_check=[{...value: 9.9}]` with 9.9 in a numeric-forbidden set) are correctly rejected; but `risk_check=[{line_id: PAPER_ONLY, value: [BYPASS]}]` (extra list layer) returns `red_line_clean=True` and `promote_package` proceeds; unknown top-level keys in the package (`{"-": "-"} {meta, params, risk_check, mystery_key}`) pass without warning.

**Verdict and reasoning.** CONFIRMED at S1 (agreed): this is the row that converts A-014's presence-only proposals into a paper-trial gate that a malformed (or adversarial) package can satisfy. The paper-trial gate `T-PKG-001` ANDs on `red_line_clean`, so its integrity is the protection.

**Root cause.** Leaf-value type assumption in the RED LINE check (expects scalars; lists pass through), and the unknown-key check covers `params` but not `risk_check` entries' shapes.

**Direct impact.** A nested RED LINE value bypasses the only automated veto between DRAFTED and paper-trial promotion; downstream the paper trial itself (CP-15) is still required for promotion, but the RED LINE contract (§17.1) is not machine-enforced.

**Secondary effects and interactions.** Upstream: A-014 (proposals unchecked). Downstream: `promote_package` gate. The audit's own "bypass test on a flat nested list" is reproduced exactly.

**Contract and decisions.** §17.1 RED LINE (L17100–17124): "risk_check entries … one per RED LINE item, with the value the package actually uses"; no decision relaxes the RED LINE. W.5 (L16395–99): "risk_check … The Risk Kernel RED LINE values must be listed and must NOT be relaxed."

**Frozen status and non-frozen alternative.** governance.py not frozen; fix in-file.

**Fix options.** A) Make the RED LINE check recursively unwrap single-level lists (and reject unexpected structure: value must be scalar or explicitly-typed list with per-element checks); reject unknown package keys; reject `risk_check` entries whose `line_id` is not in the RED LINE registry. Side effects: `tests/unit/test_research_governance.py` fixtures use flat values (compatible); probes A-015 cases become rejections (intended); a handful of new tests.

**My recommendation.** A.

**Acceptance and regression tests.** Nested `value: [BYPASS]` must be rejected; flat correct entries still pass; unknown package/entry keys rejected; full research-governance suite green.

---

## A-016

**Auditor claim (short quote).** "`injector.inject` بدون `validate=True` قابل اجراست؛ تزریق واقعی روی دیسک انجام می‌شود… همان `package_id` با هش متفاوت با خروجی `no_op` بی‌صدا ختم می‌شود، بدون ثبت نمونهٔ دوم یا خطا."

**What I read.** `apex/research/governance.py` `InjectionLedger` L528–562 and `inject` L564–627: `inject(package, package_dir, validate=False)` runs the write path (copies suggestion + appends ledger row) without calling validation; duplicate `package_id` with different `content_hash` → `_seen_packages` short-circuits `return "no_op"` without recording the second instance or warning. `assert_live_params_untouched` L97–108 (params/ guarded — `git status --porcelain params/` must be empty after injection).

**Reproduction.** `python3 -B AUDIT/probes_V6/A-016.py` (temp ledger dir + temp package dir; real governance module) → `.out`: inject with `validate=False` writes the suggestion file and one ledger row (id, package_id, decision=SUGGEST, hash) and `params/` is untouched (guard passes); second inject with same `package_id`, different content → returns `no_op`, ledger still has ONE row, no warning, second content never recorded; inject of an APPROVED-but-unvalidated package also succeeds (validation skipped); ledger file path is accepted as-is (see A-017).

**Verdict and reasoning.** CONFIRMED. Severity lowered S1→S2: the injection seam is research-plane only — it writes `params_suggestions/<...>.yaml` + `state/injection_ledger.csv`, never live `params/` (guard verified in-probe); no runtime code path calls `inject` (grep: only tests + probes). The idempotency no-op is a provenance/integrity defect of the research ledger, not a trading-path defect.

**Root cause.** `validate` default False at the API boundary; `_seen_packages` keyed by `package_id` alone (not id+hash), with silent early return.

**Direct impact.** Two different payloads under one `package_id` — the second silently vanishes; an auditor reading the ledger sees one hash and believes it is THE content.

**Secondary effects and interactions.** Downstream: promotion/promotion decision records; upstream: A-014/A-015 (what counts as validated). Combined chain: unevidenced package → draft (A-014) → nested RED LINE clean (A-015) → injectable without validation (A-016) — the reason this cluster is serious even though each seam is research-plane.

**Contract and decisions.** §17.1: "packages are content-addressed; the ledger records every injection attempt"; T-PKG-001; the ledger is the provenance chain for the governed-change protocol. No decision permits silent no-op on hash mismatch (silent no-op is reasonable for a TRUE duplicate — same id AND same hash).

**Frozen status and non-frozen alternative.** governance.py not frozen; fix in-file.

**Fix options.** A) (i) Default `validate=True` (or refuse `validate=False` outside tests via an explicit `allow_unvalidated` flag); (ii) key `_seen_packages` by `(package_id, content_hash)`: identical pair → no_op; same id, different hash → raise/warn and record a REJECTED row. Side effects: tests calling inject without validation must pass the explicit flag (a few); ledger gains a rejection record type (schema is append-only CSV — new decision value is additive).

**My recommendation.** A.

**Acceptance and regression tests.** Same-id-same-hash → no_op (idempotent retry, unchanged); same-id-different-hash → recorded rejection + non-silent error; validate=False requires the explicit flag; `assert_live_params_untouched` still enforced.

---

## A-017

**Auditor claim (short quote).** "مسیر ledger با user input تعیین می‌شود؛ path traversal آزموده نشد اما هیچ اعتبارسنجی مسیر وجود ندارد."

**What I read.** `apex/research/governance.py` `InjectionLedger.__init__` L528–536 (`self.path = path` — no containment check), `inject` (writes `self.path` via append + package_dir copy); callers: `tests/unit/test_research_governance.py` (temp dirs), no runtime caller.

**Reproduction.** `python3 -B AUDIT/probes_V6/A-017.py` → `.out`: `InjectionLedger(path=Path("/tmp/../etc/exploit_ledger.csv"), research_root=tmp)` is accepted without complaint (no validation at construction; the probe then uses a harmless /tmp target for the write itself to stay read-only outside AUDIT/temp); a same-name check shows the constructor accepts absolute paths outside `research_root`, `..` segments, and symlinked parents.

**Verdict and reasoning.** CONFIRMED (constructor accepts arbitrary paths; no validation exists). S2 agreed: research seam, no runtime caller, the realistic misuse is a misconfigured ops script writing the ledger somewhere unexpected — integrity/observability, not a trading fault.

**Root cause.** No path normalisation/containment at the API boundary.

**Direct impact.** A ledger can be redirected anywhere the process can write; provenance chain becomes unauditable if the path is wrong.

**Secondary effects and interactions.** Interacts with A-016 (ledger integrity); the threat model is internal tooling, not a remote attacker.

**Contract and decisions.** §17.1 provenance requirements (ledger must reflect reality); no decision governs the path.

**Frozen status and non-frozen alternative.** governance.py not frozen; fix in-file.

**Fix options.** A) Resolve and require `ledger_path.resolve().is_relative_to(research_root.resolve())` (Python 3.11 API, available — runtime floor is 3.11 per pyproject `requires-python`), reject otherwise; same for `package_dir`. Side effects: tests using temp dirs inside a tmp research root pass; any out-of-root caller (none in-repo) breaks loudly.

**My recommendation.** A.

**Acceptance and regression tests.** Out-of-root and `..`-escaping paths raise; in-root paths unchanged; existing governance tests green.

---

## A-018

**Auditor claim (short quote).** "کیفیت هیچ ECEntry تایید نمی‌شود؛ `validate=False` می‌گذرد؛ مقدار خارج از بازه در APPROVED فعال است… اعتبارسنجی نه در سیستم روتین است و نه در پروتکل."

**What I read.** `apex/research/governance.py` `ECRegister` L430–526 (`register(entry)` appends without quality validation; `active_value()` returns the last APPROVED entry's value with no bounds check), callers (grep: only `validate_ec` in tests and the register API — no runtime consumer reads `active_value`).

**Reproduction.** `python3 -B AUDIT/probes_V6/A-018.py` → `.out`: `register` accepts an APPROVED entry with `value=2.0` for an EC whose documented bounds are `[0, 1]` (bounds are advisory — never consulted); `active_value` returns 2.0; `validate=False` path never triggers; nothing in `apex/` or `scripts/` reads `active_value` at runtime.

**Verdict and reasoning.** CONFIRMED. S2 agreed: the register is a research-plane record with no runtime consumer; its failure mode is false closure/future misuse rather than a current trading fault.

**Root cause.** Register is a passive log; bounds/typing/decision linkage are not part of `register` or `active_value`.

**Direct impact.** An "APPROVED" out-of-bounds constant would be treated as authoritative if a future consumer wires `active_value` in.

**Secondary effects and interactions.** Upstream: the EC protocol (§17.1) expects experiment-constant changes to be governed; downstream: nothing today.

**Contract and decisions.** §17.1 EC register protocol (L17138): entries must cite decisions and stay within the constant's documented domain. No decision relaxes it.

**Frozen status and non-frozen alternative.** governance.py not frozen; fix in-file.

**Fix options.** A) Validate at register: decision_id exists and is not superseded; value within the constant's documented bounds (encode a small EC table in governance.py); refuse `validate=False` outside tests. Side effects: only future callers affected; a few tests to add.

**My recommendation.** A.

**Acceptance and regression tests.** Out-of-bounds APPROVED entry rejected; bounded one accepted; `active_value` never returns an out-of-domain value.

---

## B-001

**Auditor claim (short quote).** "wheel در setuptools 66.1.1 با ۴ فایل پایتونی ساخته می‌شود؛ engines/, execution/, telegram/, ops/ و پوشهٔ params/ وجود ندارند؛ import به `ModuleNotFoundError` می‌خورد… بیلد با backend مصوب (≥68) آزمایش نشده است."

**What I read.** `pyproject.toml` (full): `[build-system] requires = ["setuptools>=68"]`, `[tool.setuptools] packages = ["apex", "apex.config"]` with `package-dir = {"": "."}` and `package-data = {"apex.config" = ["*.yaml", "j2.py"]}` — only `apex/` top-level modules and the `apex/config` package are declared; `MANIFEST.in` absent; `apex/` directory tree (engines, execution, telegram, ops, data_catalog, research, decision, risk subpackages exist on disk but are NOT declared packages); `README.md` "Install"; ADR-P2-002 (decision log) pins the packaging approach.

**Reproduction.** `python3 -B AUDIT/probes_V6/B-001.py` → `.out` (+`B-001b.py` for the approved-backend variant): `python3 -m build --wheel` in a temp copy (repo untouched) with setuptools 66.1.1 → wheel contains 102 files of which **4 are `.py`**: `apex/__init__.py`, `apex/config/__init__.py`, `apex/config/j2.py`, and `apex/config/params.py` (module) — plus the 11 YAML `package-data` files. No `apex/engines/`, `apex/execution/`, `apex/telegram/`, `apex/ops/`, no `params/`. Isolated rebuild with the **approved backend** (setuptools 68+: `pip install build` into a venv with setuptools>=68) produces the SAME 4-file wheel — the auditor's open question ("untested with ≥68") is answered: same defect. Fresh-venv install of the wheel: `import apex.decision.pipeline` → `ModuleNotFoundError: No module named 'apex.decision'`; `apex.config.Config()` → `FileNotFoundError` on `params/` (params not shipped); `python -c "import apex; print(apex.__file__)"` works only for the stub.

**Verdict and reasoning.** CONFIRMED and strengthened (approved-backend build tested: identical). S1 agreed: the wheel is the G16 deliverable artifact for the owner's Termux device; as built, `pip install` yields a package that cannot run `serve`/`boot` — the owner following `README` "Install" gets a broken system.

**Root cause.** `[tool.setuptools] packages` lists only `["apex", "apex.config"]` instead of package discovery over `apex.*` (e.g. `find:` with `include = ["apex*"]`), and `params/` is neither a package nor data. NOTE: the six frozen YAMLs are the runtime authority and live in `params/` — shipping them inside the wheel would need an owner decision (they are also hash-locked against the repo state).

**Direct impact.** Termux deployment via wheel is impossible; only `git clone` + in-tree execution works (which is what the phone runbooks actually do — J-012's commands run from the repo, mitigating real-world impact to "artifact-level broken, workflow unaffected").

**Secondary effects and interactions.** README install section promises a working wheel; interacts with B-002 (dependency check runs before any import error would be seen). Frozen constraint: `requirements.lock` is FROZEN — fixing packaging must not add build-time pins to it (build backend requires are in pyproject, which is not frozen).

**Contract and decisions.** ADR-P2-002 governs packaging; G16 (Termux-first) requires the delivered artifact to run. The wheel as built violates the delivery requirement.

**Frozen status and non-frozen alternative.** `pyproject.toml` not frozen. `requirements.lock` frozen (do not touch; setuptools>=68 belongs in `[build-system].requires` which is separate — and is already there).

**Fix options.** A) Switch to package discovery: `[tool.setuptools.packages.find] where = ["."], include = ["apex*"]` (picks up all `apex.*` subpackages; excludes tests/scripts/AUDIT); decide on `params/` shipping separately (owner ruling: either ship as data with hash tests adjusted, or document clone-based install as the only supported path and drop the wheel promise). Side effects: wheel grows to ~100+ modules — verify no test imports break; the six frozen YAMLs must remain byte-identical (hash-lock tests run against the repo, not the wheel — unaffected); e11 artifact remains device-only (correct). B) Ship a source distribution only (`sdist`) with a documented `pip install .` from the repo directory. Side effects: still needs correct package discovery (same fix core); no binary artifact to audit.

**My recommendation.** A, with the explicit owner decision on `params/` data shipping.

**Acceptance and regression tests.** Build wheel in temp; assert `apex/engines`, `apex/execution`, `apex/telegram`, `apex/ops`, `apex/data_catalog`, `apex/research`, `apex/decision`, `apex/risk` are present; fresh-venv install then `import apex.decision.pipeline` succeeds; `python3 scripts/run_apex.py status` runs to its config-loading refusal (not ImportError); params presence decision documented.

---

## B-002

**Auditor claim (short quote).** "بررسی نسخه‌ها در بوت فقط `__import__` و `getattr` است؛ stubهای 0.0.1 همه را پاس می‌کنند؛ وجود ماژول معیار است نه نسخهٔ pin شده."

**What I read.** `apex/execution/fsm.py` `_check_dependencies` L39–57 (`__import__(mod)` in try/except → ImportError caught; no version introspection); callers: `BootFSM.__init__`/`boot()`; `requirements.lock` (9 pins); `tests/unit/test_boot_fsm.py` (uses monkeypatched modules, consistent with presence-only checking).

**Reproduction.** `python3 -B AUDIT/probes_V6/B-002.py` → `.out`: the real `_check_dependencies` accepts fake modules injected into `sys.modules` with `__version__ = "0.0.1"` for all nine pins (numpy, pandas, pydantic, aiohttp, aiogram, aiosqlite, matplotlib, python-dateutil, pytz) → returns OK/READY; no version string is consulted. Reading the real environment: `pip list` shows the nine pins at their locked versions (this session installed them), so the real device check passes for the right reason here.

**Verdict and reasoning.** CONFIRMED. S2 agreed: the boot gate checks presence, not the lock; a divergent environment (e.g. numpy 2.x on Termux) boots and fails later with confusing runtime errors instead of a named refusal.

**Root cause.** Dependency gate predates/omits `importlib.metadata.version` comparison.

**Direct impact.** Version drift on the phone is undetected at boot — the "single runtime" promise (requirements.lock, README "Runtime pin") is unenforced.

**Secondary effects and interactions.** Downstream: numpy 2.0 incompatibilities, pandas API drift — surface as engine crashes, not boot refusals. Constraint: requirements.lock is FROZEN — the fix must use stdlib `importlib.metadata` (Python 3.11 stdlib), not a new dependency.

**Contract and decisions.** Ch.1 SBOM (L96–107): nine pins are the runtime; G16 fail-closed boot; README:10 "Runtime pin: numpy==1.26.0 (requirements.lock)".

**Frozen status and non-frozen alternative.** `apex/execution/fsm.py` not frozen; `requirements.lock` frozen (untouched by the fix — stdlib only).

**Fix options.** A) In `_check_dependencies`, after import, compare `importlib.metadata.version(dist)` against the pin table (a literal dict inside fsm.py — no file added to the lock); refuse with `DEPENDENCY_VERSION_MISMATCH` naming both versions. Side effects: dev environments running slightly newer patches would be refused (strictness is the intent — matches `==` pins); the pins must be kept in sync with the lock by a test (read requirements.lock in a test, compare to the literal).

**My recommendation.** A.

**Acceptance and regression tests.** A 0.0.1 stub for each dependency must fail boot with the mismatch message; the true locked versions pass (probe already proves the mechanism); a sync test lock↔table.

---

# J-rows — internal documentation conflicts

For every J-row: both conflicting passages are quoted with line numbers, `PHASE2_DECISION_LOG.md` was searched for a resolving decision (search terms per row below), and each is classified as **resolved by decision** / **documentation-only** / **runtime-relevant**.

## J-001

**Auditor claim (short quote).** "README به‌عنوان نقطهٔ شروع، در نقطهٔ ورود ۹ دستور اصلی را پوشش نمی‌دهد؛ ۶ دستور run_apex.py در README نیستند؛ bootstrap هیچ‌جا در README ذکر نشده. ارجاع مستقیم به runbook مشکل را حل می‌کند."

**What I read.** `README.md` in full (commands documented: `alerts`, `boot`, `demo`, `grid` + `python -m unittest` + `pytest` + `python scripts/run_apex.py --help` pointer); `scripts/run_apex.py` argparse (`add_subparsers` → 10 commands: alerts, boot, bootstrap, demo, grid, publish-quality-backfill, repair-partial, serve, status, train-e11); `PHASE2_HANDOFF_CP9.md` L60–75 (the CP-9 handoff runbook: all six missing commands present with full invocations); `PHASE2_GLOBAL_DIRECTIVES.md` G16 ("ONE clear run procedure").

**Reproduction.** `python3 -B AUDIT/probes_V6/J-001.py` → `.out`: argparse choices = 10 commands; README contains `run_apex.py <cmd>` for exactly 4 of them (alerts/boot/demo/grid); missing 6: bootstrap, publish-quality-backfill, repair-partial, serve, status, train-e11; `PHASE2_HANDOFF_CP9.md` contains all six missing invocations. README's `--help` pointer exists (L66) but G16 requires a single explicit run procedure at the entry point.

**Verdict and reasoning.** CONFIRMED. The audit's own caveat ("CP-9 handoff documents them; the gap is README-as-entry-point") is accurate — I verified both halves.

**Root cause.** README (CP-1 deliverable) written before the CP-9/CP-14 CLI surface matured; never updated.

**Direct impact.** A new operator starting from README cannot reach serve/bootstrap/status/train-e11 without discovering the handoff file; G16's "ONE clear run procedure" is satisfied only by reading two documents.

**Secondary effects and interactions.** Interacts with J-012 (phone procedure pulls a stale branch — the combination is the real onboarding hazard).

**Contract and decisions.** G16 (PHASE2_GLOBAL_DIRECTIVES.md:36): "The final system must execute on the owner's single Termux/Android device; the delivery includes ONE clear run procedure". README is the natural entry point.

**Frozen status and non-frozen alternative.** README not frozen.

**Fix options.** A) Add a "Commands" table to README listing all 10 commands with one-line purpose + pointer to the CP-9 runbook for full procedures. Side effects: none; README tests (none exist for command coverage) unaffected; add a tiny test that parses run_apex's argparse choices and diffs them against README's table to prevent recurrence.

**My recommendation.** A.

**Acceptance and regression tests.** A unit test: `set(subparser choices) == set(commands documented in README)`.

Classification: **documentation-only** (no runtime effect; no decision resolves it).

---

## J-002

**Auditor claim (short quote).** "docstring می‌گوید «exactly and only nine»؛ پارسر هر نام دیگری را می‌پذیرد و استفاده از آن در DOCSTRING مجاز شمرده شده است؛ APEX_DOTENV_PATH نام دهم است."

**What I read.** `apex/config.py` module docstring (L1–18): "Parses exactly and only the nine environment variables listed in §2.5"; `parse_dotenv` L106–116 (accepts ANY name, only warns for unknown); `Config.__init__`/`_load_env` (`APEX_DOTENV_PATH` read at L100–104 — a tenth name); `PHASE2_DECISION_LOG.md:203` (D13: "`APEX_DOTENV_PATH` stays env-only, never a CLI flag" — the tenth name is sanctioned) and ISSUE-CP8-004 context.

**Reproduction.** Reading-only row (verified by direct inspection, no probe needed): docstring quoted above; code accepts arbitrary names with a warning; `APEX_DOTENV_PATH` is used by `_load_env` itself. D13 explicitly keeps `APEX_DOTENV_PATH`.

**Verdict and reasoning.** CONFIRMED. The docstring's "exactly and only nine" is false in both directions (a tenth name exists by decision; other names are tolerated with a warning).

**Root cause.** Docstring written for the §2.5 nine-name contract; D13's env-only loader path and the tolerance behaviour were never reflected.

**Direct impact.** None at runtime; a reader/maintainer may believe unknown names are rejected when they are not (connects to A-002/A-003 reality).

**Secondary effects and interactions.** Documentation trust; pairs with A-013 (custom env FILE names also possible).

**Contract and decisions.** D13 (L203) governs: `APEX_DOTENV_PATH` is legitimate. Docstring must be updated to match the decision.

**Frozen status and non-frozen alternative.** config.py CP-1-owned — a docstring-only edit is still a file change; batch it with the parser fixes (A-002/A-003) under one decision entry.

**Fix options.** A) Docstring edit: "nine §2.5 names plus `APEX_DOTENV_PATH` (D13); unknown names are parsed with a warning". Side effects: none.

**My recommendation.** A.

**Acceptance and regression tests.** A doctest or simple assertion test on the docstring text mentioning APEX_DOTENV_PATH.

Classification: **resolved by decision (D13)** + documentation-only residual.

---

## J-003

**Auditor claim (short quote).** "full_id برای F70 و F71 یکسان است (`APEX.L00.ATOM.CNDL.CD-3.RATIO.V1`)؛ کلید یکتا catalog با full_id است؛ خطای شناخت دوتایی برای یک full_id وجود ندارد."

**What I read.** `apex/data_catalog/catalog.py` `register` L80–92 (`_by_full_id[contract.id.full_id] = contract` — same-id assignment overwrites or coexists silently depending on container), `FeatureID` dataclass (no `num` field — verified); the catalog build; `tests/unit/test_catalog.py` (74 features registered); `APEX_GEN5.md` §3.12/§3.13 (L7080–7160): F70 = `CD-3 RATIO` (directional candle body ratio), F71 = `CD-3R RATIO` (directional range candle ratio) — two distinct concepts, both described with the same full_id string in the frozen contract text.

**Reproduction.** `python3 -B AUDIT/probes_V6/J-003.py` → `.out`: `build_registry()` returns 74 contracts; `len(set(full_id for all)) == 73`; the colliding full_id is `APEX.L00.ATOM.CNDL.CD-3.RATIO.V1` used by **F70 and F71**; `_by_full_id` lookup for that id returns F71 (last registration wins); no error/warning is raised at build time. The duplicate is inherited verbatim from the frozen contract (§3.13 table lists the same full_id on both rows).

**Verdict and reasoning.** CONFIRMED. The registry is internally consistent (74 distinct FeatureID objects; `FeatureID` has no numeric component at all), but the human-facing identity (full_id) is duplicated — lookup by full_id is ambiguous.

**Root cause.** The frozen §3.13 table assigns the same full_id to two different features; the registry copies the text faithfully.

**Direct impact.** Any consumer doing `_by_full_id["APEX...CD-3.RATIO.V1"]` silently gets one of the two (F71); ambiguity is invisible.

**Secondary effects and interactions.** Downstream: governance/promotion reference features by full_id in packages; a proposal referencing the shared id is ambiguous. Upstream: the frozen contract text itself. (Related new finding X-V6-001: `_by_num` — a dead index — is ALSO keyed by full_id.)

**Contract and decisions.** §3.13 (frozen content): both rows carry the same id — the defect is in the frozen text; fixing requires an owner ruling on which feature gets a new id (e.g. `CD-3R.RATIO.V1` for F71), plus a DECISION_LOG entry; `apex/data_catalog/**` is FROZEN — any fix needs explicit owner approval.

**Frozen status and non-frozen alternative.** catalog.py FROZEN (apex/data_catalog/**); the contract text §3.13 is part of APEX_GEN5.md (D2-patchable with AJ traceability row). No non-frozen alternative — the registry is the only build path.

**Fix options.** A) Owner ruling: assign F71 a distinct full_id (e.g. `...CNDL.CD-3R.RATIO.V1`), patch §3.13 under D2 with an AJ row, then update catalog.py (frozen-file change, one literal). Side effects: any stored artifact referencing the old id (device snapshots, suggestion files) needs a migration note; registry tests updated; duplicate detection test added.

**My recommendation.** A, as a single owner-approved change (contract text + registry together).

**Acceptance and regression tests.** `len(set(full_id)) == len(contracts) == 74` assertion in test_catalog; lookup-by-full-id uniqueness test.

Classification: **documentation-only** today (no runtime consumer resolves by full_id ambiguously — `resolve` used in engines is by feature identity object; the runtime risk is future consumers).

---

## J-004

**Auditor claim (short quote).** "§3.13 برای هر feature قید parameters/consumers/tests دارد؛ قراردادِ runtime این فیلدها را ندارد؛ validation مربوطه در catalog.py یک no-op است… F73/F74 بدون این فیلدها PASS می‌شوند."

**What I read.** `apex/data_catalog/catalog.py` `validate_contracts` L100–140 (loops checking `contract.id`/`contract.kind`/formula presence — no parameters/consumers/tests checks exist), `FeatureContract` dataclass L20–78 (fields: id, kind, formula, evidence_window, min_history, quality_flags — NO parameters/consumers/tests); `APEX_GEN5.md` §3.13 (L7160–7200: per-feature rows with parameters/consumers/tests columns — F73/F74 rows have these cells filled in the text); `tests/unit/test_catalog.py` (gutted fixtures: F73/F74 registered without those fields and the suite passes).

**Reproduction.** `python3 -B AUDIT/probes_V6/J-004.py` → `.out`: `FeatureContract` has no parameters/consumers/tests attributes (`dataclasses.fields` enumerated); `validate_contracts` returns OK for a contract set lacking them; the F73/F74-style minimal contracts pass; §3.13's own rows DO carry parameters/consumers/tests text (quoted).

**Verdict and reasoning.** CONFIRMED. The runtime contract is a strict subset of the documented contract; the documented fields are aspirational.

**Root cause.** Contract dataclass implemented for the fields the engines actually need; §3.13's governance columns never encoded.

**Direct impact.** The "parameters/consumers/tests" traceability promised per feature does not exist in machine-checkable form; F73/F74 (and in fact ALL features) pass without it.

**Secondary effects and interactions.** Traceability matrix claims (J-005 adjacent); promotion/governance cannot machine-verify consumer wiring.

**Contract and decisions.** §3.13 (frozen text) is the contract; no decision relaxes it. apex/data_catalog/** is FROZEN — adding fields to the dataclass is a frozen-file change needing owner approval.

**Frozen status and non-frozen alternative.** catalog.py + contracts (data_catalog package) FROZEN. Non-frozen alternative: a sidecar mapping (e.g. a JSON under AUDIT or docs) that test_catalog.py cross-checks against §3.13 — but test files are non-frozen, so a TEST asserting the documented columns exist in a sidecar could enforce traceability without touching the frozen package. (Weaker: sidecar can drift.)

**Fix options.** A) Owner-approved frozen-file change: add optional `parameters/consumers/tests` fields to `FeatureContract` + a `validate_contracts` check that they are non-empty for all 74. Side effects: every `register()` call gains three literals (74 edits inside the frozen file); governance tests extended. B) Non-frozen sidecar + test cross-referencing §3.13 text (parse the frozen doc table). Side effects: doc parsing is brittle; no runtime change.

**My recommendation.** A when the owner next opens the frozen package; B as an interim AUDIT-side enforcement.

**Acceptance and regression tests.** A contract without consumers must fail validation (after A); all 74 real contracts carry the fields.

Classification: **documentation-only** (aspirational contract fields; no runtime behaviour depends on them).

---

## J-005

**Auditor claim (short quote).** "ماتریس CP-5 هنوز θ_H=۰٫۶۵، مرزهای Q2/Q5=۰٫۸/۰٫۴ و `yaml_assertions == []` را «PASS» و مبنای قاعدهٔ رژیم معرفی می‌کند. D49 مقادیر YAML را به ۱٫۱۰۵۸۷۸/۱٫۲۲۹۸۸۰/۰٫۵۶۴۴۱۵ تغییر داده و تست فعلی سه assertion می‌خواهد. PASS تاریخ ۱۲ سپتامبر تاریخچه است… D30 fit پیش‌فرض ۲۰ سلول پایه است، نه ۱۴۰ سلول دامنهٔ داده."

**What I read.** `PHASE2_TRACEABILITY_MATRIX.md:150–155` — the CP-5/E11 rows, verbatim: E11\|3 "TRANSITION(H≥0.65 RAW nats, ISSUE-CP5-010)"; E11\|6 "Q2 H≥0.8∨Tur≥20 / Q3 H≥0.65∨Tur≥15.5 / Q5 H<0.4∧Tur<8"; E11\|8 "params/e11_params_v4.yaml re-asserted … K=9, θ_H=0.65 nats … yaml_assertions == [] (zero divergences) … PASS(2026-09-12)". `params/e11_params_v4.yaml:4–11` — "D49 (2026-09-24): theta_H = H p80, quality_H_Q2 = H p90, quality_H_Q5 = H p30" with `theta_H: 1.105878`, `quality_H_Q2: 1.229880`, `quality_H_Q5: 0.564415`. `PHASE2_DECISION_LOG.md` D49 (matrix L604/L645 mirror it: "D49 values … 1.105878, 1.229880, 0.564415 | Implemented; tests/unit/test_cp146.py") and D30 (training scope). `tests/unit/test_e11_regime.py:668–684` — asserts `p.entropy_threshold == pytest.approx(1.105878)` and `len(p.yaml_assertions) == 3` with theta_H/quality_H_Q2/quality_H_Q5 all recorded as overrides.

**Reproduction.** Suite run (beyond the auditor, who ran nothing): `python3 -m pytest -q tests/unit/test_e11_regime.py` → **79 passed** with the D49 values — the binding artifacts (YAML + engine + tests) agree with D49 and disagree with the matrix text. Machine comparison matrix↔YAML↔test: matrix says 0.65/0.8/0.4 and `yaml_assertions == []`; YAML/test say 1.105878/1.229880/0.564415 and 3 assertions. The matrix's own D49 row (L645) records the new values as Implemented — the CP-5 rows were simply never revisited.

**Verdict and reasoning.** CONFIRMED. The CP-5 matrix rows are stale relative to D49; the "PASS(2026-09-12)" predates D49 (2026-09-24) and is a historical record, not a result of the current suite. D30 nuance also confirmed: the E11 default training scope is the 20 base cells (decision), while the 140-cell figure is the data-coverage scope — the matrix's phrasing conflates them.

**Root cause.** Matrix CP-5 rows written at CP-5 time; D49 re-tuned the three governed values at CP-14.6 and the traceability rows were not updated (the decision-log row was).

**Direct impact.** None at runtime (the YAML and engine follow D49). A reader of the matrix sees a contradictory calibration registry and may attribute the old PASS to the new thresholds.

**Secondary effects and interactions.** Acceptance/testing trust; the audit's "possible independent fallback R-006" is a risk note, not something I can test without device artifacts.

**Contract and decisions.** D49 governs (later decision overrides the matrix by the precedence rule); D30 governs the scope phrasing.

**Frozen status and non-frozen alternative.** Matrix not frozen.

**Fix options.** A) Update E11\|3/6/8 rows to the D49 values, mark the 2026-09-12 PASS as historical, add the current-suite result (79 passed, dated), and note the D30 scope distinction. Side effects: none.

**My recommendation.** A.

**Acceptance and regression tests.** A doc-lint test comparing the matrix E11 rows against the YAML literals (both files readable in-test).

Classification: **resolved by decision (D49)** + stale matrix text (documentation-only).

---

## J-006

**Auditor claim (short quote).** "Z.8 برای A هم‌زمان «۲۷ برد/۴۲» و «نرخ پس‌از‌هزینه ۰٫۵۸» می‌دهد؛ `z8_scenarios` Wilson را بر ۲۷/۴۲ می‌زند: LB≈۰٫۴۹۱۷، PROMOTION_ALLOWED. سند خودش با p̂=0.58، LB≈۰٫۴۹ می‌نویسد؛ محاسبهٔ مستقیم فرمول برای p̂=۰٫۵۸، LB≈۰٫۴۳۰ است. اگر ۰٫۵۸ نرخ برد پس‌از‌هزینه باشد، ۲۴ یا ۲۵ برد/۴۲ LB≈۰٫۴۲۲/۰٫۴۴۵ و تصمیم مرز ۰٫۴۸ برعکس می‌شود؛ ۰٫۵۸×۴۲ شمار صحیحِ برد نیست."

**What I read.** `APEX_GEN5.md` Z.3 (L17348–17367): "Let n = pooled trade count, k = number of profitable trades (**cost-adjusted**)… The Wilson 95% lower bound is… where z = 1.96"; Z.8 Scenario A (L17413–17430, verbatim): "Pooled sample: 42 trades…; Profitable trades: 27 wins.; Raw success rate: 27/42 ≈ 64%.; After accounting for transaction costs and slippage: cost-adjusted success rate ≈ 58%.; Wilson 95% lower bound (using n=42, p̂=0.58, z=1.96): approximately **49%**.; Breakeven threshold (cost-adjusted): 48%.; Since 49% > 48%, **promotion is allowed**." `apex/research/promotion.py:443–489` `z8_scenarios()` — encodes the worked example; `wilson_gate` (z=1.96 literal). `PHASE2_TRACEABILITY_MATRIX.md:339–345` (R-CP8\|6: "Wilson LB 0.49 for (27,42)"). Decision log searched ("wilson", "0.48", "cost-adjusted", "Z.8") → no resolving decision on the rate definition.

**Reproduction.** `python3 -B AUDIT/probes_V6/J-006.py` → `.out` (all four z8_scenarios re-derived with the real module): Scenario A quoted LB 0.49 vs recomputed **0.4917** (consistent — because the code computes on k=27, p̂=0.643); B_initial 11/18 → 0.3862 (quoted 0.39 ✓); B_3months 22/35 → 0.4634 (quoted 0.46 ✓, still blocked); B_6months 31/48 → 0.5044 (quoted 0.50 ✓, allowed) — every quoted lower bound and decision is consistent with the **integer-count** computation. But the doc's own label "p̂=0.58" is inconsistent with that arithmetic: **Wilson(0.58, n=42) = 0.4303** (< 0.48 → BLOCKED); 0.58×42 = 24.36 is not an integer win count; at k=24 → 0.4221 and k=25 → 0.4449, both below 0.48 — the promotion decision FLIPS if the cost-adjusted count is the truthful k.

**Verdict and reasoning.** CONFIRMED. The document computes the bound with the raw count (27) while labelling it with the cost-adjusted rate (0.58); Z.3's own definition says k IS the cost-adjusted count. The code (`z8_scenarios`, `wilson_gate`) inherits the k=27 arithmetic — so the runtime formula is faithful to the integer-count reading, and the "≈58%" label is the false element. Which reading is true requires the individual outcomes (device evidence) — exactly the audit's conclusion.

**Root cause.** Z.8's example was written with two rates (raw 64% for the arithmetic, cost-adjusted 58% for the label) and never reconciled with Z.3's definition of k.

**Direct impact.** None at runtime today (worked example only; the real gate uses actual outcome counts). The risk: an operator or a future implementer computing the gate on a cost-adjusted RATE instead of a count would produce a different verdict at the margin (0.48 boundary).

**Secondary effects and interactions.** Family promotion acceptance (matrix R-CP8\|6 quotes "Wilson LB 0.49 for (27,42)"); interacts with J-007 (per-window minimums) in the same Z-protocol cluster.

**Contract and decisions.** Z.3 formula governs the mechanism (code implements it); the p̂ definition conflict has no decision. AI.0 precedence does not resolve it (both passages are in the same annex).

**Frozen status and non-frozen alternative.** APEX_GEN5.md D2-patchable (Z.3/Z.8 owning sections, AJ row + new sha256 record).

**Fix options.** A) Owner decision defining the gate's k (recommend: k = number of cost-adjusted-profitable trades, an integer count, as Z.3 already says) + D2 patch of the Z.8 label ("p̂=27/42", or recompute the example with a true cost-adjusted count) + a `z8_scenarios` comment. Side effects: none runtime; the worked example's numbers change textually; the matrix row's "0.49 for (27,42)" stays valid as the integer-count arithmetic.

**My recommendation.** A (owner definition first — the audit says the same).

**Acceptance and regression tests.** A parametrized test pinning Wilson boundaries at n=42: k=26 → BLOCKED, k=27 → ALLOWED, and rate-based p̂=0.58 → BLOCKED, so the two readings can never be silently conflated again.

Classification: **documentation-only** today (code follows the integer-count formula consistently); unresolved (no decision on the rate definition).

---

## J-007

**Auditor claim (short quote).** "سیگنال حداقل ۱۰۰ معامله در پنجره را می‌خواهد؛ Z.1 می‌گوید <۱۰۰ به‌ازای هر سلول تاریخچه است؛ Z.4 کف ۳۰ برای pool خانواده است؛ optimizer به‌ازای سلول <۱۰۰ می‌سازد؛ تناقض بین این‌ها حل نشده."

**What I read.** `apex/research/promotion.py` `SIGNAL_MIN_TRADES_PER_WINDOW = 100` (GOVERNED_DEFAULTS block L40–58) and `FAMILY_POOL_MIN_TRADES = 30`; APEX_GEN5.md Z.1 (L15480–500: cells hold <100 trades each historically), Z.4 (L15500–20: family pool floor 30), W.2 (L15240–60: signal objective requires ≥100 trades per window); the optimizer loop in `apex/research/bootstrap.py` (cells iterate; the signal gate applied per candidate).

**Reproduction.** `python3 -B AUDIT/probes_V6/J-007.py` → `.out`: a pool with 42 trades passes `FAMILY_POOL_MIN_TRADES=30` (family gate OK) but the signal objective with `SIGNAL_MIN_TRADES_PER_WINDOW=100` is infeasible for every candidate (no cell/window reaches 100) → optimizer returns zero admissible candidates. Search of `PHASE2_DECISION_LOG.md` (terms: "100", "MIN_TRADES", "window", "signal") → no resolving decision.

**Verdict and reasoning.** CONFIRMED. The three clauses cannot all hold on the Z.1 data reality. Severity lowered S1→S2: the optimizer/promotion plane is Phase-3 research tooling — no PAPER/LIVE trading path executes it; today's effect is that a Phase-3 run would produce no candidates (a loud absence, not a wrong trade).

**Root cause.** Thresholds written for different populations (per-window signal vs per-cell history vs pooled family) without a reconciliation decision.

**Direct impact.** Phase-3 optimizer cannot promote anything under Z.1 data conditions; the family pool floor of 30 lets pools FORM that the signal gate then starves.

**Secondary effects and interactions.** Downstream: no optimized E-weights → defaults stay (safe direction); upstream: J-006 (the boundary math is moot while infeasible).

**Contract and decisions.** Z.1/Z.4/W.2 all frozen text; no decision resolves the conflict (verified). Later-decision precedence cannot apply — there is no later decision.

**Frozen status and non-frozen alternative.** APEX_GEN5.md D2-patchable; `promotion.py` NOT frozen (its GOVERNED_DEFAULTS could be re-decided). The clean fix is a decision, then a constant.

**Fix options.** A) Owner ruling defining the signal-gate population explicitly (e.g. "≥100 trades per family pool window" aligning with Z.4 pooling, or a per-cell relaxation table) + D2/AJ patch + `GOVERNED_DEFAULTS` update. Side effects: promotion thresholds change → tests pinned to 100 must be updated with the decision reference.

**My recommendation.** A (owner ruling required; no code-first fix).

**Acceptance and regression tests.** After the ruling: a pool at the new boundary passes/fails per the decision; the three doc clauses quote the same population.

Classification: **runtime-relevant** (research plane; blocks Phase-3 promotion); unresolved.

---

## J-008

**Auditor claim (short quote).** "۵ API که handoff CP9 در INTERFACES می‌دهد وجود ندارند یا امضایشان فرق دارد: registry_summary/assert_rejected_absent/registry_rows/rejected_rows (نام‌های واقعی دیگر است)، validate_change_proposal (نه validate_proposal)، ECRegister.register (نه ECRegistry)، sensitivity_removal_candidate(*, s1, st, threshold=0.05) و BacktestEngine run(start_index=…)…"

**What I read.** `PHASE2_HANDOFF_CP9.md` INTERFACES section (L30–55) listing the claimed signatures; `apex/research/governance.py` (actual: `InjectionLedger`, `ECRegister.register`, `validate_change_proposal`, `registry_rows`, `rejected_rows`, `assert_rejected_absent`, `registry_summary` — names/locations verified), `apex/research/backtest.py` (`BacktestEngine.run(start_index=...)` signature read), `apex/research/sensitivity.py` (`sensitivity_removal_candidate(*, s1, st, threshold=0.05)`).

**Reproduction.** `python3 -B AUDIT/probes_V6/J-008.py` → `.out`: `inspect.signature` of each real function/class vs the handoff text — 5 mismatches: (1) handoff names `validate_proposal`, real is `validate_change_proposal`; (2) handoff names `ECRegistry`, real is `ECRegister` with method `register`; (3) handoff's `sensitivity_removal_candidate(s1, s2)` — real keyword-only `(*, s1, st, threshold=0.05)`; (4) handoff's `BacktestEngine.run(i0, i1)` — real `run(start_index=...)`; (5) handoff's registry helpers under `ECRegister` class vs module-level functions (real: `registry_rows`/`rejected_rows`/`assert_rejected_absent` module-level; `registry_summary` is a method). No decision log entry covers the handoff text (searched "INTERFACES", "handoff CP-9").

**Verdict and reasoning.** CONFIRMED (5/5 verified against live signatures).

**Root cause.** Handoff written from an earlier API sketch; not regenerated after CP-8 changes.

**Direct impact.** A Phase-3 implementer (or agent) coding against the handoff gets AttributeError/TypeError on every listed call.

**Secondary effects and interactions.** None runtime; onboarding friction; compounds J-001.

**Contract and decisions.** No decision governs handoff signature text; the code is authoritative.

**Frozen status and non-frozen alternative.** Handoff file not frozen.

**Fix options.** A) Regenerate the INTERFACES table from `inspect.signature` output (the probe is the generator). Side effects: none; add a CI-ish test that imports each named symbol to prevent drift.

**My recommendation.** A.

**Acceptance and regression tests.** A test asserting every INTERFACES row resolves via `getattr`/`inspect.signature` on the real module.

Classification: **documentation-only**.

---

## J-009

**Auditor claim (short quote).** "F3 برای ورود close-at-submit را الزام می‌کند؛ backtest با next-open وارد می‌شود؛ شکاف قیمت دیده شد (۱۰۰ در برابر ۱۱۰). simulator خودش ساخته نشده."

**What I read.** APEX_GEN5.md Session-A F3 (L2740–60: "PAPER fills use the close price at submit time; any other price is a protocol violation"); `apex/research/backtest.py` `BacktestEngine.run` fill logic (next-bar OPEN entry — read the fill lines); `apex/execution/paper_sim.py` (does NOT exist — the PAPER fill simulator is unwired; grep `paper_sim|PaperSim` → absent); `PHASE2_DECISION_LOG.md` D58 (= CP-15 open: PAPER fill simulator unwired).

**Reproduction.** `python3 -B AUDIT/probes_V6/J-009.py` → `.out`: synthetic candle series 100→110; decision at bar t (close 100); `BacktestEngine` entry fill = next bar's open (110); a close-at-submit fill would be 100 — a 10% price gap on this synthetic example; no `paper_sim` module exists to reconcile.

**Verdict and reasoning.** CONFIRMED. The contract (F3) and the backtest disagree on entry price; the PAPER simulator that would implement F3 is not built (exactly D58's open item). Synthetic-data proof only — as mandated, this is NOT evidence about real fills.

**Root cause.** Backtest written with standard next-open assumption; F3 written later for PAPER; CP-15 simulator pending.

**Direct impact.** Backtest PnL and paper PnL are not comparable until the simulator lands (D58); any promotion decision taken from backtest numbers uses a different fill model than PAPER will.

**Secondary effects and interactions.** = D58 (owner-known item: PAPER fill simulator unwired, CP-15); promotion gate T-PKG-001 reads paper trials, not backtests — so the immediate promotion path is safe; the risk is analytical comparison. Numbering note: the repo decision log's own D58 entry (2026-09-24) is the *composite_estimate NOT_WIRED* decision (ISSUE-CP14-070); the fill-simulator scope is the owner's CP-15 plan item tracked under the same D-number in the owner list — the collision is flagged, not silently resolved.

**Contract and decisions.** D58 (owner item, above) already carries the missing simulator; the F3-vs-backtest fill discrepancy is the increment beyond D58 (the owner item covers the simulator being unwired, not the backtest's next-open divergence). F3 (Session-A freeze) governs PAPER fills.

**Frozen status and non-frozen alternative.** `apex/research/backtest.py` is FROZEN — the backtest cannot be changed to close-at-submit without an owner ruling (and shouldn't be: next-open is the standard backtest convention; the SIMULATOR is the artifact that must implement F3). Non-frozen path: the CP-15 simulator (new file) implements close-at-submit per F3.

**Fix options.** A) Owner ruling clarifying the intended comparison model: F3 governs PAPER; backtest keeps next-open; document that promotion gates must use PAPER trials only (T-PKG-001 already does) + D2 patch of the comparison annex. Side effects: none runtime. B) Change backtest to close-at-submit (frozen-file change) — NOT recommended: silently rewrites historical research numbers.

**My recommendation.** A; B only with explicit owner instruction.

**Acceptance and regression tests.** When CP-15 lands: a test that the simulator's fill at submit equals the decision-time close (F3), and a documented divergence note vs backtest.

Classification: **runtime-relevant** (CP-15 simulator pending = D58); doc increment documentation-only.

---

## J-010

**Auditor claim (short quote).** "بکاپ ساعتی + per-transition و WAL/replica در یک متن، backup هر ۱۵ دقیقه و RPO≤۵ دقیقه در متن دیگر؛ ابزار WAL/replica ندارد و scheduler وصل نیست."

**What I read.** APEX_GEN5.md §2.6 (L1181–89: hourly + per-transition backups with WAL + replica verification), SL-12 (L4150–60: 15-minute backup interval), AI.7 (L19900–10: RPO ≤ 5 minutes); `apex/ops/backup.py` (constants for backup paths/retention only; no WAL checkpoint, no replica, no scheduler wiring — read in full); `apex/ops/scheduler.py` (no backup task registered — grep `backup` in scheduler); `PHASE2_DECISION_LOG.md` D-021 (backup not yet wired — owner-known open item; searched "backup", "RPO", "WAL").

**Reproduction.** Reading + grep: `grep -rn "backup" apex/ops/scheduler.py apex/ops/plan_bridge.py` → no caller; `apex/ops/backup.py` exports helpers with no runtime consumer (only tests). The three doc intervals (60min+per-transition vs 15min vs RPO 5min) are mutually exclusive as written. No decision picks one.

**Verdict and reasoning.** CONFIRMED. Severity lowered S1→S2: the WIRING gap is already recorded as audit row D-021 (S1 there — periodic backup wiring absent, owner's external monitor/backup unknown); this row's increment is the numeric contradiction and the absent WAL/replica mechanism — documentation + unwired code, no runtime behaviour. (D-021's own severity is not re-litigated here.)

**Root cause.** Recovery requirements written in three passes (§2.6 system view, SL-12 runbook view, AI.7 acceptance view) without reconciliation; backup.py is a stub ahead of CP-15/CP-16.

**Direct impact.** No backups run today (owner-known); when wiring happens, the implementer must guess the interval.

**Secondary effects and interactions.** SQLite durability (WAL mode), the L3–L5 ladder's cancel-on-boot path (D57), and ISSUE-076's missing indexes all touch the same DB; RPO ≤ 5min implies per-transition logging, not hourly copies.

**Contract and decisions.** Audit row D-021 (wiring pending) covers the missing caller; the repo's decision log is silent on backup intervals (verified by grep — "backup" appears in none of the PHASE2 control files). No decision resolves the 60min/15min/RPO≤5min contradiction; AI.7 is the acceptance annex, and without a decision the precedence rule cannot select among the three.

**Frozen status and non-frozen alternative.** `apex/ops/backup.py` not frozen; APEX_GEN5.md D2-patchable.

**Fix options.** A) Owner ruling selecting one RPO/interval set (recommend: AI.7's RPO≤5min via per-transition WAL copy, hourly full copy, documented in one place) + D2 patches of §2.6/SL-12 + wiring task under CP-16 (scheduler registration, non-frozen). Side effects: Termux disk/battery cost of 5-minute copies must be sized (owner decision input).

**My recommendation.** A (owner ruling first; wiring after).

**Acceptance and regression tests.** Once wired: a test that a forced transition produces a backup file within the decided RPO; restore-verification test.

Classification: **runtime-relevant** (unwired recovery = D-021) + unresolved numeric conflict (documentation-only increment).

---

## J-011

**Auditor claim (short quote).** "۲۴ ساعت در برابر ۳۶۰۰ ثانیه TTL؛ ۳ در برابر ۴ retry؛ truncate در برابر split برای پیام‌های طولانی. پیاده‌سازی از Ch.21 canonical استفاده می‌کند."

**What I read.** `apex/telegram/gateway.py` (TTL constants, retry loop, message handling — read the relevant blocks), APEX_GEN5.md Ch.21 (L20750–820: canonical Telegram behaviour = 3600s TTL, 4 retries, split long messages), the conflicting annex text (L20790–800: "24h TTL, 3 retries, truncate") and AI.0 (L19150: precedence — chapter canonical text beats annex bullets).

**Reproduction.** Reading-only row: gateway constants match Ch.21 canonical (3600/4/split — verified against the code); the annex's 24h/3/truncate is the outlier; AI.0 gives precedence to the chapter. No decision log entry needed (AI.0 resolves), though none exists specifically for these three numbers (searched "TTL", "retry", "truncate").

**Verdict and reasoning.** CONFIRMED: the code follows the canonical chapter, the annex bullet is stale.

**Root cause.** Annex written from an earlier draft.

**Direct impact.** None (code correct); documentation ambiguity only.

**Secondary effects and interactions.** None.

**Contract and decisions.** AI.0 precedence rule resolves (canonical chapter > annex); implementation complies.

**Frozen status and non-frozen alternative.** APEX_GEN5.md D2-patchable (annex section).

**Fix options.** A) D2 patch of the annex bullet to match Ch.21 (3600s/4/split) + AJ row. Side effects: hash bookkeeping only.

**My recommendation.** A.

**Acceptance and regression tests.** Existing gateway tests already pin the canonical numbers.

Classification: **documentation-only** (resolved by AI.0 precedence; residual text stale).

---

## J-012

**Auditor claim (short quote).** "مرحلهٔ ۱ رویهٔ تلفنی شش‌مرحله‌ای branch قدیمی 7dcd022 را می‌کشد؛ PR #24 بسته شده؛ #25 مرج شده… مرحلهٔ ۶ فقط PR/merge است؛ ادغام به main در متن هست؛ ماتریس FIX ردیف و 3040 در برابر 3051 هم stale است."

**What I read.** `PHASE2_HANDOFF_CP14.md` PHONE ACCEPTANCE section (step 1: `git fetch origin && git checkout 7dcd022...` — read the six steps); GitHub state via `gh`: PR #24 (status CLOSED, unmerged, head 7dcd022), PR #25 (status MERGED at merge commit `85b2c155` — the baseline); `PHASE2_TRACEABILITY_MATRIX.md` FIX row (stale "3040 tests" count vs current collection of 3051 — verified by running `pytest --collect-only -q tests/ | tail -1` earlier in the session: 3051 items).

**Reproduction.** Reading + `gh pr view 24/25` (read-only API calls): #24 CLOSED (never merged), #25 MERGED at 85b2c155. The handoff's step-1 checkout of 7dcd022 would put the phone on a branch that was superseded by #25's merge. Six-command procedure verified step-by-step against the repo state. Matrix FIX row + test-count row confirmed stale.

**Verdict and reasoning.** CONFIRMED. The phone procedure, if executed as written today, checks out an obsolete commit; the current baseline is 85b2c155 (merged via #25).

**Root cause.** Handoff written when #24 was the expected vehicle; #25 superseded it; document not updated after the merge.

**Direct impact.** A phone acceptance run following the letter of the runbook lands on the wrong code (7dcd022 lacks the final CP-14.6 state); device state was NOT inspected (no device access) — actual owner state unknown.

**Secondary effects and interactions.** Compounds J-001 (entry-point gaps) — an operator has two documents, both partially stale.

**Contract and decisions.** G16 ONE run procedure; the merge record (#25) is the transport-level truth (verified via GitHub API).

**Frozen status and non-frozen alternative.** Handoff + matrix not frozen.

**Fix options.** A) Update step 1 to `git fetch origin && git checkout 85b2c155` (or the tag/branch that tracks the merged state) + update the FIX row and test count in the matrix. Side effects: none; add a note that PR #24 is closed-superseded.

**My recommendation.** A.

**Acceptance and regression tests.** A link-check style test is impractical for GitHub state; a note in the runbook to verify the merge commit before checkout suffices.

Classification: **documentation-only** (operationally significant).

---

## J-013

**Auditor claim (short quote).** "§13.1 هم `C=1−U` با U وزن‌دار و هم `C=1−max(U)` روی شش جزء را «binding» می‌خواند؛ این دو برای بردار نامساوی یکسان نیستند. D34 صریحاً max قدیمی را تصحیح و PAPER bootstrap را با `C=1−U` تصویب کرده، کد/تست همان را مصرف می‌کنند؛ docstring ماژول هنوز می‌گوید هر دو قانون محاسبه/گزارش می‌شوند، درحالی‌که builder مقدار max جدا تولید نمی‌کند."

**What I read.** APEX_GEN5.md L16072 ("confidence C = 1 − U, with U the weighted dissonance" — binding) and L16096/L16166–16169 (the max-form passages "C = 1 − max(U)" also presented as binding over the six components); `PHASE2_DECISION_LOG.md` D34 (L821 + L837–839: the old max rule is corrected; PAPER bootstrap uses weighted `C = 1 − U`); `apex/forecast/logistic.py` L23–26 (module docstring: both laws computed/reported), L450–476 (`build_forecast` produces the weighted value only); `tests/unit/test_forecast_logistic.py` L118–130 and L370–375 (pin the weighted form).

**Reproduction.** `python3 -B AUDIT/probes_V6/J-013.py` → `.out`: with a real `ForecastEvent` built through the repo's own `build_forecast` (u components 0.44/0.56 weighting), the record's `c` equals `1 − weighted_U` (0.56-style value); `1 − max(U)` = 0.5 is computed nowhere in the record (no separate max field exists); the module docstring nevertheless claims both laws are computed and reported.

**Verdict and reasoning.** CONFIRMED. D34 resolves the runtime question (weighted form governs; code and tests comply); the residual defect is documentation: §13.1 still presents both formulas as binding, and the docstring claims a second value that the builder never produces. No runtime failure — the audit says the same.

**Root cause.** D34 corrected the rule without a D2 patch of §13.1 or the docstring.

**Direct impact.** A re-implementer following §13.1 alone would produce a different C and different C_min accept/reject decisions at the margin; replay/oracle comparisons get two possible oracles.

**Secondary effects and interactions.** Downstream: eligibility (plan_bridge C gate) and the D55 confidence floor (0.4 + 0.2·pmax, owner item) both consume `c`; a max-form C would be systematically lower for unequal U vectors.

**Contract and decisions.** D34 (L821) is explicit and later — it governs by the precedence rule. The consumed/UNAVAILABLE set should be stated per D34.

**Frozen status and non-frozen alternative.** APEX_GEN5.md §13.1 D2-patchable; `logistic.py` docstring is in a non-frozen file (apex/forecast is not in the frozen list) — docstring fix needs no ruling.

**Fix options.** A) D2 patch of §13.1 (binding = weighted C = 1 − U per D34; the max form historical) + docstring correction + explicit consumed/UNAVAILABLE list. Side effects: hash record update; a reader-facing semantic change only.

**My recommendation.** A.

**Acceptance and regression tests.** Existing test_forecast_logistic tests already pin the weighted form; add an assertion that no `max` form is emitted in the record.

Classification: **resolved by decision (D34)** + stale text/docstring (documentation-only).

---

## J-014

**Auditor claim (short quote).** "§14.1 ابتدا C را confidence در P/U/C و شرط `C≥C_min`، سپس C را هزینهٔ اجرا تعریف می‌کند؛ fence تولید candidate، `C=cost(entry,side)` را در candidate می‌گذارد اما رتبه‌بندی `-c.C` و متن «higher C» دارد: در tie، هزینهٔ بیشتر را ترجیح می‌دهد اگر همان متغیر ملاک باشد. پیاده‌سازی حاضر `cost_unit` را برای EU و `C=forecast.c` را برای eligibility/rank جدا می‌کند."

**What I read.** APEX_GEN5.md L16642–16657 (C introduced as confidence in P/U/C with `C ≥ C_min`), L16667–16675 (C re-defined as cost: `C = fee + half_spread + slippage`), L16683–16695 (candidate pseudocode `C = cost(entry, side)`; ranking `-c.C`; tie-break text "higher C"); `apex/decision/pipeline.py` L180–210 (eligibility reads `forecast.c` — the confidence), L220–249 (ranking keys `-EU, -P, -C, U_sum, RR` where C is `forecast.c`); `apex/ops/plan_bridge.py` L854–887 (setup_for_decision: `C = forecast.c`, `cost_unit = forecast.cost_r` kept separate, feeding EU).

**Reproduction.** Reading-only row (verified by full reads + grep of both call paths; no probe needed — the audit itself proves only a documentation conflict): the two C senses coexist in §14.1; the pseudocode's tie-break "higher C" is correct for confidence but perverse for cost (prefers the more expensive execution); the implementation separates them correctly (`cost_unit` → EU; `forecast.c` → eligibility and ranking).

**Verdict and reasoning.** CONFIRMED: a contract/pseudocode conflict, not a runtime bug — the current code cannot be shown to misbehave (the audit's own boundary).

**Root cause.** One symbol (C) reused for two quantities in the same chapter; pseudocode written before the cost/confidence split was formalised.

**Direct impact.** A re-implementer of the fence could gate/rank on cost instead of confidence; two oracles for candidate prioritisation.

**Secondary effects and interactions.** Downstream: plan_bridge's EU computation uses cost_r — correct; D55's confidence floor consumes `c` — a cost-valued C would break it.

**Contract and decisions.** AI.0/AI.15 precedence does not resolve an intra-chapter symbol collision; the runtime split (confidence vs cost_R) matches the D59 hygiene decisions.

**Frozen status and non-frozen alternative.** APEX_GEN5.md §14.1 D2-patchable.

**Fix options.** A) Rename in the pseudocode: `C_confidence` for the gate/rank value, `cost_unit`/`cost_R` for the execution cost; fix the tie-break text to "higher C_confidence"; state units. Side effects: text-only; keeps the runtime untouched (as the audit recommends — fix the doc, not the code).

**My recommendation.** A.

**Acceptance and regression tests.** None beyond existing pipeline tests (they already pin the correct separation).

Classification: **documentation-only**.

---

## J-015

**Auditor claim (short quote).** "شبه‌کد §14.1 هنوز `RR=max(0.5,target_distance/stop_distance)` می‌گوید؛ D59 تصریح کرده `RR<min_rr` باید `DECISION_NO_TRADE:RR_BELOW_MIN` باشد و floor نشود. `units_of_r` فعلی رد می‌کند؛ بنابراین باگ جاری آن تابع ادعا نمی‌شود، ولی fence می‌تواند RR=.1 را ظاهراً .5 و قابل‌قبول جلوه دهد."

**What I read.** APEX_GEN5.md L16683–16694 (pseudocode `RR = max(0.5, target_distance/stop_distance)`); `PHASE2_DECISION_LOG.md` L1177 (D59(9): RR below min_rr must be refused with `DECISION_NO_TRADE:RR_BELOW_MIN`, never floored); `apex/decision/pipeline.py` L137–153 (`units_of_r` computes the raw ratio, raises `DECISION_NO_TRADE:RR_BELOW_MIN` under `min_rr`), L220–237 (candidate ranking uses the raw RR); `tests/unit/test_decision_pipeline.py` L56–63 (pins the boundary: 0.5 eligible; below refused).

**Reproduction.** Reading + test run: `tests/unit/test_decision_pipeline.py` green (included in the 179-test run of V-002b); `units_of_r` verified by inspection to raise rather than floor. No probe file needed — the audit's claim is precisely that the CODE is correct and the FENCE is stale, which inspection confirms.

**Verdict and reasoning.** CONFIRMED: fence-vs-decision conflict; the current program does not floor the ratio (the audit explicitly does not claim a code bug).

**Root cause.** D59 corrected the rule; the §14.1 fence was not patched.

**Direct impact.** A pseudocode follower admits sub-minimum geometric-payoff trades into ranking and reports RR=0.5 for a 0.1R trade; replay/acceptance comparisons across versions become inconsistent.

**Secondary effects and interactions.** `min_rr` is governed by `params/decision_v1.yaml` (0.5, D59); the ranking's RR key consumes the raw value.

**Contract and decisions.** D59 (L1177) governs (later decision over the fence).

**Frozen status and non-frozen alternative.** APEX_GEN5.md §14.1 D2-patchable.

**Fix options.** A) D2 patch: `RR = target_distance/stop_distance; if RR < min_rr: DECISION_NO_TRADE:RR_BELOW_MIN` + a historical note that the old max(0.5,…) form was superseded by D59. Side effects: text-only.

**My recommendation.** A.

**Acceptance and regression tests.** Existing test_decision_pipeline.py:56–63 already pins 0.1R → NO_TRADE and 0.5R → eligible; keep.

Classification: **resolved by decision (D59)** + stale fence (documentation-only).

---

## J-016

**Auditor claim (short quote).** "متن CLOSEDِ CP5-006 به‌طور کلی `D_mag<0.2 ⇒ filtered + EV_MOM_007` می‌گوید؛ اما بند منبع این فیلتر را در خطرِ بازار به‌شدت range-bound می‌آورد و مثال‌های واگرایی pivot با D_mag≈.078/.09 را معتبر می‌شمارد. کد EV_MOM_007 را در OLSِ هم‌علامتِ کم‌مقدار می‌دهد ولی واگرایی PIVOT را بدون گیت `.2` می‌سازد؛ fixture GF07 نیز رژیم range-bound را اثبات نمی‌کند."

**What I read.** `PHASE2_DECISION_LOG.md:118` (ISSUE-CP5-006 CLOSED text) and L805; APEX_GEN5.md L11427–11435 (E10 §7-11: the D_mag < 0.2 filter scoped to the **strongly range-bound** hazard; §11 examples with D_mag ≈ 0.078/0.09 treated as valid divergences); `apex/engines/e10_momentum/engine.py` L724–790 (OLS/pivot divergence; `convergence_dmag_max = 0.2` applied on the OLS same-sign path) and L915–941 (method arbitration); `tests/unit/test_e10_momentum.py` L261–273; golden fixture GF07.

**Reproduction.** `python3 -B AUDIT/probes_V6/J-016.py` → `.out`: using the repo's own golden fixture GF07 (pivot path, D_mag = 0.0778, price/mom pivots — no candles, so `classify_pivot_pair`/`divergence_mag_pivot` called directly as the test module does), the PIVOT path produces a valid `REGULAR_BEARISH` divergence with no 0.2 gate; the 0.2 gate exists only on the OLS same-sign path (`convergence_dmag_max`).

**Verdict and reasoning.** CONFIRMED. The CLOSED issue's summary generalises the filter beyond what the source clause (range-bound hazard) and the code (OLS-only) do; the audit correctly frames this as an imprecise ruling scope, NOT as proof that all low-magnitude pivots must be filtered.

**Root cause.** The issue-closure text compressed a path-scoped filter into a blanket rule.

**Direct impact.** None at runtime (the code is self-consistent); a future maintainer "fixing" the pivot path to match the closure text would wrongly suppress valid pivot divergences (the §11 examples' 0.078/0.09 class).

**Secondary effects and interactions.** EV_MOM_007 emission on low-D_mag OLS; arbitration between methods; fixtures GF07/GF08 would need rewriting if a global gate were imposed.

**Contract and decisions.** The source clause (L11431–32, range-bound scope) is the contract; the closure text over-generalises. Owner ruling needed to state the filter's scope, the OLS/PIVOT/BOTH method policy, and the range-bound definition (the audit's recommendation).

**Frozen status and non-frozen alternative.** `apex/engines/e10_momentum/engine.py` is FROZEN (apex/engines/**) — any scope change there needs explicit owner approval. The decision-log text is not frozen.

**Fix options.** A) Owner ruling (versioned): the 0.2 convergence gate applies to the OLS same-sign path only; pivot divergences are gated by their own minimum (0.05); "range-bound" defined per the source clause. Patch the ISSUE-CP5-006 closure text to the precise scope. Side effects: none runtime; fixture documentation updated.

**My recommendation.** A (text/decision-only; no engine change).

**Acceptance and regression tests.** Existing e10 tests + GF07/GF08 already pin current behaviour; add a comment-level test asserting the gate's path scope if the engine is ever reopened.

Classification: **documentation-only** (imprecise CLOSED ruling scope).

---

## J-017

**Auditor claim (short quote).** "سر فصل ۱۵ و D34 برای PAPER صریحاً `max(0,-net completed PAPER P/L)/current capital` را مصوب کرده‌اند و کد فقط outcome کامل را وارد loss projection می‌کند؛ بند «normative» پایین‌تر همان فصل می‌گوید این vetoها (به‌ویژه زیان روز/هفتهٔ ۱۰/۱۱) بر realized+unrealized P/L پوزیشن باز سنجیده می‌شوند. P/L بازِ منفی بدون outcome، دو oracle متضاد برای وتوی زیان می‌سازد؛ در PAPER، تقدم D34 و رفتار فعلی ثابت است."

**What I read.** APEX_GEN5.md L16701–16704 (Ch.15 head: completed PAPER P/L basis) vs L16835–16849 (the "normative" clause: vetoes 10/11 measured on realized+unrealized P/L of open positions); `PHASE2_DECISION_LOG.md:821` (D34: PAPER uses net completed P/L); `apex/ops/engine_context.py` L2254–2281 (loss projection consumes OUTCOME records only — completed trades).

**Reproduction.** Reading-only row (the two passages and the code path quoted above; the audit's own boundary: PAPER resolved, LIVE not evaluated). Verified by direct inspection that `engine_context` feeds realized-loss projection from completed OUTCOME records exclusively.

**Verdict and reasoning.** CONFIRMED: two clauses of the same chapter define the loss-veto basis differently; PAPER is resolved (D34 + code agree on completed-only); the LIVE semantics remain textually unresolved — the audit's exact framing.

**Root cause.** The lower "normative" clause predates/survives D34's PAPER adjudication without an override annotation.

**Direct impact.** None in PAPER today; a LIVE implementation must choose an oracle (completed-only vs realized+unrealized) with different veto behaviour for open losing positions.

**Secondary effects and interactions.** Veto 10/11 (daily/weekly loss caps from `risk_defaults_v1.yaml`: 0.03/0.06) and the L3–L5 ladder; interacts with J-019's margin bands in the same chapter.

**Contract and decisions.** D34 governs PAPER (explicit); the LIVE clause needs an owner decision or an explicit override annotation (changing D34 itself needs owner permission — the audit says so).

**Frozen status and non-frozen alternative.** APEX_GEN5.md Ch.15 D2-patchable; `engine_context.py` not frozen (but no code change is implied for PAPER).

**Fix options.** A) D2 patch: annotate the lower clause with "PAPER override per D34 (completed-only); LIVE basis: owner decision pending" and define the mark-risk basis separately if needed. Side effects: text-only.

**My recommendation.** A.

**Acceptance and regression tests.** Existing risk-kernel tests pin the PAPER behaviour; a LIVE-basis decision would need new tests then.

Classification: **resolved by decision (D34) for PAPER** + unresolved LIVE text (documentation-only).

---

## J-018

**Auditor claim (short quote).** "فصل ۱۶ کلید اجرا را SHA بر `intent_id/order_id/timestamp_UTC/nonce` با TTL می‌خواهد، ولی AI.8 برای همان Order submission کلید `order_hash` بر `symbol/side/qty/price/timestamp` با TTL=۶۰ثانیه و حذف ارسال تکراری را مقرر می‌کند… probe با fake دو POST امضاشده و دو clientOrderId متمایز ساخت؛ کلید فصل ۱۶ فقط در audit/result بود، نه query، و cache آداپتر بر intent تکیه داشت. D50 نیز intent مستقل و عدم ارسال مجدد همان ID را تصویب کرده است. دو intent شاید دو دستور مجاز مستقل باشند."

**What I read.** APEX_GEN5.md L16908–16917 (Ch.16 idempotency key: SHA over intent_id/order_id/timestamp_UTC/nonce with TTL) and L18930–18948 (AI.8: `order_hash` over symbol/side/qty/price/timestamp, TTL 60s, suppress duplicate submissions); `PHASE2_DECISION_LOG.md:1159` (D50: independent intents; no re-submission of the same ID); `apex/execution/toobit_map.py` L558–576; `apex/execution/toobit_adapter.py` L402–474 (signed request construction), L639–660 (intent cache), L722–725; `tests/fake_toobit_responder.py` (the signed-request double).

**Reproduction.** `python3 -B AUDIT/probes_V6/J-018.py` → `.out` (real adapter + FakeToobitResponder, env APEX_ENV=PAPER/APEX_ALLOW_SIGNED=1 + dummy key/secret per the test pattern): two submissions with DISTINCT intents but IDENTICAL content (symbol/side/qty/price/timestamp) → **two signed POSTs with two distinct clientOrderIds**; the Ch.16 key appears only in the audit/result records, never in the HTTP query; repeating the SAME intent → cached, no second POST. So AI.8's content-based dedup is not implemented; Ch.16/D50's intent-based idempotency is.

**Verdict and reasoning.** CONFIRMED: the two contract clauses give different answers for two-intents-same-content; the implementation follows Ch.16/D50. Whether two such plans are legitimate independent orders (or a duplicate the system should suppress) is an owner policy question — the probe does not prove a real trading duplicate, exactly as the audit frames it.

**Root cause.** AI.8 (annex, integration-contract table) and Ch.16 (canonical chapter) define idempotency over different tuples; D50 sided with intent identity; AI.8 was never patched.

**Direct impact.** If a genuine duplicate plan ever carries a fresh intent_id, it will be submitted twice; the 60-second content-window suppression of AI.8 does not exist.

**Secondary effects and interactions.** D50's replay_key (content-addressed identity for research) is a different mechanism and is implemented; the ladder's cancel paths (L3) rely on order identity too.

**Contract and decisions.** D50 + Ch.16 govern (canonical chapter + later decision over the annex per AI.0); AI.8's row is the stale/conflicting element.

**Frozen status and non-frozen alternative.** APEX_GEN5.md AI.8 D2-patchable; the adapter (execution plane) is not in the frozen list but a behaviour change needs a decision.

**Fix options.** A) Owner ruling: intent-based idempotency (Ch.16/D50) is the law; D2-patch AI.8's row to describe the research/replay identity (D50's replay_key) instead of order dedup, OR mandate a content-window guard if suppression is wanted. Side effects of adding a content guard: two legitimate identical orders within 60s would be refused — a trading-behaviour change needing explicit approval.

**My recommendation.** A (ruling + doc patch first; no code change without the owner asking for suppression).

**Acceptance and regression tests.** The probe's three behaviours (distinct intents → 2 POSTs; same intent → cache; Ch.16 key in audit trail only) become an adapter test.

Classification: **resolved by decision (D50/Ch.16)** for the implemented behaviour; **runtime-relevant policy question** for AI.8's suppression (owner).

---

## J-019

**Auditor claim (short quote).** "فصل ۱۵ هشدار را زیر ۶۰٪، منع ورود/veto14 را زیر ۴۰٪ و L3 CANCEL_ALL را زیر ۲۰٪ می‌نامد؛ D29 این سه مرز سختِ PAPER را صریح تثبیت کرده و `margin_health_state` همان را برای PAPER پیاده می‌کند. ولی Y.2 همان اعداد را «comfortable در ۶۰٪، warning در ۴۰٪، critical در ۲۰٪» معرفی می‌کند… آزمون CP-6 با نام PAPER در veto14 مقدار ۰٫۴ [بدون تعیین محیط] می‌آزماید."

**What I read.** APEX_GEN5.md L16859–16863 (Ch.15 bands: warning <60%, entry veto/veto14 <40%, L3 CANCEL_ALL <20%), L17573–17590 (Y.2: comfortable/warning/critical labels on the same 60/40/20 numbers), L20486; `PHASE2_DECISION_LOG.md` D29 (L455–462: the three hard PAPER borders); `apex/risk/kernel.py` L289–296 (veto14) and L543–574 (`margin_health_state`: PAPER strict-below vs default inclusive comparisons); `params/paper_account_v1.yaml`; `tests/integration/test_context_to_trade_paper.py` L494–517 (the CP-6 veto14 test).

**Reproduction.** `python3 -B AUDIT/probes_V6/J-019.py` → `.out`: band-edge table from the REAL kernel: at health 0.60 PAPER=OK vs default=WARNING; at 0.40 PAPER=WARNING (ALLOW) vs default=ACTION (REJECT via veto14); at 0.20 PAPER=ACTION/BLOCK vs default=EMERGENCY (L3 CANCEL_ALL semantics). The CP-6 test `test_hard_veto_flips_allow_to_reject` calls the kernel at 0.40 WITHOUT setting environment/margin_model — so it exercises the DEFAULT branch only; under the PAPER identity the same fraction yields ALLOW. Y.2's labels (60 comfortable / 40 warning / 20 critical) give a third reading that names no action.

**Verdict and reasoning.** CONFIRMED. Ch.15+D29 (PAPER) and the default/LIVE branch genuinely diverge at every band edge; Y.2's labelling is loose (no action mapping, no ≤/< statement, no PAPER/LIVE scope). No PAPER runtime error is claimed — the PAPER path implements D29 exactly.

**Root cause.** Y.2 (a summary annex) re-labelled Ch.15's action bands without the comparison operators or the PAPER/default split; the CP-6 test name says PAPER but does not pin the environment.

**Direct impact.** None in PAPER (correct per D29). A LIVE/default-mode reader gets different actions at 0.40/0.20 than the PAPER labels suggest; the test's name overstates what it covers.

**Secondary effects and interactions.** veto14 (entry block), the L3 CANCEL_ALL ladder (D-030 area / Ch.23), and ISSUE-076's boot ladder context; the 0.20 edge additionally diverges in ACTION name (BLOCK vs LIQUIDATION_APPROACH/EMERGENCY_L3_CANCEL_ALL).

**Contract and decisions.** D29 governs PAPER (explicit, L455–462); Ch.15 carries the default bands; Y.2 is the loose summary.

**Frozen status and non-frozen alternative.** APEX_GEN5.md Y.2 D2-patchable; `kernel.py` not frozen (no change implied — the PAPER branch is per D29); the test file not frozen.

**Fix options.** A) D2 patch of Y.2: state the comparison operators, the PAPER vs default/LIVE scope, and the action per band (aligning labels to Ch.15/D29); add a note in the CP-6 test that it exercises the default branch, and add a PAPER-branch twin test. Side effects: none runtime; test additions only.

**My recommendation.** A.

**Acceptance and regression tests.** Parametrised kernel test at 0.60/0.40/0.20 for BOTH the PAPER and default branches (the probe output is the expected table).

Classification: **resolved by decision (D29) for PAPER**; Y.2 residual text (documentation-only) + test-coverage nuance.

---

## J-020

**Auditor claim (short quote).** "W.6 انتخاب پیش‌فرض DEEP را دریافت و درج خام از ۲۰۲۰ تا ۲۰۲۶ برای ۱۴۰ سلول داده و Phase 2 replay روی کل store محلی می‌خواهد؛ §۲.۶ و AI.5 نگهداشت raw را ۱۲ ماه rolling تعیین می‌کنند. در صورت اعمال `retention_purge` پس از اخذ DEEP در ۲۰۲۶، raw پیش از حدود ۲۰۲۵ از store حذف می‌شود… فراخوانی زمان‌بندی‌شدهٔ purge در runtime مشاهده نشد."

**What I read.** APEX_GEN5.md L1181–1183 (§2.6: 12-month rolling raw retention), L17249–17276 (W.6: DEEP 2020→2026 default for the 140 data cells), L17290–17293 (Phase-2 replay over the whole local store), L18723–18735 (AI.5), L20698–20699 (DEEP freeze identity); `apex/data_catalog/store/sqlite_store.py` L627–660 (`retention_purge` — exists, takes cutoff, deletes raw rows); grep for callers; `PHASE2_DECISION_LOG.md` ISSUE-CP11-001 (L176: venue retains only ~3500 bars/interval).

**Reproduction.** Reading + grep: `retention_purge` has NO runtime caller (referenced by a test only); no scheduler/ops path invokes it; no archive/exception decision exists for DEEP-acquired history. The two policies (deep acquisition vs rolling purge) are both in the frozen text with no reconciliation. ISSUE-CP11-001 adds the practical bound: the venue itself serves only ~3500 bars per interval, so multi-year raw history cannot be re-fetched after a purge.

**Verdict and reasoning.** CONFIRMED as a **conditional policy conflict**: if DEEP is acquired and a purge is later run (or scheduled), raw pre-~2025 would be deleted unrecoverably (venue cap); today no purge runs, so nothing has been lost. K-007/008 (the audit's separate execution-consequence rows) are out of V6 scope.

**Root cause.** Retention and acquisition policies written in different annexes without a mutual exception; the purge helper shipped without a wiring/authorization decision.

**Direct impact.** None today (no caller). Future: silent loss of replay/optimizer history if the purge is wired naively.

**Secondary effects and interactions.** J-010 (backup/RPO) — a backup exception would also answer this; the optimizer's W.6 promise; ISSUE-CP11-001's venue bound makes the loss irreversible.

**Contract and decisions.** No decision resolves it (searched: retention, purge, archive, 12-month). AI.5/§2.6 vs W.6 both frozen text.

**Frozen status and non-frozen alternative.** APEX_GEN5.md D2-patchable; `sqlite_store.py` is FROZEN (apex/data_catalog/**) — wiring the purge would be a frozen-file change needing owner approval anyway.

**Fix options.** A) Owner ruling: DEEP-acquired cells are exempt from the 12-month rolling purge (or: purge applies to live-ingest cells only; deep history is archived before purge with an owner-decided archive path). D2 patch of §2.6/AI.5/W.6 to state the exception; only then wire `retention_purge` (with the archive step) under CP-16. Side effects: storage growth on the phone (owner capacity input — the G-CAPACITY annex is the constraint).

**My recommendation.** A (decision before any wiring).

**Acceptance and regression tests.** When wired: a test that DEEP-flagged cells survive a purge; an archive-then-purge round-trip test.

Classification: **runtime-relevant conditionally** (unwired today); policy conflict unresolved.

---

## J-021

**Auditor claim (short quote).** "Y.1 هزینهٔ رفت‌وبرگشت «به‌ازای واحد» را از دو fee rate، لغزش و funding می‌سازد، تعداد معاملهٔ روزانه را بر تمام روزهای معامله‌شدهٔ بازه تعریف می‌کند و برای مبلغ «USDT در ماه» آن را در ۲۱٫۷ روز کاری ضرب می‌کند؛ Y.3/Y.4 بازار هدف را ۲۴/۷ می‌دانند. با ۱۰ معامله/روز و هزینهٔ واقعی ۱ USDT برای هر معامله، در ماه ۳۰روزه هزینهٔ ۳۰۰ USDT است نه ۲۱۷؛ اگر بند (۱) فقط نرخ/هزینهٔ هر واحد باشد، ضرب آن در تعداد معاملات بدون اندازهٔ هر معامله اصلاً مبلغ USDT [نمی‌دهد]."

**What I read.** APEX_GEN5.md L17546–17569 (Y.1: per-unit round-trip cost from the two fee rates + slippage + funding; daily trade count over all traded days; the monthly USDT figure multiplied by 21.7 business days), L17592–17618 (Y.3/Y.4: 24/7 target market), L19235–19261; `apex/research/backtest.py` L496–519 (the cost model that exists — per-trade cost accounting); grep of `apex/` + `scripts/` for any 21.7/monthly-cost gate implementation.

**Reproduction.** Reading + grep: no runtime implementation of the Y.1 monthly gate exists (no 21.7 constant, no monthly USDT accumulation outside the annex text); Y.1's own closing table marks every item UNVERIFIED. The arithmetic check: 10 trades/day × 1 USDT × 30 days = 300 ≠ 10 × 1 × 21.7 = 217; and a per-UNIT rate multiplied by a trade COUNT is not a USDT amount without per-trade size.

**Verdict and reasoning.** CONFIRMED: the Y.1 cost-budget formula is dimensionally wrong (rate×count≠USDT) and its 21.7-business-day calendar contradicts Y.3/Y.4's 24/7 market; nothing implements it, and the annex itself labels the items UNVERIFIED.

**Root cause.** Y.1 drafted by analogy with equity-market calendar conventions.

**Direct impact.** None today (no implementation). If implemented as written, the monthly economic-gate budget would be understated and dimensionally meaningless.

**Secondary effects and interactions.** The economic gate (signed LIVE permission surface, §2.5) would consume this budget; D-001-family rows about the economic gate are separate audit items.

**Contract and decisions.** No decision governs the monthly cost gate (searched); Y.3/Y.4 are the market-model authority.

**Frozen status and non-frozen alternative.** APEX_GEN5.md Y.1 D2-patchable.

**Fix options.** A) D2 patch of Y.1: define cost per trade in USDT (rate × trade notional/size), a 30-day (or 365/12-day) crypto calendar, and an explicit formula; keep the UNVERIFIED markers until measured on device. Side effects: text-only until an implementation is decided.

**My recommendation.** A.

**Acceptance and regression tests.** When implemented: a unit test of the monthly budget with a known trade log (dimensional check included).

Classification: **documentation-only** (defect in an unimplemented annex formula).

---

## J-022

**Auditor claim (short quote).** "جدول AI.12، خروجی «Decision Engine & Portfolio Proposal» را `capital allocation per candidate` و پذیرش را «allocation non-negative; sum ≤ capital limit» می‌نامد، ولی §۱۴ فقط `sizing_request`/پیشنهاد را پیش از Risk می‌دهد… خروجی Arbitration فعلی `allocates_capital=False` است و `StrategyProposal` تنها درخواست اندازه‌گذاری می‌برد؛ آزمون CP-6 اولی را و ALLOW/سایز خروجی Risk را جدا assert می‌کند."

**What I read.** APEX_GEN5.md L19202–19211 (AI.12 row: "capital allocation per candidate", "allocation non-negative; sum ≤ capital limit"), L15953–15975 (AF.1: the decision plane proposes, never allocates), L16621–16648 (§14.1: sizing_request only, pre-Risk), L16696–16700 (Strategy Arbitration boundary: no capital allocation); `apex/decision/pipeline.py` L394–407 (`StrategyProposal` with `allocates_capital=False`), L411–492 (arbitration output); `tests/integration/test_context_to_trade_paper.py` L471–491 (asserts `allocates_capital=False` and the separate Risk ALLOW/size output).

**Reproduction.** Reading + test run (the CP-6 integration test is part of the suite; the 471–491 assertions verified by reading): the pipeline's proposal carries no allocation; sizing is computed after the 14 vetoes in the Risk Kernel; AI.12's table text contradicts AF.1/§14.1.

**Verdict and reasoning.** CONFIRMED: explicit contract-internal conflict; the implementation and tests follow AF.1/§14.1 (no allocation before Risk). AI.0/AI.15 say integration tables are informative — but the conflict is still a defect for any reader implementing from AI.12.

**Root cause.** AI.12's portfolio-proposal row written at an architecture level above the actual pre-Risk contract.

**Direct impact.** None at runtime (code correct). A re-implementer adding pre-Risk allocation would violate the arbitration boundary and double-allocate.

**Secondary effects and interactions.** The Risk Kernel's `size()` is the single sizing authority (interacts with A-005/J-024 numbers).

**Contract and decisions.** AI.0/AI.15 (informative tables) + AF.1/§14.1 (normative) resolve in favour of the current behaviour.

**Frozen status and non-frozen alternative.** APEX_GEN5.md AI.12 D2-patchable.

**Fix options.** A) D2 patch of the AI.12 row: output = "sizing_request per candidate (no capital allocation; allocation happens in the Risk Kernel after vetoes)". Side effects: text-only.

**My recommendation.** A.

**Acceptance and regression tests.** Existing tests already assert `allocates_capital=False`; keep.

Classification: **documentation-only** (resolved by AI.0/AI.15 precedence + implementation).

---

## J-023

**Auditor claim (short quote).** "AA.7 با عنوان «Normative» استفاده از Numba JIT و Float32 را برای تمام محاسبات سنگین الزام می‌کند؛ §۹.۵-۹ صریحاً Numba را «Wave-Out / do not implement» چون در SBOM نیست می‌نامید. تصمیم CP8-002 به‌درستی Wave-Out را مقدم دانسته و `proxies.py` با `NUMBA_USED=False` و تست نبود import کار می‌کند؛ بنابراین این ردیف ادعای باگ محاسبهٔ کنونی یا لزوم نصب Numba نیست."

**What I read.** APEX_GEN5.md L17718–17727 (AA.7-2: "Normative" Numba JIT + Float32 for HMM/DCC/Kalman/EVT/bootstrap) vs L20343–20349 (§9.5-9: Numba is Wave-Out — not in the SBOM); `PHASE2_DECISION_LOG.md:157` (ISSUE-CP8-002: Wave-Out takes precedence); `apex/research/proxies.py` L1–28 and L48 (`NUMBA_USED = False`); `tests/unit/test_research_proxies.py` L280–285 (asserts no numba import); `requirements.lock` (no numba — frozen).

**Reproduction.** Reading + test run (`test_research_proxies.py` is in the CP-8 suite; the 280–285 assertions verified): `NUMBA_USED=False`; no numba import anywhere; the decision closes the conflict in favour of Wave-Out.

**Verdict and reasoning.** CONFIRMED: the residual is the un-patched AA.7-2 "Normative" text, which still tells a standalone reader to install a forbidden dependency and change numeric policy (Float32 vs the contract's double precision).

**Root cause.** AA.7 drafted with performance aspirations; the SBOM constraint won; the annex header never downgraded.

**Direct impact.** None at runtime.

**Secondary effects and interactions.** Numeric-precision policy (canonical JSON 8-digit doubles, §9.5) would break under a Float32 reading.

**Contract and decisions.** ISSUE-CP8-002 (CLOSED) resolves: Wave-Out governs; requirements.lock (frozen) has no numba.

**Frozen status and non-frozen alternative.** APEX_GEN5.md AA.7-2 D2-patchable.

**Fix options.** A) D2 patch: mark AA.7-2 as superseded by ISSUE-CP8-002 (Wave-Out; stdlib/numpy double precision is the contract). Side effects: text-only.

**My recommendation.** A.

**Acceptance and regression tests.** Existing test_research_proxies.py:280–285 (no numba import) already pins it.

Classification: **resolved by decision (ISSUE-CP8-002)** + residual annex text (documentation-only).

---

## J-024

**Auditor claim (short quote).** "جدولِ «SL-12 governed defaults» در §۱۷ `budget_per_trade=۱٪` و `k_attn=۰٫۰۵` می‌گوید، ولی FROZEN_BOOTSTRAP §۹.۵ و YAML نسخه‌شده `۰٫۰۰۵=۰٫۵٪` و `۰٫۲۵` دارند؛ D8 صریحاً YAML را مرجع runtime و متن §۱۷ را واگراییِ ثبت‌شده می‌داند. `size()` از YAML بار می‌گیرد و `assert_yaml_consistency` فقط یادداشت `doc_inconsistency` می‌دهد."

**What I read.** APEX_GEN5.md L17130–17142 (§17.1 SL-12 governed-defaults table: budget_per_trade=1%, k_attn=0.05), L20459/L20490–20505 (§9.5 FROZEN_BOOTSTRAP: 0.005 and 0.25), L20946–20948; `PHASE2_DECISION_LOG.md:156` (ISSUE-CP8-001), L201 (D8: YAML is the runtime authority; the §17 table is a recorded divergence), L216; `params/risk_defaults_v1.yaml:1–6` (budget_per_trade: 0.005, k_attn: 0.25); `apex/risk/kernel.py` L360–382 (`size()` reads the YAML through `frozen_risk_params`); `apex/research/governance.py` L112–126/L220–245 (`assert_yaml_consistency` → `doc_inconsistency` notes); `tests/unit/test_research_governance.py` L65–75.

**Reproduction.** `python3 -B AUDIT/probes_V6/J-024.py` → `.out`: `assert_yaml_consistency` on the real six YAMLs reports exactly the two `doc_inconsistency` rows (budget_per_trade, k_attn); `size()` uses the YAML values (R_allowed = 0.005 × capital; attention bound = 0.25 × atr_cap × capital) — a 2× and 5× difference from the §17 table numbers respectively.

**Verdict and reasoning.** CONFIRMED: the divergence is real, recorded, and resolved by D8 in favour of the YAML; the runtime loads the YAML; the governance check notes the divergence without failing. No sizing error and no YAML change is claimed — matching the audit.

**Root cause.** The §17 table predates the frozen YAML values; D8 recorded the divergence instead of patching the table.

**Direct impact.** None at runtime. A reader of §17 alone would expect double the budget and a fifth of the attention cap.

**Secondary effects and interactions.** A-005 (inf values), A-012 (mutability), V-001 (coverage) all assume the YAML is the authority — consistent with D8.

**Contract and decisions.** D8 + ISSUE-CP8-001 govern (YAML = runtime authority; §17 text = recorded divergence).

**Frozen status and non-frozen alternative.** `params/risk_defaults_v1.yaml` is one of the six FROZEN YAMLs — untouchable without owner ruling; the §17 table is D2-patchable text.

**Fix options.** A) D2 patch of the §17.1 table to the YAML values (0.005/0.25) with a historical note "superseded by D8", keeping `assert_yaml_consistency`'s notes as the divergence registry until then. Side effects: text-only; the governance probe output would then show zero doc_inconsistency rows (update its test expectation).

**My recommendation.** A.

**Acceptance and regression tests.** Keep `assert_yaml_consistency` as the machine registry; after the patch its expected note count changes from 2 to 0.

Classification: **resolved by decision (D8 / ISSUE-CP8-001)** + stale table text (documentation-only).

---

# O-rows — evidence limits, and V-rows — verified controls

## O-001

**Auditor claim (short quote).** "baseline فریز اولیه قابل بازسازی محلی نیست؛ محدودیت شواهد؛ هش سند جاری با رکورد آن منطبق است؛ فایل docs فقط رکورد هش است، نه متن فریز. checkout shallow است. D2 اصلاح کنترل‌شدهٔ سند را مجاز کرده؛ اختلاف هش به‌تنهایی نقص نیست."

**What I read.** `README.md:5–6` (freeze digest 216bcc9e… recorded); `docs/APEX_GEN5_frozen_216bcc.md` in full (1155 bytes — a hash record with anchors, NOT the frozen text); `PHASE2_DECISION_LOG.md:195` (D2: controlled patch permission); the git history of `APEX_GEN5.md` (all 20 commits touching it, after this session's read-only `git fetch --unshallow`).

**Reproduction.** `python3 -B AUDIT/probes_V6/O-001.py` → `.out`: current `APEX_GEN5.md` sha256 = `493568887acb…` == the CP-14.6-FIX digest recorded in docs/README (hash chain intact); `docs/APEX_GEN5_frozen_216bcc.md` is 1155 bytes (hash record only — confirmed); scanning all 20 historical versions of `APEX_GEN5.md`: **commit `102dffe01` ("Add files via upload", the initial commit) holds the frozen baseline text with sha256 exactly `216bcc9e5f3e…`** — the freeze digest. `git rev-parse --is-shallow-repository` = false in this session (after the unshallow fetch).

**Verdict and reasoning.** PARTIAL. Every sub-claim is individually true **as scoped to a shallow checkout** ("checkout shallow است" — the audit's own words, and this session's checkout was also shallow at start). But the headline "the initial freeze baseline is not locally reconstructible" is an artifact of the shallow clone: with the full history (which the same repository serves — no external evidence needed), `git show 102dffe:APEX_GEN5.md` reproduces the baseline and its digest matches the record. The auditor's requested remedy ("provide the baseline text/commit in readable form") is satisfiable from the repo itself. Everything else (docs file = hash record only; current hash matches; D2 permission; a hash difference alone is not a defect) is CONFIRMED.

**Root cause.** Evidence limitation of the audit environment (shallow clone), correctly labelled by the auditor as a limitation rather than a repository defect.

**Direct impact.** None (no incident claimed).

**Secondary effects and interactions.** Enables the freeze-diff audit the auditor wanted: baseline 102dffe vs current, mapping every change to a D2-authorised patch. Session-A note: commits `8d8ef4e` (digest 132f702f) and `1835b59` (digest 683ea01d) also match digests recorded in the decision-log patch history — the D2 chain is internally consistent.

**Contract and decisions.** D2 (L195) governs controlled document edits; D60 records the freeze digest documentation.

**Frozen status and non-frozen alternative.** docs/README not frozen; no change implied.

**Fix options.** A) No repository change required; the remedy is procedural: run freeze-diff audits against `102dffe:APEX_GEN5.md` and map diffs to D2 decisions (this session verified the chain exists; the full diff-mapping audit remains future work — see "Rows not verified or incomplete"). Optionally note the baseline commit id next to the hash record in docs/. Side effects: none.

**My recommendation.** A.

**Acceptance and regression tests.** A one-line audit script asserting `sha256(git show 102dffe:APEX_GEN5.md) == 216bcc9e…` (probe O-001 is that script).

---

## O-002

**Auditor claim (short quote).** "داده، وزن مدل و گزارش واقعی آموزش در checkout نیست؛ محدودیت شواهد، نه شکست آموزش؛ `data/` و `params/e11_classifier_v1.yaml` وجود ندارند و عمداً خارج Git نگهداری می‌شوند. پوشش دادهٔ واقعی ۱۴۰ سلول، وزن‌ها، آستانه‌های مشتق‌شده و وضعیت دستگاه تأیید نشده‌اند."

**What I read.** `.gitignore:2` (`data/`) and `:12` (`/params/e11_classifier_v1.yaml` — ADR-CP14-021: "owner-produced runtime classifier, never a repository artifact"); `README.md:10` (RUNTIME_ARTIFACTS sentence); `params/e11_params_v4.yaml:4–6` (D49 header citing the device-only report `data/e11_train_report_20260924T181954Z.json`); the params directory listing.

**Reproduction.** `python3 -B AUDIT/probes_V6/O-002_O-003.py` → `.out`: `data/` does not exist; `params/e11_classifier_v1.yaml` does not exist; both are deliberately gitignored (ADR-CP14-021 / ADR-P2-013); README documents them as RUNTIME_ARTIFACTS never committed; the YAML header references the device-only training report. All six frozen YAMLs + the four non-frozen params files ARE present (verified in V-001/V-002).

**Verdict and reasoning.** CONFIRMED: the evidence limit is real, deliberate (by decision), and correctly characterised — an evidence limitation, NOT a training failure. Real 140-cell coverage, the model weights, the derived thresholds, and the device state remain unverifiable from the repo alone.

**Root cause.** By design (owner-produced runtime artifacts on the phone; secrets/data hygiene per ADR-P2-013, D3).

**Direct impact.** None claimable; conclusions about training correctness or operational readiness cannot be independently drawn from the repo.

**Secondary effects and interactions.** J-005 (the D49 values came from that device-only report — the values are in the YAML but the percentiles are not independently recomputable); O-003 (the environment that produced the artifact is also not fully pinned).

**Contract and decisions.** ADR-CP14-021 (classifier never a repo artifact); ADR-P2-013 (runtime data hygiene); D3; ISSUE-CP14-066 (OPEN for the 2026-12-22 OOS re-check only).

**Frozen status and non-frozen alternative.** `.gitignore` ADR-P2-013-governed — the correct remedy is NOT adding data/secrets to git (the audit says so too).

**Fix options.** A) Device-side evidence pack when the owner chooses: artifact sha256, schema, sample counts, timestamps, protocol, and validation output (non-sensitive extracts only) — matched against the runtime consumer. Side effects: none to the repo.

**My recommendation.** A (defer to owner; nothing to fix in-repo).

**Acceptance and regression tests.** When provided: cross-check the artifact hash against `e11_params_v4.yaml`'s recorded artifact reference and the loader's expectations.

---

## O-003

**Auditor claim (short quote).** "lock کامل محیط وجود ندارد؛ محدودیت پذیرفته‌شدهٔ قرارداد فعلی؛ ۹ وابستگی مستقیم pin شده‌اند؛ transitiveها و hash بسته‌ها کامل ثبت نشده‌اند؛ backend فقط حداقل نسخه دارد. خود سند همین فهرست را lock و hashها را UNVERIFIED معرفی کرده است."

**What I read.** `requirements.lock` (9 `==` pins: aiohttp 3.9.5, aiogram 3.7.0, aiosqlite 0.20.0, matplotlib 3.8.4, pandas 2.2.0, numpy 1.26.0, pydantic 2.5.0, python-dateutil 2.8.2, pytz 2024.1); `pyproject.toml` build-system (`requires = ["setuptools>=68"]` — minimum only); `APEX_GEN5.md:112` (Ch.1 SBOM: "This pin list is requirements.lock (hashes UNVERIFIED until first `pip freeze`)").

**Reproduction.** `python3 -B AUDIT/probes_V6/O-002_O-003.py` → `.out`: 9 direct pins, no package hashes, no transitive pins (demonstrated concretely: this session's install pulled `pydantic_core==2.14.1` — a pydantic transitive NOT in the lock; two installs could differ there); build backend is a minimum bound only; the Ch.1 text itself declares the hashes UNVERIFIED — the document is honest about the limit.

**Verdict and reasoning.** CONFIRMED: the lock is a direct-pins-only manifest by accepted contract; the auditor's characterisation (accepted limitation, self-declared) is exact. This session's environment additionally demonstrates the transitive gap empirically (pydantic_core).

**Root cause.** Contract choice (nine-pin SBOM; no tenth dependency allowed — ISSUE-CP1-008/ADR-P2-002); a full hash-pinned manifest was never produced.

**Direct impact.** Two installs with identical direct pins can differ in transitives → replay/training comparisons and device-diff debugging lose reproducibility.

**Secondary effects and interactions.** B-002 (the boot check cannot enforce what the lock does not pin); O-002 (the artifact's producing environment).

**Contract and decisions.** Ch.1 SBOM (L96–112) is the governing contract and self-declares the limit; `requirements.lock` is FROZEN — any manifest extension needs an owner decision.

**Frozen status and non-frozen alternative.** requirements.lock FROZEN. Non-frozen alternative: a SEPARATE device-side manifest (e.g. `data/pip_freeze_<date>.txt`, gitignored anyway, or an owner-decided new file) recording the phone's actual `pip freeze` + wheel hashes.

**Fix options.** A) Owner decision: record a full environment manifest (pip freeze + package hashes + build tool versions) at each device deployment, kept outside the frozen lock (device artifact or a new non-frozen file with a DECISION_LOG note); define the reconstruction procedure (install order, `--no-deps`?). Side effects: none to the lock; a new governance habit on the phone.

**My recommendation.** A (owner decision; do not touch the frozen lock).

**Acceptance and regression tests.** Two independent installs from lock+manifest must produce identical `pip freeze` output (the audit's own acceptance idea).

---

## V-001

**Auditor claim (short quote).** "پوشش اسمی تنظیمات تأیید شد؛ نتیجهٔ مثبت محدود؛ ۱۰ نماد و ۱۴ TF یکتا؛ پوشش کامل جدول‌های symbol/TF بررسی‌شده؛ مجموع Q_raw هر ردیف و وزن setup برابر ۱، جرم family برابر ۰٫۷. این، پوشش داده یا آموزش واقعی نیست."

**What I read.** `params/universe_v1.yaml`, `params/quality_weights_v1.yaml`, `params/risk_defaults_v1.yaml`, `params/setup_weights_v1.yaml` (the cited ranges), loaded through the REAL `apex.config.load_params()`.

**Reproduction.** `python3 -B AUDIT/probes_V6/V-001.py` → `.out`: 10 unique symbols; 14 unique TFs; `tick_size`/`quantity_step`/`min_notional`/`exchange_max_leverage` each cover all 10 symbols; `q_raw_weights_by_tf` has 14 rows, every row sums to exactly 1.0; `q_min_by_tf`/`q_thr_by_tf`/freshness/oi_lag tables complete over 14 TFs; the 12 setup weights sum to 1.0; `family_engines` mass = 0.54 (required 6) + 0.16 (orderblock+momentum) = **0.70**; `system_leverage_cap_by_tf` matches the Y.2 groups (2/3/4/5) for all 14 TFs; risk scalars budget 0.005 / k_attn 0.25 / daily 0.03 / weekly 0.06 / halt 4.

**Verdict and reasoning.** CONFIRMED: every nominal figure the auditor reported reproduces exactly through the real loader. This is a nominal-coverage control only — it is NOT evidence about real 140-cell data coverage or training (the audit's own scope note, which I repeat).

**Root cause.** n/a (positive control).

**Direct impact.** n/a.

**Secondary effects and interactions.** The 0.70 family mass is the `Q_setup` denominator (D59 bounded quality form); the 14-TF completeness is what ISSUE-CP14-069 (D62) fixed for `q_thr_by_tf`.

**Contract and decisions.** D62 (q_thr completeness), D63 (regime_window), D59 — the YAML surface the control covers.

**Frozen status and non-frozen alternative.** The six YAMLs are FROZEN — the correct state is "keep"; regression tests already pin them.

**Fix options.** n/a (keep). Optional: promote the probe's assertions into a permanent unit test (several already exist in `test_cp1_foundations.py`).

**My recommendation.** Keep as-is; optionally fold the coverage assertions into the existing test file when an owner-sanctioned test change happens.

**Acceptance and regression tests.** The probe itself (V-001) is the regression script.

---

## V-002

**Auditor claim (short quote).** "هر ۱۰ YAML موجود mapping شد؛ فقدان classifier خطا داد؛ محیط واقعی اولویت داشت؛ سه credential اصلی در repr mask شدند؛ شش متد TestParamsFrozenValues مستقل در حافظه PASS شدند. pytest و ۹ وابستگی runtime نصب نبودند؛ suite کامل اجرا نشد."

**What I read.** `apex/config.py` L86–200 (dotenv, masking, accessors) and L444–460 (`_load_yaml`); `tests/unit/test_config.py` (14 tests) and `tests/unit/test_cp1_foundations.py` L156–295 (`TestParamsFrozenValues`, 6 methods + the rest of the file).

**Reproduction.** Beyond the auditor's in-memory checks (they had no pytest/deps), this session installed the nine pins + pytest and ran the real suites: `python3 -m pytest -q tests/unit/test_config.py tests/unit/test_cp1_foundations.py` → **30 passed**; `TestParamsFrozenValues` alone → **6 passed**; additionally `test_e11_regime.py + test_decision_pipeline.py + test_forecast_logistic.py + test_catalog.py` → **179 passed** (`AUDIT/probes_V6/V-002.out`, `V-002b.out`). The loader's behaviours the auditor verified in-memory (all 10 YAMLs map; missing classifier raises; env precedence; credential masking) are exactly what these tests pin — and A-001/A-002 probes independently demonstrated env precedence and parse behaviour on the real module.

**Verdict and reasoning.** CONFIRMED and extended: the auditor's five in-memory findings hold, and the test suites that encode them pass in a real dependency-complete environment. The auditor's boundary statement ("full suite not run") also remains true of THIS session (the full ~3051-test collection was not executed; the config/params/E11/decision/forecast/catalog subsets were — deliberately, per the session's probe-first mandate).

**Root cause.** n/a (positive control).

**Direct impact.** n/a.

**Secondary effects and interactions.** The six `TestParamsFrozenValues` methods are the literal-vs-blueprint guard for the frozen YAMLs; `test_config.py` pins the parser behaviours rows A-001..A-013 examine.

**Contract and decisions.** ISSUE-CP1-008 (parser), D8 (YAML authority), D49/D59/D62/D63 (params decisions the tests pin).

**Frozen status and non-frozen alternative.** config.py CP-1-owned; tests not frozen.

**Fix options.** n/a (keep).

**My recommendation.** Keep; the full-suite run remains an owner-environment task (the audit's own recommendation).

**Acceptance and regression tests.** The passing suites are the acceptance evidence (recorded in V-002/V-002b outputs).

---

# New findings not in the audit

## X-V6-001 — `FeatureRegistry._by_num` is a dead, mistyped index (S4, informational)

`apex/data_catalog/catalog.py:82` declares `self._by_num: Dict[int, FeatureContract]`, and `register()` (L90) populates it with `contract.id.full_id` — a STRING — for every contract (73 entries; 74 contracts minus the J-003 duplicate). No code anywhere reads `_by_num` (grep over apex/, tests/, scripts/: only the two catalog.py lines). It is simultaneously (a) dead code, (b) misnamed ("by number"), and (c) mistyped (`Dict[int, …]` holding strings). Adjacent to J-003 but distinct: the audit covers the duplicate full_id in the IDENTITY space; this covers an internal index that is wrong on three axes and unused. Evidence: `AUDIT/probes_V6/X-V6-001.py/.out`. Catalog is FROZEN — removal/fix needs an owner ruling; impact none (dead). Recommended option: delete or fix the key type whenever the frozen package is next opened by owner ruling.

## X-V6-002 — a repo test depends on full git history and fails in shallow clones (S3)

`tests/unit/test_research_governance.py::TestLiveParamsWriteForbidden::test_frozen_params_files_are_untouched_by_this_suite` runs `git show f14be36:params/<name>` with `check=True`. In a depth-1 shallow clone (the default shape of this session's checkout — and of the audit's environment) the object `f14be36` does not exist: `fatal: invalid object name 'f14be36'` → `CalledProcessError` → the test FAILS (observed live at session start: 1 failed / 95 passed; after `git fetch --unshallow`: 96 passed). Reproduced harmlessly on a temp `--depth 1` clone: `AUDIT/probes_V6/X-V6-002.py/.out`. Consequences: (a) any verifier on a shallow clone sees a spurious failure (a false alarm — the conservative direction, but it undermines suite trust and wastes triage); (b) the audit's "suite not run" hid this; (c) the test's protection (frozen YAMLs untouched by the suite) silently degrades to an environment error in exactly the environments third-party auditors use. Not in the audit (O-001 notes the shallow checkout but not this test failure). Tests are NOT frozen. Recommended option A: make the test skip-with-reason (or fetch the object on demand) when `git cat-file -e f14be36` fails, so shallow clones get a clear SKIP instead of an error; side effects: none for full clones.

# Rows not verified or incomplete

- **None of the 49 rows were skipped.** 48 CONFIRMED + 1 PARTIAL (O-001, whose environment-scoped statement is confirmed as scoped and refuted as a repository-level fact — see the row).
- **Partial-depth items inside otherwise-confirmed rows** (inherent to a repo-only, read-only session; each is flagged in its row): A-001 (no real order submission — same boundary as the auditor); J-009 (synthetic 100→110 gap only; real-fill behaviour is device evidence; the CP-15 simulator does not exist); J-012 (GitHub transport state verified via `gh`; the owner's actual phone state not inspected); J-017 (LIVE semantics unresolved by design — no LIVE runtime exists to test); J-018 (whether two same-content intents are legitimate independent orders is an owner policy question; probe used the fake responder only); J-020 (no device purge/archive to observe); O-002 (device artifacts absent by design); V-002 (full ~3051-test suite not run — config/params/E11/decision/forecast/catalog subsets were).
- **O-001 follow-on not performed:** the full freeze-diff audit (baseline `102dffe` vs current, mapping every changed line to a D2-authorised decision) — the baseline's existence and digest match are verified; the line-by-line diff mapping is future work the auditor also did not do.

# Final counts

- Rows verified: **49/49** (A-001..A-018, B-001, B-002, J-001..J-024, O-001..O-003, V-001, V-002).
- Verdicts: **CONFIRMED 48, PARTIAL 1 (O-001), REJECTED 0, DEVICE-EVIDENCE-NEEDED 0** (device-evidence boundaries are flagged inside rows, not used as verdicts).
- Independent severity vs auditor: **S1 retained: A-001, A-015, B-001. Lowered by one level (with in-row justification): A-003 (S1→S2), A-004 (S1→S2), A-005 (S1→S2, though strengthened in substance: concrete OverflowError + attention-cap disablement), A-014 (S1→S2), A-016 (S1→S2), J-007 (S1→S2), J-010 (S1→S2). All other rows: identical to the auditor.** No severity was raised.
- Strengthened beyond the auditor's evidence: A-005 (two concrete downstream effects of inf), B-001 (approved-backend ≥68 build tested: identical 4-file wheel), J-016 (GF07 fixture used directly), J-019 (full band-edge table for both branches), V-002 (30 + 179 real tests run with dependencies installed), O-001 (freeze baseline located in history with matching digest).
- New findings beyond the audit: **X-V6-001** (dead/mistyped `_by_num` index, S4), **X-V6-002** (shallow-clone test failure, S3). Both reproduced with probes.
- Probe artifacts: 39 probe scripts + outputs under `AUDIT/probes_V6/` (A-001..A-018 + A-004b, B-001 + B-001b, B-002, J-001, J-003, J-004, J-006, J-007, J-008, J-009, J-013, J-016, J-018, J-019, J-024, O-001, O-002_O-003, V-001, V-002/V-002b, X-V6-001, X-V6-002); reading-only rows (J-002, J-005, J-010, J-011, J-012, J-014, J-015, J-017, J-020, J-021, J-022, J-023) cite the passages, code and test-run evidence inline.
- Repository discipline: no source/config/test/doc file modified; no PR opened; only files under `AUDIT/` added on branch `arena/01a0e8b1-upstage`; `git status` clean of everything except AUDIT/ additions at each commit.

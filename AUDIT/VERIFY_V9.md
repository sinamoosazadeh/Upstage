# VERIFY_V9 — Independent read-only verification of audit rows Q-001..Q-032 and R-001..R-021

- Baseline: commit `85b2c155d7b054a468379ddfd802eb239d0801f9` (verified; all line numbers refer to it).
- Branch: `arena/01a0e8b8-upstage`. Only files under `AUDIT/` were created; no source/config/test/doc was modified.
- Every row was reproduced against the REAL engine code (`PYTHONPATH=. python3 AUDIT/probes_V9/<ID>.py`, output in `AUDIT/probes_V9/<ID>.out`). numpy 1.26.0 was installed from `requirements.lock`, so E11 (Hamilton filter) and E12 ran for real — no AST substitutes.
- Baseline test health before probing: `pytest tests/unit/test_e07_rtm.py … test_e12_temporal.py tests/integration/test_cp4_engines.py test_cp5_engines.py` → **568 passed** (green), so every defect below coexists with a green suite.
- Severity scale: S0 (catastrophic) … S4 (cosmetic). "Frozen?" = does the in-engine fix touch a frozen path (`apex/engines/**`, frozen YAMLs)?
- None of the rows required SQL; `EXPLAIN QUERY PLAN` was therefore not applicable to any row in this batch (the producer-join plan issue is already owned by ISSUE-079 and was not re-litigated here).

## Summary table

| ID | Verdict | Auditor sev | Independent sev | Frozen? | Cross-ref | Recommended option |
|----|---------|-------------|-----------------|---------|-----------|--------------------|
| Q-001 | CONFIRMED | S1 | S1 | Yes | ISSUE-CP4-005, Q-007 | B (producer gate) |
| Q-002 | CONFIRMED | S1 | S1 | Yes | — | B (producer gate) |
| Q-003 | CONFIRMED | S1 | S1 | Yes | D54 (per-TF expiry) | B (fabric ageing) |
| Q-004 | CONFIRMED | S1 | S1 | Yes | — | B (producer price feed) |
| Q-005 | CONFIRMED | S1 | S1 | Yes | Q-006 | B (adapter re-label) |
| Q-006 | CONFIRMED | S2 | S2 | Yes | Q-005, Q-028 | A (contract erratum) |
| Q-007 | CONFIRMED | S1 | S1 | Yes | I-010, Q-027, R-003 | B (store-side identity) |
| Q-008 | CONFIRMED | S2 | S2 | Yes | ISSUE-073 family | B (producer calendar policy) |
| Q-009 | CONFIRMED | S1 | S1 | Yes | ISSUE-CP4-013/014 | B (owner recalibration) |
| Q-010 | CONFIRMED | S1 | S1 | Yes | Q-009 | B (producer BOS carry) |
| Q-011 | CONFIRMED | S1 | S1 | Yes | — | A (contract erratum) + tests |
| Q-012 | CONFIRMED | S2 | S2 | Yes | — | B (fabric chain gate) |
| Q-013 | CONFIRMED | S2 | S2 | Yes | R-004 | B (producer dedup) |
| Q-014 | CONFIRMED | S1 | S1 | Yes | Q-007 | B (adapter re-stamp) |
| Q-015 | CONFIRMED | S2 | S2 | Yes | Q-009, Q-017 | A (contract erratum) |
| Q-016 | CONFIRMED | S2 | S2 | Yes | — | A (contract erratum) |
| Q-017 | CONFIRMED | S2 | S2 | Yes | Q-015 | B (owner rescale) |
| Q-018 | CONFIRMED | S2 | S2 | Yes | — | A (contract erratum) |
| Q-019 | CONFIRMED | S1 | S1 | Yes | Q-020 | B (producer min-bars gate) |
| Q-020 | CONFIRMED | S1 | S1 | Yes | Q-019 | B (fabric validity map) |
| Q-021 | CONFIRMED | S1 | S1 | No (producer) | Q-025, Q-028 | A (wire mom_series in producer) |
| Q-022 | CONFIRMED | S2 | S2 | Yes | — | B (producer ATR guard) |
| Q-023 | CONFIRMED | S1 | S2 | Yes | — | B (producer swing sanitizer) |
| Q-024 | CONFIRMED | S2 | S2 | Yes | Q-025 | B (owner spec first) |
| Q-025 | CONFIRMED | S2 | S2 | Yes | Q-021 | A (contract erratum) |
| Q-026 | CONFIRMED | S2 | S2 | Yes | R-004 | A (document fresh-instance rule) |
| Q-027 | CONFIRMED | S1 | S1 | Yes | Q-007, R-003 | B (store-side identity) |
| Q-028 | CONFIRMED | S2 | S2 | Yes | Q-021 | A (contract erratum) |
| Q-029 | CONFIRMED | S1 | S1 | Yes | I-009 | B (producer as_of guard as sole entry) |
| Q-030 | CONFIRMED | S2 | S2 | Yes | — | B (config-layer validation) |
| Q-031 | CONFIRMED | S2 | S2 | Yes | Q-007 | B (fabric conflict rule) |
| Q-032 | CONFIRMED | S2 | S2 | Yes | Q-028 | B (producer BOS filter) |
| R-001 | CONFIRMED | S2 | S2 | Yes | Q-024 | B (producer pairing filter) |
| R-002 | CONFIRMED | S2 | S2 | Yes | — | A (contract erratum) |
| R-003 | CONFIRMED | S1 | S1 | Yes | Q-007, Q-027 | B (store-side identity) |
| R-004 | CONFIRMED | S2 | S2 | Yes | Q-013, Q-026 | B (producer correction policy) |
| R-005 | CONFIRMED | S2 | S2 | Yes | — | B (producer geometry gate) |
| R-006 | CONFIRMED | S1 | S1 | Yes (engine) / No (config) | D47, D49 | B (boot-time loader assert) |
| R-007 | CONFIRMED | S2 | S2 | Yes | Q-007 | B (store-side identity) |
| R-008 | CONFIRMED | S2 | S2 | Yes | GF_13 | B (producer state watchdog) |
| R-009 | CONFIRMED | S1 | S2 | Yes | — | A (contract erratum) + producer cutoff |
| R-010 | CONFIRMED | S2 | S2 | Yes | R-018 | B (profile-builder gate upstream) |
| R-011 | CONFIRMED | S1 | S1 | Yes | R-012 | B (producer profile vetting) |
| R-012 | CONFIRMED | S2 | S2 | Yes | R-011 | B (two-pass producer) |
| R-013 | CONFIRMED | S2 | S2 | Yes | Q-006, Q-028 | A (contract erratum) |
| R-014 | CONFIRMED | S2 | S2 | Yes | ISSUE-CP5-020 | B (provider-dict passthrough) |
| R-015 | CONFIRMED | S2 | S2 | Yes | R-016 | A (contract erratum) |
| R-016 | CONFIRMED | S2 | S2 | Yes | R-015, Q-030 | B (producer param echo check) |
| R-017 | CONFIRMED | S3 | S3 | Yes (doc conflict) | — | A (owner picks one phase spec) |
| R-018 | CONFIRMED | S1 | S1 | Yes | R-010 | B (fabric downgrades Q4→Q3) |
| R-019 | CONFIRMED | S2 | S2 | Yes | R-020 | B (adapter event filter) |
| R-020 | CONFIRMED | S1 | S1 | Yes | D55, R-019 | B (fabric SUSPECTED cap) |
| R-021 | CONFIRMED | S2 | S2 | No (producer OK) | D23, D30 | A (fixture/test hardening) |

Verdicts: **53 CONFIRMED, 0 PARTIAL, 0 REJECTED, 0 DEVICE-EVIDENCE-NEEDED.** Severity differences from the auditor: R-009 (S1→S2) and Q-023 (S1→S2), justified inline.

---

# E07 — RTM (`apex/engines/e07_rtm/engine.py`)

## Q-001 — Q5 granted in degraded temporal mode

**Auditor claim.** "The E12-less branch yields `degraded=True/E12_UNAVAILABLE_DEGRADED_QX` but the Q5 gate only looks at the local `is_overlap`; with 120 valid candles, 5 ordered confirmations, 14:00 UTC and no provider, `bundle=Q5`."
**What I read.** `apex/engines/e07_rtm/engine.py:685–755` (`utc_activity_window_check` degraded local-registry branch), `798–824` (quality ladder — reads `kz_info["is_overlap"]` only, never `degraded`/`source`), `1159–1196`; `tests/integration/test_cp4_engines.py:171–182` (only tests non-overlap time).
**Reproduction.** `AUDIT/probes_V9/Q-001.py` → `.out`: no provider, 14:00 UTC overlap ⇒ bundle quality **Q5** with `kz_info.degraded=True`, `source=LOCAL_DEGRADED`; identical snapshot_id with a contract-shaped stub provider.
**Verdict and reasoning.** CONFIRMED. The real engine emitted Q5 from the explicitly non-authoritative branch; nothing in the ladder consumes the degraded flag.
**Root cause.** Quality ladder predicate is `is_overlap and mtf_align>=0.9 …` (per APEX_GEN5.md L8730) with no provenance term; the degraded marker is decorative downstream of `utc_activity_window_check`.
**Direct impact.** Temporally unverified bundles publish as top-quality Q5 whenever E12 wiring is absent/broken at 12:30–16:00 UTC.
**Secondary effects and interactions.** Fabric/setup weighting (D56 lambda table keyed on Q) over-weights these bundles; combines with Q-007 (identity ignores provenance) so degraded and authoritative runs collide into one snapshot_id.
**Contract and decisions.** APEX_GEN5.md L8490: "Q5 Diamond: … Killzone overlap …"; L8318 quality scored against "Killzone/temporal alignment". The contract presumes an authoritative temporal source; ISSUE-CP4-005 (provider contract) resolved plumbing, not the gate.
**Frozen status and non-frozen alternative.** Gate fix is in frozen `apex/engines/e07_rtm/engine.py`. Non-frozen alternative: producer (`apex/ops/engine_context.py` E07 section) refuses to call E07 without a live `E12TemporalProvider`, or a fabric-side rule caps quality at Q4 when `kz_info.degraded` is true (the flag is present in the result payload).
**Fix options.** A) In-engine: require `not kz_info["degraded"]` for Q5 — frozen, plus golden fixture churn. B) Producer/fabric cap Q4 on `degraded=True` — no frozen files, no fixture churn, but the engine still self-reports Q5 in direct API use. C) Owner decision to declare degraded-Q5 acceptable — must be written into APEX_GEN5.
**My recommendation.** B now, A at the next unfreeze window.
**Acceptance and regression tests.** Same 5-confirmation chain at 14:00: with real E12 ⇒ Q5; provider absent/raising ⇒ ≤Q4 with machine-readable provenance; 09:00 both non-Q5; snapshot lineage distinguishes the two sources (ties to Q-007 test).

## Q-002 — Po3 bundle built while `is_range=False`

**Auditor claim.** "`run_engine` computes `range_info` but uses it only for EV_RTM_001, not for building Po3; with `range.is_range=False/reason=RANGE_CONDITION_UNMET_QX` and five confirmation names, `bundle=Q5/EV_RTM_004` was built."
**What I read.** `e07_rtm/engine.py:466–547` (range helper), `853–898` (bundle build — consumes confirmation names only), `1164–1185` (EV_RTM_004 append unconditioned on range); `tests/fixtures/e07_golden_fixtures.json` "RANGE_FAIL_VOL_HIGH" (helper-only); producer `apex/ops/engine_context.py:1637–1688`.
**Reproduction.** `AUDIT/probes_V9/Q-002.py` → `.out`: window engineered so `range_info["is_range"]=False`, `reason=RANGE_CONDITION_UNMET_QX`, yet result contains a bundle and `EV_RTM_004`.
**Verdict and reasoning.** CONFIRMED — the Accumulation leg of Po3 is never actually gated on a valid range.
**Root cause.** `run_engine` treats `range_info` and the confirmation-chain scorer as parallel, unlinked computations.
**Direct impact.** Po3 completion is claimable without contractual Accumulation; insufficient history can still yield bundles if names are present.
**Secondary effects and interactions.** E07-native collects E01/E02/E03/E05 inputs separately (producer L1637–1688), so their union does not guarantee a valid range either; interacts with Q-005 (chain integrity) and Q-007 (identity).
**Contract and decisions.** APEX_GEN5 Po3 section requires Accumulation (range) → Manipulation → Distribution as ordered phases; EV_RTM_004 trigger text presumes the completed structure.
**Frozen status and non-frozen alternative.** In-engine gating is frozen. Non-frozen: producer computes/validates range from the same window and skips `collect(E07)` (or tags the frame) when `is_range=False`.
**Fix options.** A) In-engine: condition bundle build on `range_info["is_range"]` — frozen, fixture updates required. B) Producer-side pre-gate — single non-frozen path, but direct-API callers stay exposed.
**My recommendation.** B; document the API hazard in the CP-4 handoff erratum.
**Acceptance and regression tests.** 101+ bar window with sweep/BOS/FVG but high VolRatio or failed range must not produce a complete/ACTIVE Po3; a genuinely compressed PIT window with the linked chain must pass.

## Q-003 — No staleness bound; stale confirmations recycled as fresh

**Auditor claim.** "The confirmation filter is only `t_confirm<=as_of`; `update_bundle_fate` is never called in batch/native. After 30 closed candles, the same old confirmations rebuilt an `active/age_bars=0/Q4` bundle with a fresh event_time; expiry=20 was bypassed."
**What I read.** `e07_rtm/engine.py:341–368` (`update_bundle_fate` — exists), `935–956` (`build_order_map` first-per-cid), `1164–1196`, `1292–1310`; `grep -rn update_bundle_fate` ⇒ no caller outside its definition/`__all__`. Producer L1637–1688, L1862–1884 windows up to 300 candles.
**Reproduction.** `AUDIT/probes_V9/Q-003.py` → `.out`: +30 candles after the last confirmation ⇒ same bundle re-emitted `fate=active`, `age_bars=0`, fresh event_time; `update_bundle_fate` confirmed dead code by caller grep in-probe.
**Verdict and reasoning.** CONFIRMED. The expiry constant exists (APEX_GEN5.md L8808 "time>expiry=20 bars → expired", L8884 `bundle_expiry_bars` default 20) but nothing enforces it on the emission path.
**Root cause.** Fate lifecycle was implemented as an orphan helper; batch driver re-derives "active" from scratch each call.
**Direct impact.** Stale evidence is perpetually reborn as fresh & active; age-based decay in fabric measures the new event_time, not the confirmations' age.
**Secondary effects and interactions.** D54 (per-TF evidence expiry in bars) operates downstream on the wrong timestamp; conditional setup scoring can act on an obsolete direction.
**Contract and decisions.** APEX_GEN5.md L8808/L8884 (expiry=20, governed); D54.
**Frozen status and non-frozen alternative.** Engine fix frozen. Non-frozen: fabric/producer computes `age = as_of − max(t_confirm)` from the order_map (already in the payload) and expires/downgrades before admission.
**Fix options.** A) In-engine: call `update_bundle_fate` in `run_engine` — frozen. B) Fabric ageing rule on `order_map` timestamps — non-frozen, single data source, works for replay too.
**My recommendation.** B.
**Acceptance and regression tests.** At 20/21/30 candles after the last confirmation with no new events, the governed expiry must apply; no re-issued `active` bundle without a fresh chain reaches the fabric.

## Q-004 — MSS confirmed regardless of distance; `mss_confirmed` dead

**Auditor claim.** "`mss_confirmed(100,200,2,≈1)=False` but `run_engine(framework_id=RTM.MSS.v1)` built a Q5 bundle from the same sweep/CHoCH; the proximity helper has no caller; native takes `p_confirm` from the candle close, not the real sweep/pivot price."
**What I read.** `e07_rtm/engine.py:555–569` (`mss_confirmed`, `mss_proximity`), `853–884`, `1159–1185`; caller grep ⇒ both helpers uncalled. Producer L1640–1659 builds confirmation prices from `close`.
**Reproduction.** `AUDIT/probes_V9/Q-004.py` → `.out`: helper returns False at |Δp|=50·ATR while `run_engine` under `RTM.MSS.v1` still emits a bundle from the same events; caller-absence asserted.
**Verdict and reasoning.** CONFIRMED.
**Root cause.** The MSS framework path reuses the generic name-chain scorer; the MSS-specific predicates were written but never wired.
**Direct impact.** MSS declared far from any valid liquidity; in native, even the price fed in is a close proxy.
**Secondary effects and interactions.** Only reachable natively if the MSS framework is selected (current native default is Po3), so present blast radius is API/batch; if enabled later, zone/direction evidence would be baseless.
**Contract and decisions.** APEX_GEN5 MSS spec requires proximity (≤0.5·ATR) to the swept level with concurrent ATR20.
**Frozen status and non-frozen alternative.** Engine wiring frozen. Non-frozen: producer supplies true sweep/pivot prices and refuses `RTM.MSS.v1` until the gate exists.
**Fix options.** A) In-engine: wire `mss_confirmed` into the MSS branch — frozen. B) Producer: block framework selection + feed real prices — non-frozen. Single sensible path is A eventually; B is the interim guard.
**My recommendation.** B now, A at unfreeze.
**Acceptance and regression tests.** Same confirmations: distance ≤0.5·ATR passes; larger distance or missing ATR is rejected fail-closed; parent price and PIT time readable in order_map.

## Q-005 — EV_RTM_011 "full hunt chain" without retest

**Auditor claim.** "Integrity ≥0.7 and coverage ≥0.6 alone emit EV_RTM_011; with sweep→choch→fvg→vol_confirm and no retest, the bundle and EV_RTM_011 were emitted and `missing=[retest]` remained."
**What I read.** `e07_rtm/engine.py:93–114` (catalog text "full hunt chain"), `185–200` (chain integrity math), `853–884`, `1180–1189` (emission on thresholds only).
**Reproduction.** `AUDIT/probes_V9/Q-005.py` → `.out`: 4-of-5 chain, integrity 0.833 ≥ 0.7 ⇒ EV_RTM_011 emitted with `missing=['retest']` in the same payload.
**Verdict and reasoning.** CONFIRMED — the event name asserts completeness the emitter does not check.
**Root cause.** Threshold-based emission vs. set-based contract semantics.
**Direct impact.** "Complete chain" event plausibly fires with a missing link; a future consumer keying on EV_RTM_011 would over-trust.
**Secondary effects and interactions.** Current wrapper only ships the generic bundle (Q-006), so the mislabeled event is confined to `result["events"]` today.
**Contract and decisions.** EVENT_CATALOG trigger text for EV_RTM_011 ("LiquidityGrabChain_Detected — full hunt chain").
**Frozen status and non-frozen alternative.** Engine frozen. Non-frozen: adapter renames/annotates the event (`partial_chain=True`) before any bus publication.
**Fix options.** A) In-engine: require all links for 011, emit a distinct partial-chain code — frozen. B) Adapter re-label — non-frozen, no fixture churn.
**My recommendation.** B until unfreeze; the catalog text must not be silently weakened (owner sign-off either way).
**Acceptance and regression tests.** Remove each link in turn ⇒ 011 refused; complete ordered chain in-window ⇒ 011; test asserts on real output, not helper.

## Q-006 — Six catalog codes unproducible from batch; wrapper drops diagnostics

**Auditor claim.** "Catalog defines EV_RTM_001…011 but batch appends only 001, 004/005, 007/011; 002/003/006/008/009/010 are never produced; the wrapper returns `[]` on `bundle=None` and even incomplete EV_RTM_005 never reaches evidence/store."
**What I read.** `e07_rtm/engine.py:93–114`, `1177–1196` (the only `events.append` sites), `1222–1245` (wrapper builds evidence solely from a non-None bundle); PHASE2_TRACEABILITY_MATRIX.md:110–117 claims catalog delivery.
**Reproduction.** `AUDIT/probes_V9/Q-006.py` → `.out`: source-level enumeration of append sites {001,004,005,007,011} + runtime confirmation that a bundle-less run yields zero EvidenceEvents.
**Verdict and reasoning.** CONFIRMED.
**Root cause.** Catalog enum was authored ahead of emitters; traceability matrix equates definition with delivery.
**Direct impact.** MSS/OTE/Judas/invalidation diagnostics are unreconstructable from the 24-field journal; replay audits blind.
**Secondary effects and interactions.** Q-005 (semantics of what *is* emitted) is separate; same pattern recurs in E09 (Q-028) and E12 (R-013) — a systemic wave-out gap.
**Contract and decisions.** Traceability matrix rows 110–117; EVENT_CATALOG §5.3.
**Frozen status and non-frozen alternative.** Emitters are frozen. Non-frozen: correct the traceability matrix / handoff docs to state actual wave-out, and have the adapter publish `result["events"]` (already returned by `run_engine`) as diagnostics.
**Fix options.** A) Contract erratum + adapter publishes journal events — non-frozen. B) In-engine full emitter build-out — frozen, large fixture surface.
**My recommendation.** A.
**Acceptance and regression tests.** Positive & negative integration per catalog code with insert/readback; a mere `EVENT_CATALOG` definition or `validate_24_fields` pass must not satisfy the test.

## Q-007 — snapshot_id collisions (direction/provenance excluded)

**Auditor claim.** "The hash payload is only `{framework_id,present,integrity,as_of_ms}`; UP and DOWN at the same t got the same ID; degraded-E12 and valid-stub runs got the same ID."
**What I read.** `e07_rtm/engine.py:283–294` (hash payload), `878–898`, `1275–1316`; `apex/data_catalog/store/sqlite_store.py:91–119` (no uniqueness guarantee — I-010).
**Reproduction.** `AUDIT/probes_V9/Q-007.py` → `.out`: direction-flipped windows and degraded-vs-stub temporal sources each produced byte-identical snapshot_ids with different payload semantics.
**Verdict and reasoning.** CONFIRMED. Symbol, timeframe, direction, parent prices/times, quality/confidence, provenance are all outside identity.
**Root cause.** Content-address chosen over a minimal core dict that predates the payload's growth.
**Direct impact.** Two contradictory facts share one identity; dedup/replay can merge them.
**Secondary effects and interactions.** Q-027 (E09) and R-003 (E10) and R-007 (E11) are the same defect class per engine; store-side provenance joins become ambiguous after a temporal-source change.
**Contract and decisions.** APEX_GEN5.md L8318: "snapshot_id follows a deterministic SHA-256 identity, for determinism" — determinism holds; *injectivity over meaning* was never specified, which is the gap. I-010 covers missing DDL uniqueness.
**Frozen status and non-frozen alternative.** Hash payload is frozen. Non-frozen: store/fabric persists a secondary `content_key` (full canonical payload hash) alongside the engine `snapshot_id`; dedup keys on the pair.
**Fix options.** A) In-engine payload widening — frozen, breaks every golden fixture hash. B) Store-side secondary identity + migration/lineage notes — non-frozen, replay-stable.
**My recommendation.** B (a plain UNIQUE constraint alone is explicitly insufficient, matching the auditor).
**Acceptance and regression tests.** Direction, E12 source, confirmation price/time, cell key changes ⇒ identity changes; exact replay ⇒ stable; every record traceable to parent.

## Q-008 — Missing calendar treated as "no conflicting news"

**Auditor claim.** "Q5 requires no news conflict but `econ_events=None` becomes an empty list and `econ_conflict=False`; native builds `E12TemporalProvider()` without a calendar and E07 without `econ_events`. No input → Q5; injecting HIGH at the same time → Q4."
**What I read.** `e07_rtm/engine.py:685–729`, `798–824`, `1143–1196`; producer L1685–1688 (no calendar arg); `e12_temporal/engine.py:1356–1381` (provider `econ_calendar=None` default).
**Reproduction.** `AUDIT/probes_V9/Q-008.py` → `.out`: identical chain — absent calendar ⇒ Q5; HIGH event at t ⇒ Q4. Native construction verified by source read.
**Verdict and reasoning.** CONFIRMED — absence-of-feed is silently equated with verified-clear.
**Root cause.** `None → [] → conflict=False` coercion at the boundary; no `calendar_state` in provenance.
**Direct impact.** The news gate passes open-loop whenever the feed is missing/stale; E12 independently emits EV_TMP_008 but E07's ladder never sees it.
**Secondary effects and interactions.** If a real calendar exists on the device but isn't wired to native, RTM confidence is systematically inflated. Actual PAPER occurrence not established (calendar data unavailable here — same limitation as auditor).
**Contract and decisions.** APEX_GEN5.md L8490 ("economic calendar clear"), L8946 ("Entry: only … with a clear economic calendar").
**Frozen status and non-frozen alternative.** Engine frozen. Non-frozen: producer policy — unavailable/stale calendar ⇒ cap Q4 (or governed fail-closed state) + `calendar_provenance` field in the frame.
**Fix options.** A) In-engine tri-state (CLEAR/CONFLICT/UNKNOWN) — frozen. B) Producer/fabric policy cap — non-frozen.
**My recommendation.** B, with the owner writing the unavailable-calendar policy into the decision log.
**Acceptance and regression tests.** Three states — verified clear, HIGH ±30min, unavailable — only the first may reach Q5; availability_time respected.

## Q-030 — Param overrides accepted without range/invariant validation

**Auditor claim.** "`get_params` rejects only unknown keys, not §6 bounds: E07 `th_int=0,th_weight=0` gave a Q0/active bundle from a lone sweep; E08 `w_position=100` made weight-sum 100.75; E09 accepted `window_macro=0`."
**What I read.** `e07_rtm/engine.py:123–177`, `e08_wyckoff/engine.py:115–189`, `e09_trend/engine.py:117–176` — all three `get_params` validate key membership only.
**Reproduction.** `AUDIT/probes_V9/Q-030.py` → `.out`: all three engines accepted the degenerate values and produced schema-valid outputs.
**Verdict and reasoning.** CONFIRMED. These are direct API overrides; native defaults inject no overrides, so PAPER today is insulated — matching the auditor's scoping.
**Root cause.** Bounds tables exist in §6 documentation but were never encoded at the entry point.
**Direct impact.** Any future settings/research-to-runtime wiring can violate quality/window invariants without error, with valid-looking evidence identity.
**Secondary effects and interactions.** R-016 shows E10's emitter ignoring overrides entirely — the two failure modes bracket each other (accept-invalid vs ignore-valid).
**Contract and decisions.** APEX_GEN5 §6 parameter governance tables (ranges + change process, L8318).
**Frozen status and non-frozen alternative.** Engines frozen. Non-frozen: a config-layer validator (in `apex/config.py` surroundings or producer) that checks type/finiteness/range/weight-sum before any params dict reaches an engine.
**Fix options.** A) In-engine validation — frozen ×3 engines. B) Shared non-frozen validator at the only ingress (producer/config) — single path.
**My recommendation.** B.
**Acceptance and regression tests.** Zero/negative/NaN, non-summing weights, window=0 ⇒ rejected with reason; allowed values replay identically with a valid parameter_version.

## Q-031 — Opposite-direction Q5 bundles coexist; resolver dead

**Auditor claim.** "`resolution_class` runs with `has_conflict=False` by default; the margin=0.1 resolver and `update_bundle_fate` are helpers with no callers; UP and DOWN runs at the same t were both Q5/active."
**What I read.** `e07_rtm/engine.py:798–824`, `901–932` (`resolve_conflicting_bundles`), `959–1008`, `1143–1196`; caller grep ⇒ resolver uncalled anywhere.
**Reproduction.** `AUDIT/probes_V9/Q-031.py` → `.out`: two contradictory Q5/active bundles at the same timestamp; resolver demonstrated functional when invoked manually, proving the gap is wiring, not math.
**Verdict and reasoning.** CONFIRMED.
**Root cause.** Conflict handling designed as a post-processor that no pipeline stage owns.
**Direct impact.** The "Q5 requires no conflict" clause is unenforced in the API; contradiction resolution depends on the caller never asking twice.
**Secondary effects and interactions.** Native currently picks one direction per request, so exposure is API/replay/multi-framework futures; Q-007 identity collisions make the two "opposites" potentially *indistinguishable* in the store — the worst pairing.
**Contract and decisions.** APEX_GEN5.md L8490 ("no conflict"), L8953 ("Algorithmic reference: `resolve_conflicting_bundles` plus expiry handling").
**Frozen status and non-frozen alternative.** Engine frozen. Non-frozen: fabric admission step runs the (existing, importable) resolver over overlapping bundles before scoring, persisting terminal fates.
**Fix options.** A) In-engine invocation — frozen. B) Fabric-side invocation of the same helper — non-frozen and reuses frozen-but-importable code.
**My recommendation.** B.
**Acceptance and regression tests.** Two opposite bundles, high overlap, margin=0.1 ⇒ contractual fate + correct Q5 denial; zero overlap ⇒ untouched.

---

# E08 — Wyckoff (`apex/engines/e08_wyckoff/engine.py`)

## Q-009 — Default-parameter entropy makes every phase AMBIGUOUS; strength = uncertainty

**Auditor claim.** "With scores in [0,1] and positive weights summing to 1, `p_max<=e/(e+7)=0.2797` and `H>=1.274>θ_H=0.85` — all phases AMBIGUOUS at defaults, Q4-from-entropy impossible; `strength=min(entropy,1)` turns uncertainty into 'strength' 1.0."
**What I read.** `e08_wyckoff/engine.py:413–498` (logit build), `940–955` (fate), `1087–1127` (quality), `1275–1314` (`strength`); `tests/unit/test_e08_wyckoff.py:217–230` (acknowledges the ceiling); ISSUE-CP4-013/014 in the traceability matrix.
**Reproduction.** `AUDIT/probes_V9/Q-009.py` → `.out`: analytic bound verified on the real softmax; observed H≈2.08 nat > 0.85 on an 8-phase run; `strength=1.0`; fate AMBIGUOUS every bar.
**Verdict and reasoning.** CONFIRMED. Known ceiling (ISSUE-CP4-013) — the *new, verified* increment is the strength inversion and the resulting permanent CANDIDATE/DEGRADED evidence.
**Root cause.** Logits confined to [0,1] cannot separate 8 classes past the entropy threshold; strength formula reuses entropy with the wrong sign convention.
**Direct impact.** Phase never ACTIVE from defaults; downstream reads high "strength" that actually encodes maximal confusion.
**Secondary effects and interactions.** CP-6 test manually promotes CANDIDATE (I-004); M-007 covers non-conversion to PAT-WYC. Q4 gate (Q-015/Q-017) is doubly unreachable.
**Contract and decisions.** APEX_GEN5.md L9106 (θ_H=0.85 nat ≡ 2.34 equally-likely regimes), L9124 (Q4 needs Entropy<θ_H and Brier<0.25).
**Frozen status and non-frozen alternative.** Logit scale/θ_H are frozen engine constants. Non-frozen: owner recalibration proposal (governance path) + interim fabric rule to not interpret E08 `strength` as conviction.
**Fix options.** A) Rescale logits (e.g. z-scored scores × OOS weights) — frozen + full re-calibration. B) Governance: recalibrate θ_H or weight scale via the §6 change process; fabric ignores `strength` meanwhile. Single real path is a calibration decision, not a patch.
**My recommendation.** B.
**Acceptance and regression tests.** A separable synthetic regime must reach H<0.85 and ACTIVE; strength must correlate positively with p_max, not with H.

## Q-010 — SOS unreachable natively (BOS same-bar key, no carry)

**Auditor claim.** "The consumer looks only at `bos_by_idx[current]` but demands `confirmed_at_idx<=current−1`; native supplies BOS at key i with `confirmed_at_idx=i` and never carries earlier events — both variants fail SOS."
**What I read.** `e08_wyckoff/engine.py` SOS branch (bos at current idx, confirmation strictly earlier); producer E08 section builds `bos_by_idx` per-bar with same-bar confirmation.
**Reproduction.** `AUDIT/probes_V9/Q-010.py` → `.out`: with same-bar-confirmed BOS ⇒ no SOS; with prior-bar BOS at the *previous* key ⇒ also no SOS (wrong key); SOS only fires with the artificial combination the producer never produces.
**Verdict and reasoning.** CONFIRMED — the two halves of the interface contradict, so the SOS state is natively dead.
**Root cause.** Index-keying convention mismatch between producer and engine plus a strict PIT inequality.
**Direct impact.** Wyckoff progression stalls before SOS/LPS/MARKUP in production paths.
**Secondary effects and interactions.** Compounds Q-009 (phases ambiguous) — the event chain and the probabilistic layer are both stuck.
**Contract and decisions.** APEX_GEN5.md L16237 explicit chain "… ST → SPRING → SOS → LPS → MARKUP …".
**Frozen status and non-frozen alternative.** Engine frozen. Non-frozen: producer carries the last confirmed BOS forward under key i with its true earlier `confirmed_at_idx`.
**Fix options.** A) Engine accepts `bos_by_idx[current-1]` — frozen. B) Producer-side carry — non-frozen, single path.
**My recommendation.** B.
**Acceptance and regression tests.** Native-shaped window with a BOS confirmed at i−1 reaches SOS; same-bar-confirmed BOS alone must not.

## Q-011 — SC event emitted same-bar without AR confirmation window

**Auditor claim.** "Contract makes SC conditional on AR within ≤5 candles and confirmed events delayed; `process_bar` emits `EV_WYK_002`, `state=SC` on the SC bar itself."
**What I read.** `e08_wyckoff/engine.py` SC branch — emission at detection bar; `detect_sc_full` docstring promises streaming confirmation.
**Reproduction.** `AUDIT/probes_V9/Q-011.py` → `.out`: SC bar emits EV_WYK_002 immediately, no AR gate applied then or retroactively.
**Verdict and reasoning.** CONFIRMED.
**Root cause.** Detection and confirmation conflated in the streaming path.
**Direct impact.** Premature SC labels; false Springs the 6-parameter contract was designed to filter re-enter through timing.
**Secondary effects and interactions.** Downstream state machine seeds from unconfirmed SC (feeds Q-012's skip problem).
**Contract and decisions.** APEX_GEN5 §events: SC requires AR follow-through ≤5 candles (L9106 six-parameter event contract).
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: adapter holds EV_WYK_002 for 5 bars and publishes confirmed/expired retroactively with PIT-honest availability_time.
**Fix options.** A) In-engine deferred confirmation — frozen. B) Adapter delay-buffer — non-frozen but shifts availability semantics (must be documented). C) Contract erratum declaring same-bar SC "candidate" semantics.
**My recommendation.** C + tests, because B silently changes event timing for consumers.
**Acceptance and regression tests.** SC with AR at +3 ⇒ confirmed at that bar; no AR by +6 ⇒ never confirmed.

## Q-012 — SPRING without SC/AR/ST; `bars_since_st=None` bypass

**Auditor claim.** "`bars_since_st=None` effectively bypasses the ≤20 condition and `_advance` doesn't forbid skipping intermediate stages; a stable range + one wick with recovery yielded EV_WYK_005 and state=SPRING with no SC/AR/ST."
**What I read.** `e08_wyckoff/engine.py` `detect_spring` (None short-circuits the ST-age check), `_advance` (no stage-order enforcement).
**Reproduction.** `AUDIT/probes_V9/Q-012.py` → `.out`: SPRING emitted from a bare range+wick, prior chain empty.
**Verdict and reasoning.** CONFIRMED.
**Root cause.** Optional-input leniency (`None` = "no constraint") plus a permissive state machine.
**Direct impact.** The most trade-adjacent Wyckoff event (Spring) fires without its causal chain.
**Secondary effects and interactions.** With Q-011, chains can be *both* premature and skipped; fabric sees a plausible EV_WYK_005.
**Contract and decisions.** APEX_GEN5.md L16237 ordered chain with explicit INVALIDATED/EXPIRED transitions.
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: fabric chain-gate — admit EV_WYK_005 only when SC/AR/ST records exist in the same episode window.
**Fix options.** A) In-engine: treat `bars_since_st=None` as fail (no ST ⇒ no Spring) — frozen, one-line semantic flip, fixture churn. B) Fabric chain gate — non-frozen.
**My recommendation.** B.
**Acceptance and regression tests.** Range+wick without ST ⇒ no Spring; full SC→AR→ST(≤20 bars)→wick ⇒ Spring.

## Q-013 — `_seen` write-only; duplicate bars mutate state and double-emit

**Auditor claim.** "`_seen` is only written, never checked before `self.bar_idx+=1`; replaying the same breakout with identical ts kept the idempotency key equal but `range.age_bars` 1→2, snapshot changed, internal event count 14→…"
**What I read.** `e08_wyckoff/engine.py` `process_bar` (adds to `_seen`, no membership test); age accounting in the final range dict.
**Reproduction.** `AUDIT/probes_V9/Q-013.py` → `.out`: same-ts bar fed twice ⇒ `age_bars` increments, events double-emit, `_seen` cardinality proves dedup key collapsed while state advanced.
**Verdict and reasoning.** CONFIRMED.
**Root cause.** Idempotency structure built but the guard clause was never written.
**Direct impact.** At-least-once delivery (normal for feeds) corrupts age/decay and duplicates evidence.
**Secondary effects and interactions.** R-004 shows the same correction/idempotency class in E10/E11/E12 — systemic.
**Contract and decisions.** Streaming idempotency requirement in the CP-4 handoff (exactly-once semantics per (ts, symbol, tf)).
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: producer dedups (ts,symbol,tf) before `process_bar` — it already tracks the window and can enforce exactly-once cheaply.
**Fix options.** A) In-engine `if key in self._seen: return replay` — frozen. B) Producer dedup — non-frozen, single path today.
**My recommendation.** B.
**Acceptance and regression tests.** Duplicate ts ⇒ byte-identical state/snapshot, no new events; distinct ts ⇒ normal advance.

## Q-014 — Historical events re-stamped with final window; identity ignores it

**Auditor claim.** "`_to_evidence` labels all historical EVs with the final window and the snapshot hashes only `(code,ts,final.state)`; the same EV_WYK_011 at t was Q3 in a 12-bar run and Q1 with new confidence after bar 13."
**What I read.** `e08_wyckoff/engine.py` `_to_evidence` (final-state stamping); age/decay observed constant (`age=0/decay=1` for every emitted event — confirmed in probe).
**Reproduction.** `AUDIT/probes_V9/Q-014.py` → `.out`: same historical event re-emitted under a longer window with different quality/confidence yet colliding identity components; every event carries age=0/decay=1.
**Verdict and reasoning.** CONFIRMED.
**Root cause.** Evidence conversion runs once at window end using only the final state.
**Direct impact.** History is rewritten per run; the same physical event has run-dependent quality with non-distinguishing identity.
**Secondary effects and interactions.** Same identity-class defect as Q-007/Q-027/R-003; decay-aware consumers (D54) receive constant zero age.
**Contract and decisions.** 24-field evidence contract requires event-time-anchored age/decay; snapshot determinism clause (L8318).
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: adapter re-stamps age/decay from `event ts vs as_of` and appends a run-window discriminator to the stored content key.
**Fix options.** A) In-engine per-event state capture — frozen, deep change. B) Adapter re-stamp + store content key — non-frozen.
**My recommendation.** B.
**Acceptance and regression tests.** Event at t evaluated at as_of t+k must show age=k and matching decay; run-length changes must not silently alter stored quality of past events.

## Q-015 — No reachable Q4/Q5: Brier never supplied, no Q5 branch

**Auditor claim.** "`_quality` needs a real Brier for Q4 but `run_full` never passes brier/labels; even with reachable entropy the driver cannot produce Q4; no path to Q5 GOLDEN exists."
**What I read.** `e08_wyckoff/engine.py:1087–1127` `_quality` (no Q5 branch at all; Q4 requires brier arg), `run_full` (never passes it).
**Reproduction.** `AUDIT/probes_V9/Q-015.py` → `.out`: quality capped at Q3 across engineered scenarios; source shows no "Q5" literal in the ladder.
**Verdict and reasoning.** CONFIRMED.
**Root cause.** Calibration inputs (labels/brier) were never plumbed; the ladder was implemented only to Q3.
**Direct impact.** Contractual quality levels are unreachable; consumers can never see E08 Q4/Q5 regardless of market behavior.
**Secondary effects and interactions.** With Q-009's entropy ceiling this is doubly dead; Q-017 shows the metric itself is mis-scaled — three independent locks on the same door.
**Contract and decisions.** APEX_GEN5.md L9124 ("Q4 STATISTICAL (Entropy<θ_H and Brier<0.25); Q5 GOLDEN (matches a fixture)").
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: contract erratum stating E08 delivers ≤Q3 in v4, so downstream weighting tables (D56) stop reserving mass for E08-Q4/Q5.
**Fix options.** A) Plumb calibration series — frozen + needs an owned label source. B) Erratum + weight-table note — non-frozen.
**My recommendation.** B.
**Acceptance and regression tests.** Test asserting max reachable Q from `run_full` is Q3 (documents reality); future unfreeze test feeding brier<0.25 must yield Q4.

## Q-016 — Transition matrix promised, never computed/published

**Auditor claim.** "The cycle contract promises `T_ij` alongside probabilities; `transition_matrix()` is a helper no one calls; CycleState/EngineBase never publish it."
**What I read.** `e08_wyckoff/engine.py` `transition_matrix` def; caller grep ⇒ zero callers (excluding E11's same-named state key); wrapper output fields.
**Reproduction.** `AUDIT/probes_V9/Q-016.py` → `.out`: caller-absence proven; runtime output contains uniform 1/9 placeholder, not a Dirichlet/χ² matrix.
**Verdict and reasoning.** CONFIRMED.
**Root cause.** Documentation asserts a delivered feature ("Verified-existing — no fix", L16237) that is only a dormant helper.
**Direct impact.** Consumers relying on transition probabilities get an uninformative uniform prior.
**Secondary effects and interactions.** The L16237 rebuttal table overstates E08 maturity — a documentation-governance risk beyond this row.
**Contract and decisions.** APEX_GEN5.md L16237 ("transition matrix T_ij … 8×8 Dirichlet with χ² independence test").
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: erratum in traceability matrix; optionally an ops-layer job calls the existing helper and stores its output as research data.
**Fix options.** A) Wire helper into `run_full` — frozen. B) Erratum + ops-side computation — non-frozen.
**My recommendation.** B.
**Acceptance and regression tests.** If published: matrix rows sum to 1 and update with observed transitions; else: docs updated and a test pins the placeholder as placeholder.

## Q-017 — Brier/log-loss divided by class count; targets trivially passed

**Auditor claim.** "Brier and log-loss are divided by the number of classes; a skill-less uniform 8-phase forecast gives BS=0.109<0.22 and log_loss≈0.26<0.65."
**What I read.** `e08_wyckoff/engine.py` calibration helpers (per-class averaging in both metrics).
**Reproduction.** `AUDIT/probes_V9/Q-017.py` → `.out`: uniform forecasts vs one-hot outcomes ⇒ BS=0.109375, log_loss=ln(8)/8≈0.2599 — both under the governance thresholds while carrying zero skill.
**Verdict and reasoning.** CONFIRMED.
**Root cause.** Metric normalization mismatch: thresholds were set for standard multiclass Brier (sum over classes), code computes the mean over classes.
**Direct impact.** Any future calibration gate keyed on these numbers auto-passes; governance "Brier<0.22" (L9370) is toothless at this scale.
**Secondary effects and interactions.** Q-015: currently nothing consumes them, which limits live impact but also hides the mis-scale.
**Contract and decisions.** APEX_GEN5.md L9124, L9370 (Brier<0.22 board gate).
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: owner rescales the governed thresholds (0.22 → 0.22/K semantics documented), or evaluation happens in research tooling with the standard formula.
**Fix options.** A) Fix formula in-engine — frozen. B) Owner threshold/definition reconciliation — non-frozen. Single path: one of the two must be chosen explicitly; silence leaves a fake gate.
**My recommendation.** B.
**Acceptance and regression tests.** Uniform forecast must FAIL the gate; a sharp correct forecast must pass; test pins the exact formula-threshold pairing chosen.

## Q-018 — Age term cancels in softmax: 0 vs 100000 bars identical

**Auditor claim.** "`score_age=exp(−λ·age)` enters all eight phase logits identically; softmax is invariant to constant shifts — with same OHLC, age 0 vs 100, probabilities and H exactly equal."
**What I read.** `e08_wyckoff/engine.py` logit assembly — the age score is added to every phase logit with the same weight.
**Reproduction.** `AUDIT/probes_V9/Q-018.py` → `.out`: age 0 vs 100000 ⇒ probability vectors byte-identical (max |Δ|=0).
**Verdict and reasoning.** CONFIRMED — the age feature is mathematically null under softmax.
**Root cause.** Feature added uniformly across classes; softmax shift-invariance eliminates it.
**Direct impact.** Cycle ageing contributes nothing to phase inference despite being a governed parameter (λ).
**Secondary effects and interactions.** Q-014's age=0 stamping means age is dead at *both* the inference and evidence layers.
**Contract and decisions.** §6 parameter table lists the age decay λ as governed (implying effect); L16237 claims EXPIRED transitions at age>96.
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: erratum documenting the null feature; any real ageing must live in the fate/expiry layer (see Q-003/D54 pattern), not the softmax.
**Fix options.** A) Per-phase age interaction terms — frozen + recalibration. B) Erratum + fabric-side ageing — non-frozen.
**My recommendation.** B.
**Acceptance and regression tests.** Pin softmax invariance (regression); ageing effects asserted at the fate layer instead.

---

# E09 — Trend (`apex/engines/e09_trend/engine.py`)

## Q-019 — Scale windows not enforced: 51 bars silently serve MACRO(240)

**Auditor claim.** "Windows are MICRO=5/SHORT=20/INTER=60/MACRO=240 but `_scale_state` slices `bars[-W:]` without requiring len≥W; with 51 candles INTER and MACRO were `state=VALID, degraded_reason=None`, evidence ACTIVE/VALID."
**What I read.** `e09_trend/engine.py` `_scale_state` (no length check; evidence claims `bars=240` regardless).
**Reproduction.** `AUDIT/probes_V9/Q-019.py` → `.out`: 51 bars ⇒ MACRO VALID with evidence metadata asserting the full window; no degradation surfaced.
**Verdict and reasoning.** CONFIRMED — including the aggravation that the payload *claims* 240 bars while consuming 51.
**Root cause.** Python negative slicing hides shortfalls; no explicit min-bars invariant.
**Direct impact.** Long-horizon "trend" is computed from short samples and presented as fully-windowed VALID evidence.
**Secondary effects and interactions.** Q-020 (warmup mislabel) compounds: both length and indicator maturity gates fail open; MTF alignment consumers get fake MACRO agreement.
**Contract and decisions.** §6 window table for E09; PIT/quality clause L8318.
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: producer refuses to request scales whose window exceeds available closed bars (it knows the window size it fetched).
**Fix options.** A) In-engine `len(bars)>=W` else DEGRADED — frozen. B) Producer min-bars gate per scale — non-frozen single path.
**My recommendation.** B.
**Acceptance and regression tests.** 51 bars ⇒ MACRO refused/degraded with true bar count in payload; 240+ ⇒ VALID.

## Q-020 — `ADX_WARMUP_QX` recorded yet state=VALID/fate=ACTIVE

**Auditor claim.** "18 ascending candles: ADX=100 from an early seed, `warmup_2n=True`, `degraded_reason=ADX_WARMUP_QX`, but all four scales `state=VALID`; wrapper gave `TREND_*_VALID, validity=VALID, fate=ACTIVE`."
**What I read.** `e09_trend/engine.py` warmup detection sets the reason string but the state ladder never consults it (reason lives only in `explanation`).
**Reproduction.** `AUDIT/probes_V9/Q-020.py` → `.out`: reproduced exactly — the QX suffix in the reason string contradicts the VALID state in the same record.
**Verdict and reasoning.** CONFIRMED.
**Root cause.** Degradation taxonomy computed as annotation, not as a gate input.
**Direct impact.** Warmup-phase ADX (pinned at 100) drives VALID/ACTIVE trend evidence.
**Secondary effects and interactions.** With Q-019 the two admission gates E09 was supposed to have are both cosmetic; Q-027 then hashes none of it into identity.
**Contract and decisions.** The engine's own `_QX` naming convention (fail-closed suffix) plus the §5 validity/fate contract.
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: fabric validity mapper — any `degraded_reason` ending in `_QX` forces validity=DEGRADED before admission.
**Fix options.** A) In-engine: reason ⇒ state coupling — frozen. B) Fabric mapping rule — non-frozen, generic across engines.
**My recommendation.** B (it also catches future reason/state drift in other engines).
**Acceptance and regression tests.** warmup_2n=True ⇒ never VALID/ACTIVE; post-warmup same series ⇒ VALID restored.

## Q-021 — Producer never passes `mom_series`; divergence permanently degraded natively

**Auditor claim.** "Native runs E10 first but neither `E09TrendEngine.compute` nor `E09.run_engine` receives `mom_series`; both paths give `divergence.degraded=True/MOMENTUM_UNAVAILABLE_DEGRADED_QX` and EV_TRD_003 is unreachable natively."
**What I read.** Producer `apex/ops/engine_context.py:1517–1523` (E09 call — context keys exclude any momentum series despite E10 having just run); `e09_trend/engine.py` divergence branch.
**Reproduction.** `AUDIT/probes_V9/Q-021.py` → `.out`: native-shaped call ⇒ `MOMENTUM_UNAVAILABLE_DEGRADED_QX` unconditionally; supplying `mom_series` flips the path, proving the engine supports it and only the producer omits it. This answers the user directive: **E09 natively receives candles/swings/BOS/OI-state but never momentum, so its divergence module is dead in production.**
**Verdict and reasoning.** CONFIRMED.
**Root cause.** Producer contract drift: E10→E09 dependency documented but the frame key was never wired.
**Direct impact.** Exhaustion/divergence diagnostics (EV_TRD_003) cannot occur natively; E09 quality silently capped by a missing dependency.
**Secondary effects and interactions.** Q-025 (constant 0.8 score) is currently masked by this row — fixing Q-021 alone would start emitting the *wrong* score; fix order matters.
**Contract and decisions.** PHASE2_HANDOFF_CP4.md E09 dependency list (E10 momentum input).
**Frozen status and non-frozen alternative.** Producer is NOT frozen — this is the rare row with a clean in-repo fix.
**Fix options.** A) Producer builds `mom_series` from E10's momentum_z series already computed in the same request — non-frozen, single path. Must land together with a Q-025 guard (adapter drops/flags EV_TRD_003 score).
**My recommendation.** A, sequenced after Q-025's re-labeling.
**Acceptance and regression tests.** Native integration: E10 healthy ⇒ E09 divergence non-degraded and EV_TRD_003 reachable; E10 absent ⇒ explicit degraded reason retained.

## Q-022 — Missing ATR coerced to 0 ⇒ `pos` explodes yet stays "finite/valid"

**Auditor claim.** "Wrapper turns absent `atr` into zero; `pos=(C−SMA)/max(ATR,1e−12)` hit ≈8×10¹¹ for 51 ascending candles vs 0.4 with ATR=2; output remains finite with a valid snapshot; the missing-E04 cause is invisible at scale level."
**What I read.** `e09_trend/engine.py` wrapper default `atr=0`; pos formula with epsilon denominator.
**Reproduction.** `AUDIT/probes_V9/Q-022.py` → `.out`: pos ≈10¹¹ with schema-valid output and no degradation flag; strength saturates to 1.0.
**Verdict and reasoning.** CONFIRMED.
**Root cause.** Epsilon-guard designed for numeric safety repurposed as a semantic default for a *missing* dependency.
**Direct impact.** Position/strength metrics meaningless when E04(ATR) absent, without any marker.
**Secondary effects and interactions.** Saturated strength=1.0 feeds MTF alignment and (via D56 weights) scoring; Q-027 identity won't distinguish the poisoned run.
**Contract and decisions.** Fail-closed doctrine (QX states) in the CP-4 handoff; E04 dependency listed for E09.
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: producer refuses E09 when ATR unavailable, or injects `atr=None`-sentinel frame that the adapter converts to a degraded record.
**Fix options.** A) In-engine `atr is None ⇒ ATR_UNAVAILABLE_QX` — frozen. B) Producer guard — non-frozen.
**My recommendation.** B.
**Acceptance and regression tests.** ATR absent ⇒ degraded/refused with reason; ATR=2 baseline values regression-pinned.

## Q-023 — PIT guard ignores swing `idx` itself; phantom/future indexes accepted

**Auditor claim.** "Guard is only `confirmed_at_idx<=current_idx−1`; `idx<=confirmed_at_idx` or `idx<=current_idx−1` are unchecked; swing `idx=100, confirmed_at_idx=0` at `current_idx=10` scored (1,1). Golden FIX_01 itself has HH idx=4 confirmed_at_idx=3."
**What I read.** `e09_trend/engine.py:9720-analog` filter (`s["confirmed_at_idx"] <= current_idx-1 and s["idx"] >= current_idx-window` — a *future* idx≥current also passes the second clause); APEX_GEN5.md L10185 fixture FIX_01 (HH at idx 4 "confirmed" at 3 — confirmation before occurrence, in the contract's own fixture).
**Reproduction.** `AUDIT/probes_V9/Q-023.py` → `.out`: swing idx=10000/confirmed_at_idx=0 accepted and scored at current_idx=10.
**Verdict and reasoning.** CONFIRMED. Independent severity **S2** (auditor S1): the hole is real, but native swings are producer-derived with self-consistent indexes; exploitation requires a malformed upstream, unlike Q-019/Q-020 which misfire on ordinary data. Downgrade justified by reachability, not by correctness.
**Root cause.** One-sided PIT predicate; the contract fixture itself normalizes the inverted pair, showing the spec was never internally reviewed for `idx` sanity.
**Direct impact.** A corrupted/buggy swing feed can inject future structure that passes the "No-Future-Leak" guard.
**Secondary effects and interactions.** L10203 promises "Violating confirmed_at_idx<=current_idx−1 raises an exception" — the code filters silently instead of raising; test-vs-doc drift.
**Contract and decisions.** APEX_GEN5.md L8318 (PIT: data[t'≤t] verified by No-Future-Leak test), L10203.
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: producer swing sanitizer (`idx<=confirmed_at_idx<=current_idx-1` else drop+journal).
**Fix options.** A) In-engine two-sided guard — frozen. B) Producer sanitizer — non-frozen single path.
**My recommendation.** B; also file the FIX_01 fixture inconsistency to the owner (see X-V9 note — covered by the auditor's own text, so not double-counted).
**Acceptance and regression tests.** Future idx, inverted idx/confirmed pairs ⇒ rejected; injected future bar leaves seq_score at t unchanged (contract test L10203 made real).

## Q-024 — Divergence pairs peaks with no recency/co-window constraint

**Auditor claim.** "`divergence_exhaustion_check` uses neither `current_idx` nor `divergence_min_peak_distance=5`; last two price swings at idx 2 and 4 compared against momentum samples near t=40."
**What I read.** `e09_trend/engine.py` divergence helper — takes last-two of each list independently, no index arithmetic against `current_idx`.
**Reproduction.** `AUDIT/probes_V9/Q-024.py` → `.out`: ancient price swings (idx 2,4) + end-of-series momentum ⇒ divergence asserted at t=40.
**Verdict and reasoning.** CONFIRMED.
**Root cause.** Helper designed for aligned inputs; alignment never enforced anywhere.
**Direct impact.** "Divergence" can compare structurally unrelated epochs — the same class as E10's R-001.
**Secondary effects and interactions.** Natively dead until Q-021 is fixed — then this becomes live immediately; must be fixed in the same change set.
**Contract and decisions.** §6 `divergence_min_peak_distance` (governed, currently a no-op — parameter-without-consumer, cf. R-015).
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: producer supplies pre-aligned, recency-filtered swing/momentum pairs; owner specs the alignment rule first.
**Fix options.** A) In-engine index constraints — frozen. B) Producer-side alignment filter — non-frozen.
**My recommendation.** B, spec'd by the owner before Q-021 wiring goes live.
**Acceptance and regression tests.** Stale-pair scenario ⇒ no divergence; genuine adjacent HH/LH vs momentum ⇒ divergence; min_peak_distance actually consumed.

## Q-025 — EV_TRD_003 ships constant score 0.8, not the contract formula

**Auditor claim.** "The contract formula `Div·(1−strength)·(1−ADX/100)` exists as a helper but emission hardcodes 0.8 and checks `short.strength<0.8`, not the catalog's drop>0.2; with `short.strength=0, ADX=100` the formula gives 0 but the event said 0.8."
**What I read.** `e09_trend/engine.py:620–643,1020–1027` — helper vs emission constant; PHASE2_TRACEABILITY_MATRIX.md:129–132.
**Reproduction.** `AUDIT/probes_V9/Q-025.py` → `.out`: EV_TRD_003 score 0.8 while `exhaustion_score(...)` on identical inputs returns 0.0; helper caller-grep: dead.
**Verdict and reasoning.** CONFIRMED.
**Root cause.** Placeholder emission left in place; formula helper orphaned.
**Direct impact.** The exhaustion warning's magnitude is fictitious.
**Secondary effects and interactions.** Currently unreachable natively (Q-021); after Q-021 lands, downstream would consume the constant — sequencing hazard flagged there.
**Contract and decisions.** EVENT_CATALOG EV_TRD_003 (drop>0.2 trigger, formula score); traceability rows 129–132.
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: adapter recomputes the score via the *importable frozen helper* and overwrites/annotates before publication.
**Fix options.** A) In-engine bind emission to helper — frozen. B) Adapter recompute using `exhaustion_score` — non-frozen, zero duplication of math.
**My recommendation.** B.
**Acceptance and regression tests.** ADX=100 ⇒ score 0; low ADX + real strength-drop ⇒ formula value; constant 0.8 must fail the suite everywhere.

## Q-026 — Streaming cache keyed on `ts_close` only; contradictory inputs replay stale payload

**Auditor claim.** "Cache key is only `last.ts_last.c`. Second call with same ts/close but ATR=0, empty swings, OI=MISSING returned the previous payload object (`oi_state=AVAILABLE,pos=0.4`) with no new EV_TRD_008; validation of the second input happens after the cache."
**What I read.** `e09_trend/engine.py:927–953,1028–1047,1066–1080` — cache lookup precedes validation; key = f"{ts}_{close}".
**Reproduction.** `AUDIT/probes_V9/Q-026.py` → `.out`: reproduced object-identity of the stale payload across contradictory inputs on a reused TrendEngine.
**Verdict and reasoning.** CONFIRMED, with the auditor's own scoping intact: wrapper/native construct fresh engines per request, so PAPER is currently insulated; the hazard is any long-lived streaming embedding.
**Root cause.** Under-keyed memoization + validate-after-cache ordering.
**Direct impact.** Same-timestamp corrections are silently ignored on reused instances.
**Secondary effects and interactions.** R-004 is the same correction-semantics class in E10/E11/E12; a future streaming refactor would trip all four at once.
**Contract and decisions.** Correction/idempotency expectations in the CP-4 handoff.
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: document the fresh-instance-per-request requirement as a binding rule in the ops layer.
**Fix options.** A) In-engine full-input key — frozen. B) Ops-layer rule + lint/test forbidding engine reuse — non-frozen.
**My recommendation.** B (matches current architecture reality).
**Acceptance and regression tests.** Same ts/close with different H/L/ATR/OI/swings ⇒ cache miss or explicit correction record; exact replay ⇒ idempotent.

## Q-027 — Snapshot identity excludes state/continuity/degraded_reason

**Auditor claim.** "`TrendScale.to_canonical` hashes only REQUIRED keys; `state`, `continuity_break`, `degraded_reason` are outside, while the wrapper derives validity/fate/condition_state from state. tf_seconds=3600 VALID vs tf_seconds=10 DEGRADED gave identical snapshot ids."
**What I read.** `e09_trend/engine.py:679–694,898–924,1066–1080,1157–1199`.
**Reproduction.** `AUDIT/probes_V9/Q-027.py` → `.out`: VALID and DEGRADED records with byte-equal snapshot ids (metadata-injected timing, as the auditor disclosed).
**Verdict and reasoning.** CONFIRMED.
**Root cause.** Identity payload frozen to the REQUIRED schema subset while semantics grew into state fields.
**Direct impact.** Store/replay/dedup cannot recover validity from identity; corrections can overwrite opposite-validity records.
**Secondary effects and interactions.** Family: Q-007, Q-014, R-003, R-007. Q-020 separately shows the state itself can be wrong — two independent layers of unreliability.
**Contract and decisions.** Snapshot determinism clause (L8318); 24-field evidence contract validity/fate fields.
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: store-side composite content key (engine snapshot_id + state/reason/continuity digest) — same remedy as Q-007; one design, four engines.
**Fix options.** A) In-engine canonical widening — frozen, fixture churn. B) Store-side composite key — non-frozen, uniform.
**My recommendation.** B.
**Acceptance and regression tests.** State-changing metadata ⇒ traceable ID/lineage change; identical runs ⇒ stable hash.

## Q-028 — E09 wrapper drops the EV_TRD_* catalog from the bus

**Auditor claim.** "Driver produces EV_TRD_005 / EV_TRD_008 on 51 bars, but the wrapper returns only four `TREND_{SCALE}_{STATE}` events; no EV_TRD_001…008 reach the 24-field pipeline; native `collect(E09,...)` uses the same wrapper."
**What I read.** `e09_trend/engine.py:91–108,927–1028,1106–1127,1157–1199`; producer L1517–1523 (uses wrapper output; `result["events"]` stays in the in-memory frame). This completes the Q-021/Q-028 directive: **natively, E09's catalog events exist only inside the frame dict and are never persisted or published.**
**Reproduction.** `AUDIT/probes_V9/Q-028.py` → `.out`: run_engine journal non-empty; `compute()` returns only TREND_* records; set difference printed.
**Verdict and reasoning.** CONFIRMED.
**Root cause.** Same wave-out gap pattern as Q-006/R-013.
**Direct impact.** Initiation/exhaustion/conflict/OI alerts unsearchable in the journal; OI state and E10-absence cause not machine-readable in scale records.
**Secondary effects and interactions.** "Event catalog delivered" claims in the matrix overstate reality; observability and event-driven consumers.
**Contract and decisions.** PHASE2_HANDOFF_CP4.md:74–81; EVENT_CATALOG §5.3.
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: adapter publishes `result["events"]` with state/time/parent/version, or the contract states explicitly that E09's bus surface is TREND_* only.
**Fix options.** A) Adapter publication — non-frozen. B) Contract scope erratum — non-frozen. Either is single-path; both need owner choice.
**My recommendation.** A if consumers exist, else B.
**Acceptance and regression tests.** Per mandatory EV_TRD code: positive/negative scenario to EvidenceEvent + store readback, or a pinned scope note in the matrix.

## Q-032 — `bos_ok=bool(bos_event)`: direction/kind/age never checked

**Auditor claim.** "EV_TRD_001 initiation uses `bos_ok=bool(bos_event)`; a bearish BOS at idx 1 — or even a dict with kind=CHoCH — triggered initiation for four scales on an ascending trend; BOS=None gave nothing."
**What I read.** `e09_trend/engine.py:979–991`; producer L1448–1452 (passes the last BOS of the whole window).
**Reproduction.** `AUDIT/probes_V9/Q-032.py` → `.out`: stale bearish BOS and a CHoCH-kind dict both satisfied `bos_ok` on an uptrend; None suppressed the event.
**Verdict and reasoning.** CONFIRMED.
**Root cause.** Truthiness used where a typed predicate (kind==BOS ∧ direction==trend ∧ fresh ∧ confirmed) was required.
**Direct impact.** In the diagnostic API, an unrelated BOS validates trend initiation; native feeds "last BOS in window" — exactly the shape that trips this.
**Secondary effects and interactions.** Contained today by Q-028 (events not published); becomes live the moment the bus gap is closed — another sequencing coupling.
**Contract and decisions.** EVENT_CATALOG EV_TRD_001 trigger (fresh, same-direction, confirmed BOS).
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: producer filters the BOS it passes (same-direction, within governed age) — single insertion point.
**Fix options.** A) In-engine predicate — frozen. B) Producer BOS filter — non-frozen.
**My recommendation.** B.
**Acceptance and regression tests.** Fresh same-direction BOS ⇒ EV001; bearish/stale/CHoCH/future ⇒ none; E01 parent traced.

---

# E10 — Momentum (`apex/engines/e10_momentum/engine.py`)

## R-001 — Divergence pivots paired with no temporal constraint

**Auditor claim.** "The last two price pivots and last two momentum pivots are chosen independently; no index/time proximity, no co-epoch requirement. Price pivots [43,90] with momentum [90,99] reached a Q4 divergence."
**What I read.** E10 divergence assembly — price-pivot pair and momentum-pivot pair selected independently from their own series; no cross-index arithmetic.
**Reproduction.** `AUDIT/probes_V9/R-001.py` → `.out`: unit-level pivot injection — price pivots at idx 10/40 vs momentum at 90/118 accepted as one divergence.
**Verdict and reasoning.** CONFIRMED (same defect class as Q-024, independently present in E10).
**Root cause.** Pairing algorithm assumes co-generated pivot streams; nothing enforces it.
**Direct impact.** Divergence evidence can straddle unrelated market epochs and still earn Q4 (see R-018 for the Q4 laxity multiplier).
**Secondary effects and interactions.** With R-018, a temporally incoherent divergence can carry the highest runtime badge E10 issues.
**Contract and decisions.** E10 §divergence spec (pivot correspondence implied); governed `divergence_min_peak_distance`-style constraints absent from the consumer.
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: producer-level pairing filter (max index distance / same-window requirement) before evidence admission.
**Fix options.** A) In-engine pairing constraint — frozen. B) Producer/adapter filter on the emitted pivot metadata — non-frozen.
**My recommendation.** B.
**Acceptance and regression tests.** Cross-epoch pivot sets ⇒ refused; adjacent aligned pivots ⇒ divergence; boundary distance pinned.

## R-002 — Volume/participation aux series lag price by one bar

**Auditor claim.** "In `reference_mode=volume`, `vz_hist[-1]` (and in participation mode `last_mv_z`) reaches `_aux_value` before the current candle's indicator update; momentum pivots and the OLS window trail price by one candle. RSI/velocity have no such lag."
**What I read.** E10 `_aux_value` call ordering relative to indicator update in the streaming loop.
**Reproduction.** `AUDIT/probes_V9/R-002.py` → `.out`: volume-mode aux at bar t equals the z-value of bar t−1 (verified numerically); RSI mode aligned at t.
**Verdict and reasoning.** CONFIRMED (volume mode reproduced; participation mode verified by identical source pattern).
**Root cause.** Read-before-update sequencing for a subset of reference modes.
**Direct impact.** Mode choice silently changes the time base of divergence detection — cross-mode results are not comparable.
**Secondary effects and interactions.** Interacts with R-001: a one-bar-lagged aux stream widens the unconstrained-pairing damage.
**Contract and decisions.** §PIT clause (single time base per computation) L8318.
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: contract erratum documenting the one-bar lag per mode so research/backtests model it faithfully.
**Fix options.** A) Reorder update/read in-engine — frozen, changes goldens. B) Erratum + producer chooses RSI/velocity modes natively — non-frozen.
**My recommendation.** B.
**Acceptance and regression tests.** Per-mode alignment test asserting aux(t) uses data through the documented bar.

## R-003 — snapshot_id excludes param_hash/flags/MACD/state

**Auditor claim.** "`snapshot_id` derives from a core of v/a/mz/mvz/rsi/as_of/symbol/interval/q; `param_hash`, flags, MACD, full state are unbound. GF04 with close→850: `impulse_z=2` emitted EV_MOM_001, `impulse_z=4` did not — snapshot identical."
**What I read.** E10 core-dict builder; `param_hash` computed but not hashed into identity.
**Reproduction.** `AUDIT/probes_V9/R-003.py` → `.out`: `impulse_z` 2 vs 99 (both governed-range) ⇒ different events, identical snapshot_id.
**Verdict and reasoning.** CONFIRMED — identity family (Q-007/Q-027/R-007), aggravated: *behavior-changing parameters* are outside identity.
**Root cause.** Minimal core dict + params treated as ambient config.
**Direct impact.** Replays under different governed parameters collide; event/no-event runs are identity-equal.
**Secondary effects and interactions.** R-016 (emitter ignores overrides) partially masks this natively — defaults always apply — but research/API runs collide immediately.
**Contract and decisions.** L8318 determinism/identity; §6 parameter governance (parameter_version should bind outputs).
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: store-side composite key including `param_hash` (already emitted in the payload).
**Fix options.** A) In-engine core widening — frozen. B) Store composite key — non-frozen, consistent with Q-007/Q-027 remedy.
**My recommendation.** B.
**Acceptance and regression tests.** Param change within governed range ⇒ distinct stored identity; exact replay ⇒ stable.

## R-004 — Same-timestamp corrections: dedup precedes validation

**Auditor claim.** "E10's cache sees only close_time and E11 only as_of *before* validation; E12 after its narrow guard dedups on (ts,as_of) ignoring OHLCV changes. E10 returned the old snapshot with `pit.duplicate=True` even for an H<L correction; cold replay gave a fresh ID."
**What I read.** E10 dedup-then-validate ordering; E11 as_of key; E12 `on_candle` replay branch (source L1030–1075: dup (ts,as_of) ⇒ replay prior state regardless of OHLCV deltas).
**Reproduction.** `AUDIT/probes_V9/R-004.py` → `.out`: E10 same-hour corrected candle (even invalid geometry) ⇒ prior snapshot replayed as duplicate; validation never ran on the correction.
**Verdict and reasoning.** CONFIRMED (E10 executed; E11/E12 legs verified in source at the cited lines — same key-only dedup).
**Root cause.** Idempotency implemented as timestamp-equality, not content-equality; ordering places it before geometry checks.
**Direct impact.** Exchange corrections at the same timestamp are silently discarded; warm vs cold replay diverge (duplicate vs fresh ID).
**Secondary effects and interactions.** Q-013 (E08) and Q-026 (E09) complete the six-engine picture: no engine handles corrections coherently.
**Contract and decisions.** CP-4/CP-5 idempotency clauses; correction policy is an owner gap (no D-item covers it).
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: producer-level correction policy — content-hash the candle; same ts + different content ⇒ versioned re-emit or explicit refusal, journaled.
**Fix options.** A) In-engine content-aware dedup ×3 engines — frozen. B) Single producer correction gate — non-frozen.
**My recommendation.** B, plus an owner decision on correction semantics (currently unspecified).
**Acceptance and regression tests.** Same ts + changed OHLCV ⇒ correction record or refusal (never silent duplicate); byte-identical replay ⇒ duplicate.

## R-005 — Geometry gate: V<0, C>H, C=inf pass the direct API

**Auditor claim.** "E10 accepted V<0 with Q2 and `volume_ratio=-0.0105…`; `validate_state_schema` would reject the same output; C>H / close=Inf not adequately refused (volume=Inf errored in hashing). E12 with C>H or O>H returned valid Q1/ID."
**What I read.** E10 `_validate_candle` (checks a narrow subset); E12 `on_candle` guard (ts invalid, H<L, V<0 only — C>H unchecked, source L1030–1060).
**Reproduction.** `AUDIT/probes_V9/R-005.py` → `.out`: E10 produced states from v=−500, close>high, close=inf; the repo's own `validate_state_schema` rejects the v<0 output — engine and validator disagree.
**Verdict and reasoning.** CONFIRMED (E10 executed; E12 leg source-verified: its Q0 guard enumerates H<L and V<0 but not C∉[L,H]).
**Root cause.** Validation checklists diverged from the schema validator; nobody runs the validator inline.
**Direct impact.** Malformed feed data yields quality-graded evidence with negative/infinite internals.
**Secondary effects and interactions.** R-004 means a *later corrected* version of the same bad bar is then ignored — the two rows compound into "garbage in, garbage kept".
**Contract and decisions.** §8.1 candle geometry (L≤O,C≤H; V≥0; finite).
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: producer runs full geometry validation (or the existing `validate_state_schema` on output) before admission.
**Fix options.** A) In-engine full geometry check — frozen. B) Producer pre-gate + output schema validation — non-frozen, reuses existing validator.
**My recommendation.** B.
**Acceptance and regression tests.** Each malformed field ⇒ refusal with reason; valid candle ⇒ unchanged goldens.

## R-015 — `mom_window` governed but never consumed (E10); E12 twins

**Auditor claim.** "E10's `mom_window` exists at the param/hash level but momentum_z and warmup use `z_window`; 5 vs 60 changed only param_hash, not numbers/events. E12's `vol_burst_threshold`/`range_z_threshold` are defined and range-checked but `compute_temporal_profile` takes pre-boolean cond_events."
**What I read.** E10 param table and `momentum_z` (`z_window` only; `mom_window` read nowhere); E12 param registry vs profile builder inputs.
**Reproduction.** `AUDIT/probes_V9/R-015.py` → `.out`: `mom_window` 5 vs 60 ⇒ byte-identical outputs/events, differing param_hash only; source grep: zero reads of `mom_window`.
**Verdict and reasoning.** CONFIRMED.
**Root cause.** Parameter registered for governance before (or instead of) its consumer.
**Direct impact.** Governance table promises a lever that does nothing; param_hash varies meaninglessly (touches R-003's identity story from the other side).
**Secondary effects and interactions.** R-016 is the mirror image (consumer ignores the override system); together they falsify the §6 table for E10.
**Contract and decisions.** §6 parameter table (every governed parameter has a determination method and sensitivity — implying effect).
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: erratum in the §6 table marking dead parameters; research must not tune them.
**Fix options.** A) Wire or remove in-engine — frozen. B) Documented dead-parameter list — non-frozen.
**My recommendation.** B until unfreeze.
**Acceptance and regression tests.** Sensitivity smoke test: each governed param must alter some output on a reference window, or be listed as dormant.

## R-016 — Emitter uses defaults, not run overrides (th_imp=2.0, p_default())

**Auditor claim.** "`_to_evidence` takes the strength threshold from default `p_impulse()`≈2 and z_window/decay/lineage from `p_default()`, not run_engine's params; `momentum_state_projection` fixes θ=2."
**What I read.** E10 `_to_evidence` and projection code — literal `2.0`/`p_default()` calls, run params not threaded.
**Reproduction.** `AUDIT/probes_V9/R-016.py` → `.out`: `impulse_z=3` override — state layer honors 3, evidence layer graded against 2; mismatch shown on one bar (event emitted by one layer, not the other).
**Verdict and reasoning.** CONFIRMED.
**Root cause.** Evidence emitter written against module defaults; params object never passed down.
**Direct impact.** Overridden runs emit evidence inconsistent with their own state (and with the param_hash they advertise).
**Secondary effects and interactions.** With Q-030 (no bounds validation) and R-015 (dead params), E10's parameter story is unreliable end-to-end; natively defaults are used, so today's PAPER output is self-consistent by accident.
**Contract and decisions.** §6 override/versioning process.
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: producer verifies emitted `parameter_version/param_hash` equals the requested one and refuses override runs (defaults-only policy) until unfreeze.
**Fix options.** A) Thread params through emitter — frozen. B) Producer param-echo check + defaults-only policy — non-frozen.
**My recommendation.** B.
**Acceptance and regression tests.** Override run: state and evidence graded against the same θ; param echo equals request.

## R-018 — Q4 from "BOTH + n≥100" alone; Wilson/OOS helpers dead

**Auditor claim.** "§5.2 requires two-method agreement AND OOS measurement with success rate/Wilson CI for Q4; runtime grants Q4 from BOTH + candle count ≥100. 111 LCG candles with only OHLCV gave EV_MOM_003 q_tag=Q4 with no calibration/CI input; §4 pseudocode has the same shortcut."
**What I read.** E10 quality ladder (double-gate only); `wilson_ci` and related helpers — caller grep: dead.
**Reproduction.** `AUDIT/probes_V9/R-018.py` → `.out`: Q4 achieved from synthetic OHLCV with zero statistical inputs; helper caller-absence asserted.
**Verdict and reasoning.** CONFIRMED. Independent severity stays S1: Q-tags feed quality weights (D56) and E10 evidence is natively live.
**Root cause.** Ladder implemented to the pseudocode shortcut, not the prose contract; the prose/pseudocode conflict is in the contract itself.
**Direct impact.** "STATISTICAL" badge with no statistics; downstream weighting over-trusts E10.
**Secondary effects and interactions.** R-001/R-002 defects can ride a Q4 badge; APEX_GEN5 L1271 defines Q4 as "has a Wilson CI" — the badge is falsifiable by its own definition.
**Contract and decisions.** APEX_GEN5.md L1271/L1372 (Q4=STATISTICAL, Wilson CI; Q5=OOS_CALIBRATED); §5.2 vs §4 internal conflict.
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: fabric downgrades E10 Q4→Q3 until CI wiring exists (single mapping rule), plus contract reconciliation by the owner.
**Fix options.** A) In-engine CI computation — frozen + needs outcome labels. B) Fabric downgrade rule + erratum — non-frozen.
**My recommendation.** B.
**Acceptance and regression tests.** Q4 only with a CI object present in payload; LCG-OHLCV-only run caps at Q3.

---

# E11 — Regime (`apex/engines/e11_regime/engine.py`)

## R-006 — Silent fallback from governing YAML to hardcoded defaults

**Auditor claim.** "`get_params()` swallows every Exception from `load_params().e11_params` and silently returns defaults. Healthy YAML: θ_H/Q2/Q5 = 1.105878/1.229880/0.564415 with three yaml_assertions; injected ValueError: 0.65/0.8/0.4 and zero assertions."
**What I read.** `e11_regime/engine.py` `get_params` (bare `except Exception: pass` around the loader; imports `load_params` inside the function); `apex/config.py` loader; `params/e11_params_v4.yaml` (frozen, governing).
**Reproduction.** `AUDIT/probes_V9/R-006.py` → `.out`: real loader path returns the YAML thresholds (θ_H=1.105878, Q2=1.229880, Q5=0.564415, 3 assertions); monkeypatched loader failure ⇒ silent defaults 0.65/0.8/0.4, `yaml_assertions=[]`, no warning, no journal event. Directive satisfied: probe uses the **real** `apex/config.py` + frozen YAML.
**Verdict and reasoning.** CONFIRMED. No claim is made that the YAML currently fails on the device — the finding is the absent failure surface.
**Root cause.** Defensive try/except written as availability convenience over a *governing* configuration file.
**Direct impact.** A YAML syntax error / path issue would silently swap D49-governed thresholds (θ_H range 0.3–ln9) for unblessed defaults — quality ladder and hysteresis change with zero observability.
**Secondary effects and interactions.** R-007 (params outside identity when artifact sha present) means the swap would not even change snapshot ids; D47 acceptance gates (acc≥.70 etc.) validated against YAML values, not defaults.
**Contract and decisions.** D49 (θ_H governance, ISSUE-CP14-066 OPEN); D47; frozen-file list includes `e11_params_v4.yaml`.
**Frozen status and non-frozen alternative.** Engine frozen. Non-frozen: boot-time assertion in ops (`get_params().theta_H == yaml value`) that refuses startup on mismatch — three lines outside frozen paths.
**Fix options.** A) In-engine: raise/journal on loader failure — frozen. B) Boot self-test comparing engine params to the YAML — non-frozen (fits the ISSUE-077 boot self-test slot).
**My recommendation.** B immediately.
**Acceptance and regression tests.** Corrupt YAML ⇒ boot refuses with explicit reason; healthy YAML ⇒ thresholds equal file values; defaults never silently active.

## R-007 — classifier_artifact_sha256 REPLACES the param digest in identity

**Auditor claim.** "If `classifier_artifact_sha256` is supplied, `_phash` becomes that checksum of W/b/fit_protocol and `param_hash(self.p)` is not in the snapshot payload; same artifact + different thresholds ⇒ different param_hash but equal `_phash`."
**What I read.** `e11_regime/engine.py` `_phash` selection logic (artifact sha short-circuits the param digest).
**Reproduction.** `AUDIT/probes_V9/R-007.py` → `.out`: two runs, same artifact, thresholds differing (quality_Tur_Q3 15.5 vs 15.0) ⇒ different quality outputs, different param_hash, **identical snapshot_ids**.
**Verdict and reasoning.** CONFIRMED.
**Root cause.** Identity conflates "model weights version" with "full configuration version".
**Direct impact.** Threshold retunes are invisible in evidence identity whenever an artifact is pinned — exactly the production configuration.
**Secondary effects and interactions.** Amplifies R-006 (silent default swap also invisible); identity family Q-007/Q-027/R-003.
**Contract and decisions.** L8318 identity determinism; D47/D49 threshold governance implies threshold changes are version-relevant.
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: store-side composite key appending `param_hash` (present in payload) to the stored identity.
**Fix options.** A) In-engine `_phash = H(artifact_sha ‖ param_digest)` — frozen, fixture churn. B) Store composite — non-frozen, consistent with the family remedy.
**My recommendation.** B.
**Acceptance and regression tests.** Same artifact + changed governed threshold ⇒ distinct stored identity; same everything ⇒ stable.

## R-008 — Hamilton step: emission underflow ⇒ absorbing all-zero posterior

**Auditor claim.** "`hamilton_filter_step` divides by `sum(ξ_pred*η)+EPS`, not simplex/log-sum-exp normalization; with emission ≈1e−12 the posterior sums to ≈0.0001, not 1; with η=0 all components zero and stay zero next step."
**What I read.** `e11_regime/engine.py` `hamilton_filter_step` and `gaussian_log_emission` (linear-domain exp).
**Reproduction.** `AUDIT/probes_V9/R-008.py` → `.out`: |x−mu|≈250/dim ⇒ exp underflow ⇒ `xi_filt` exactly zeros; next step with *healthy* η stays zeros — absorbing state demonstrated on the real filter.
**Verdict and reasoning.** CONFIRMED, and strengthened beyond the audit: recovery does not occur even after inputs normalize.
**Root cause.** No log-space filtering; EPS placed to avoid ZeroDivision, not to preserve the simplex.
**Direct impact.** One pathological observation (data glitch, unscaled input) permanently kills the regime posterior for the engine instance; downstream states/qualities computed from a zero vector.
**Secondary effects and interactions.** GF_13 tests only ordinary emissions, so the suite can't catch it; with Q-026-style instance reuse the poison persists across calls.
**Contract and decisions.** Hamilton filter spec in §E11 (posterior on the simplex by definition).
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: producer watchdog — if `sum(xi_filt)==0` (payload-visible), reset the instance / refuse the state as QX.
**Fix options.** A) Log-sum-exp in-engine — frozen, gold-value churn. B) Ops watchdog + reset — non-frozen.
**My recommendation.** B now, A at unfreeze (numerically the only correct fix).
**Acceptance and regression tests.** Outlier bar then normal bars ⇒ posterior recovers to simplex; zero-vector states never admitted.

## R-019 — EV_RGM_003 "Transition_Confirmed" fired by catalog on first candle and every steady bar

**Auditor claim.** "`hysteresis_manager` names the first label CONFIRMED and steady continuation CONFIRMED; `run_engine.events` fires EV_RGM_003 only on true `last_confirmed` change, but `catalog_events(state)` — seeing only the status — fires it on the first candle and on every unchanged bar."
**What I read.** `e11_regime/engine.py` `hysteresis_manager` (`([], s)` ⇒ CONFIRMED), `run_engine` journal gating, `catalog_events` status-only trigger.
**Reproduction.** `AUDIT/probes_V9/R-019.py` → `.out`: first candle ⇒ status CONFIRMED; three stable bars: journal contains zero EV_RGM_003, `catalog_events` yields EV_RGM_003 for every bar — the two surfaces contradict.
**Verdict and reasoning.** CONFIRMED.
**Root cause.** "CONFIRMED" overloaded: hysteresis *status* vs transition *event*; catalog translates status directly into the event code.
**Direct impact.** Any consumer of catalog output sees perpetual phantom regime-transition confirmations.
**Secondary effects and interactions.** R-020 shows the complementary hole (SUSPECTED ungated) — the transition state machine leaks on both edges.
**Contract and decisions.** EVENT_CATALOG EV_RGM_003 (fires on confirmed *change*).
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: adapter filters catalog EV_RGM_003 to actual `last_confirmed` transitions (state carries the needed fields).
**Fix options.** A) In-engine status/event split — frozen. B) Adapter delta-filter — non-frozen.
**My recommendation.** B.
**Acceptance and regression tests.** Stable regime N bars ⇒ zero 003 events; genuine 3-bar-confirmed flip ⇒ exactly one.

## R-020 — SUSPECTED flip bar gets Q5; no transition input in quality

**Auditor claim.** "Contract: a change is SUSPECTED up to three candles, risk-affecting decisions must be blocked, Q5 needs the three-candle confirmation. With prior RANGE and a fresh raw label, status=SUSPECTED but `quality_score` (low H, low Tur) gives Q5 with no cap."
**What I read.** `e11_regime/engine.py` `quality_score` signature — inputs are entropy/turbulence/warmup/oi etc.; no transition-status parameter exists at all.
**Reproduction.** `AUDIT/probes_V9/R-020.py` → `.out`: settled engine (4 candles), trendiness_raw 0.1→0.7 ⇒ state_raw TREND, transition SUSPECTED — same bar graded **Q5**.
**Verdict and reasoning.** CONFIRMED. S1 upheld: Q5 regime evidence during an unconfirmed flip is directly risk-relevant (D55 confidence floor consumes regime quality downstream).
**Root cause.** Quality ladder designed orthogonally to the hysteresis machine; no plumbing between them.
**Direct impact.** The strongest quality badge coexists with the contract's own "do not act yet" state.
**Secondary effects and interactions.** With R-019, a consumer can simultaneously receive a phantom "confirmed" event and a Q5 grade on a suspected bar — worst-case composition.
**Contract and decisions.** E11 §hysteresis (3-candle confirmation); D55 (confidence floor).
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: fabric rule `transition_status==SUSPECTED ⇒ cap Q4` (status is in the state payload).
**Fix options.** A) In-engine quality input — frozen. B) Fabric cap — non-frozen one-liner.
**My recommendation.** B.
**Acceptance and regression tests.** Flip bar ⇒ ≤Q4; after 3 confirming bars ⇒ Q5 permitted; no cap when no flip.

## R-021 — D23 OI cap bypassed when `oi_state` key absent; fixtures never carry the key

**Auditor claim.** "Binding D23 forbids Q5 with partial participation when OI is not AVAILABLE; code caps Q4 only IF the `oi_state` key exists and is not AVAILABLE. GF_03 expects Q5 without the key; with H≈0 and Tur≈6.32 the real quality function returns Q5."
**What I read.** `e11_regime/engine.py` quality/participation branches (key-presence check); `tests/fixtures/e11_golden_fixtures.json` — zero occurrences of `oi_state` across all 18 fixtures; producer `apex/ops/engine_context.py` E11 section — **the native producer does populate oi_state** in the frame.
**Reproduction.** `AUDIT/probes_V9/R-021.py` → `.out`: no-key run ⇒ Q5; `oi_state=MISSING` ⇒ Q4; x_part differs by branch (0.4027 legacy vs 0.5987 D23 sigmoid) — two semantics selected by key presence; fixture scan shows the D23 branch is untested by goldens.
**Verdict and reasoning.** CONFIRMED as a latent contract bypass; the native path supplies the key, so PAPER currently honors D23 — the exposure is API/replay/fixture coverage.
**Root cause.** Backward-compatible optional key retained after D23 made the input mandatory-in-meaning.
**Direct impact.** Any caller omitting the key silently re-enters pre-D23 semantics (different x_part AND uncapped Q5).
**Secondary effects and interactions.** D30 scope note (20 base cells) unaffected; fixture blindness means a future regression removing the producer's key would pass the suite.
**Contract and decisions.** D23 (PHASE2_DECISION_LOG.md L343): oi_state≠AVAILABLE ⇒ OI weight 0, Q5 unreachable.
**Frozen status and non-frozen alternative.** Engine frozen, fixtures frozen-adjacent (tests are not on the frozen list). Non-frozen: add non-golden unit tests pinning both branches + a producer assertion that the key is always present.
**Fix options.** A) Test hardening + producer assert — non-frozen, no behavior change. B) In-engine default `oi_state=MISSING` when absent — frozen, flips legacy callers to capped semantics.
**My recommendation.** A now; B is the correct semantic at unfreeze.
**Acceptance and regression tests.** Key-absent call ⇒ (post-fix) treated as MISSING/Q4-capped; producer frame always contains oi_state; regression test fails if the key disappears.

## Q-029 — as_of ignored by engine wrappers; future candles emit past-dated requests' evidence

**Auditor claim.** "All `_resolve_window`s process context.window/provider without checking timestamp/availability against `as_of` or closedness; requesting 13:00 with a window ending 14:00 produced 14:00 events (E07 even Q5). E10 verified real; E12 via AST; E11 statically."
**What I read.** `e07_rtm/engine.py:1222–1266`, `e08_wyckoff/engine.py:1218–1259`, `e09_trend/engine.py:1106–1148`, `e10_momentum/engine.py:1436–1477`, `e11_regime/engine.py:1476–1544`, `e12_temporal/engine.py:1408–1457` (all six `_resolve_*` paths pass candles straight through); producer PIT guard L1702–1703, 2480–2485 (native-only defense).
**Reproduction.** `AUDIT/probes_V9/Q-029.py` → `.out`: **real E11** `compute(as_of="2024-01-01")` consumed a candle stamped 2026 and emitted evidence with 2026 event_time (upgrading the audit's static-only E11 claim to executed proof); **real E10** `run_engine(as_of_ms=2024)` restamped `state["as_of"]` after hashing while `pit.last_closed` remained a future bar — snapshot unchanged, label rewritten.
**Verdict and reasoning.** CONFIRMED across the family, now with all six engines either executed (E07/E08/E09/E10/E11/E12 probes in this series) or source-verified at the cited lines.
**Root cause.** as_of treated as a labeling input, not a filter; the only PIT filter lives in the native producer.
**Direct impact.** Any direct API/backtest/replay path outside the producer can leak future candles into past-dated evidence with full quality.
**Secondary effects and interactions.** I-009 (fixture timing) is adjacent but separate; E10's post-hash restamp additionally decouples identity from the as_of label (identity family echo).
**Contract and decisions.** L8318 PIT clause ("every formula reads only from data[t'≤t], verified by a No-Future-Leak test").
**Frozen status and non-frozen alternative.** Engines frozen. Non-frozen: make the producer guard the *sole* sanctioned entry (documented), and add a shared ops-layer prefilter (`candles = [c for c in candles if availability<=as_of]`) for every non-producer harness (research/backtest/replay CLIs).
**Fix options.** A) In-engine as_of filtering ×6 — frozen. B) Shared non-frozen prefilter + policy that direct compute() is not PIT-safe — single path today.
**My recommendation.** B.
**Acceptance and regression tests.** For each engine: window ending t+1 with as_of=t ⇒ refusal or filtered computation; no event_time/availability beyond t; E10/E11 manual as_of_ms restamps must either be rejected or rebuild identity coherently.

---

# E12 — Temporal (`apex/engines/e12_temporal/engine.py`)

## R-009 — "180-day" behavior window is really an 8640-RECORD cap

**Auditor claim.** "`returns_by_tod_from_candles` has no time cutoff; `_vol_ratio_for` takes the whole same-window buffer; the cap is `behavior_window*48` records, not days (H1 holds ~360 days); a 200-day-old candle produced vol_ratio=10; stale cohorts shift the factors."
**What I read.** `e12_temporal/engine.py:1122–1125` (`cap = behavior_window * n_bins`, list truncation), `1171–1177` (`_vol_ratio_for` — whole buffer, no time filter), `1180–1208` (`_historical_behavior` same), params L135 ("behavior_window: 180 # days, 30–365"); APEX_GEN5.md L12856 ("behavior_window is at most 365 days"), L12932 (PIT over [t−behavior_window, t−1] in days), L13216 — the contract's own pseudocode contains the same `behavior_window*48` record cap, i.e. the ambiguity is contractual.
**Reproduction.** `AUDIT/probes_V9/R-009.py` → `.out`: cap=8640 records; 9000 hourly candles ⇒ buffer spans **>300 days** (mandate 180); 4h candles ⇒ **>1000 days**; no time-based eviction exists in the stream class.
**Verdict and reasoning.** CONFIRMED. Independent severity **S2** (auditor S1): the error direction is inclusion of *older* history — no future leak, no crash, bounded by the cap; it biases seasonal statistics but does not create unsafe PIT behavior. S1 would require a risk-side consumer acting on the skew, which is not demonstrated.
**Root cause.** Day-denominated parameter reused as a record multiplier under an implicit "1h × 48-bin ≈ day" assumption that only holds for one timeframe — and the contract pseudocode encodes the same conflation.
**Direct impact.** Retention is timeframe-dependent: 360d@1h, ~4y@4h, ~6d@1m; vol_ratio and historical_behavior averages mix cohorts far outside the declared window.
**Secondary effects and interactions.** Profiles built from `returns_by_tod_from_candles` inherit the same unbounded lookback; R-010's lax Q4 gate can then bless the skewed profile. Also see X-V9-002 (`n_candles` output undercounts once capped).
**Contract and decisions.** APEX_GEN5.md L12856/L12932 vs L13216 (internal conflict).
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: contract erratum choosing records-or-days explicitly + producer-side pre-cut of the candle window to 180 calendar days before feeding E12.
**Fix options.** A) In-engine ts-based eviction — frozen. B) Producer 180-day pre-cut + erratum — non-frozen, exact for every timeframe.
**My recommendation.** B.
**Acceptance and regression tests.** 1m/1h/4h feeds: buffer time-span ≤180d ± one bar; vol_ratio excludes candles older than the window.

## R-010 — Q4 reachable with zero (or all-refused) conditional rates; leak check is a shuffle

**Auditor claim.** "When `cond_events` is empty or every `ci=None`, `all(... if entry['ci'])` is vacuously True; `no_future_leak_check` only shuffles sample order, not a timestamp cutoff; a profile with data in 2 of 48 bins, no CI, n=2 reached Q4."
**What I read.** `e12_temporal/engine.py:760–885` — Q ladder: Q4 = Q3 + `widths_ok` + replay + leak check, where `widths_ok = all(width<0.3 for entry in rates.values() if entry["ci"])`; `no_future_leak_check` — permutation self-test only.
**Reproduction.** `AUDIT/probes_V9/R-010.py` → `.out`: profile with `conditional_rates == {}` graded **Q4**; profile whose only rate has n=5 (`ci=None`) also **Q4**; `no_future_leak_check` source printed — shuffle-based, no timestamps.
**Verdict and reasoning.** CONFIRMED.
**Root cause.** Guard written as a comprehension filter, so absence of evidence satisfies the evidence requirement; the leak "check" tests permutation invariance of the estimator, not PIT.
**Direct impact.** The top statistical badge (per L1271, "Q4 = has a Wilson CI") is issuable with no CI anywhere in the object.
**Secondary effects and interactions.** R-011 lets such a profile attach unchecked; R-012's post-loop build then journals its quality as authoritative; E10's R-018 is the same "Q4 without statistics" pattern — a cross-engine theme.
**Contract and decisions.** APEX_GEN5.md L1271 (Q4 STATISTICAL has a Wilson CI); §5.3 profile quality ladder.
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: profile vetting in the producer/research layer — require ≥1 rate with CI and full-bin coverage before *using* a Q4 profile (downgrade otherwise).
**Fix options.** A) In-engine `widths_ok = rates and all(entry["ci"] and width<0.3 for ...)` — frozen one-liner. B) Upstream profile gate — non-frozen.
**My recommendation.** B now, A at unfreeze.
**Acceptance and regression tests.** Empty-rates profile ⇒ ≤Q3; n<min_samples-only rates ⇒ ≤Q3; genuine CI'd rates <0.3 width ⇒ Q4.

## R-011 — attach_profile validates version string only; forged Q4 propagates

**Auditor claim.** "`attach_profile` checks only version — not `as_of<=candle availability`, profile hash, provenance/bins, samples or publish time; a profile with as_of one day in the future and quality=Q4 attached to today's candle gave today's state Q4."
**What I read.** `e12_temporal/engine.py:1080–1093` (`attach_profile`: `version==CONTRACT_VERSION` is the sole gate), `_quality_for` (republishes profile quality verbatim when in Q2–Q4).
**Reproduction.** `AUDIT/probes_V9/R-011.py` → `.out`: fabricated profile (`quality=Q4`, `as_of` far future, no factors, junk snapshot) attached without error; next state graded **Q4**; only a wrong version string is rejected.
**Verdict and reasoning.** CONFIRMED. S1 upheld: this is an unauthenticated quality-injection port into every subsequent temporal state.
**Root cause.** Contract-version check mistaken for content validation.
**Direct impact.** Future-dated or content-free profiles silently drive state quality (a PIT hazard: a profile computed with future knowledge attaches to past candles in replay).
**Secondary effects and interactions.** With R-010 the system can *legitimately* mint hollow Q4 profiles, and with R-011 it can't tell hollow from solid at attach time; R-012 journals whatever arrives.
**Contract and decisions.** §5.3 profile contract (as_of, snapshot, provenance fields exist precisely to be checked).
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: producer vets profiles before attach (as_of ≤ first-candle availability, schema, quality enum, hash) — single choke point since only the producer attaches natively.
**Fix options.** A) In-engine validation — frozen. B) Producer vetting — non-frozen.
**My recommendation.** B.
**Acceptance and regression tests.** Future as_of ⇒ refused; quality outside enum ⇒ refused; well-formed historical profile ⇒ attached and effective.

## R-012 — profile_inputs built AFTER the loop: state graded Q1, profile shipped Q2+

**Auditor claim.** "With `profile_inputs`, the profile is built/attached after the `on_candle` loop and `last_state` is not recomputed; output had `temporal_profile.quality=Q2` but `temporal_state.quality=Q1`; the same profile given *before* the loop yields Q2 states."
**What I read.** `e12_temporal/engine.py:1305–1319` (post-loop build + attach + EV_TMP_006), return dict carrying both objects.
**Reproduction.** `AUDIT/probes_V9/R-012.py` → `.out`: one call ⇒ `temporal_state.quality=Q1` alongside `temporal_profile.quality=Q4` in the same result; re-run with `profile=` pre-attached ⇒ states graded Q4. (Probe produced Q4 rather than the auditor's Q2 — same mechanism, stronger contrast.)
**Verdict and reasoning.** CONFIRMED.
**Root cause.** Single-pass driver design: profile construction needs the streamed candles, but the states are not regraded afterwards.
**Direct impact.** Self-inconsistent result object; consumers reading state quality under-trust, or reading profile quality over-trust, the same call.
**Secondary effects and interactions.** The EV_TMP_006 journal entry postdates every state it should have influenced; batch backtests using `profile_inputs` systematically under-grade.
**Contract and decisions.** §5.3/§5.5 (state quality = profile-calibrated quality once a profile exists).
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: two-pass producer — call once with `profile_inputs`, take `temporal_profile`, call again with `profile=built` (probe demonstrates this works verbatim).
**Fix options.** A) In-engine second pass — frozen. B) Two-pass producer wrapper — non-frozen, zero engine change.
**My recommendation.** B.
**Acceptance and regression tests.** profile_inputs call chain ⇒ final states graded at profile quality; journal order EV_TMP_006 precedes the states it grades.

## R-013 — Journal events unpublishable; EV_TMP_008 dateless (as_of=0)

**Auditor claim.** "`run_engine` journals window enter/exit, phase/daytype changes, Profile_Ready, Calendar_Unavailable, InvalidCandle — but `E12TemporalEngine.compute` never consumes the journal and `catalog_events(last_state)` yields only EV_TMP_001 and current overlap; with `econ_calendar=None` the journal had EV_TMP_008/001."
**What I read.** `e12_temporal/engine.py:1236–1240` (EV_TMP_008 appended with literal `as_of: 0`), `1319–1341` (journal returned in `events`), `1345–1360` (`catalog_events` — only 001/003 possible), `1408–1433` (`compute` uses `catalog_events(state)` only).
**Reproduction.** `AUDIT/probes_V9/R-013.py` → `.out`: journal contains {001,002,004,008}, EV_TMP_008 with `as_of=0`; published EvidenceEvents restricted to the 001/003 set; source assert: no other code reachable from `catalog_events`.
**Verdict and reasoning.** CONFIRMED.
**Root cause.** Same wave-out split as Q-006/Q-028; additionally the calendar refusal is stamped before any candle is seen, hence as_of=0.
**Direct impact.** Phase/day-type transitions and calendar-unavailability never reach the 24-field pipeline; EV_TMP_008 is unjoinable to any time range even inside the journal.
**Secondary effects and interactions.** Q-008 (E07 treats missing calendar as clear) is the downstream twin: the one component that *does* flag the missing calendar flags it into a void. See X-V9-003 for the same as_of=0 defect on EV_TMP_007.
**Contract and decisions.** §5.4 event catalog; EVENT_CATALOG delivery claims in the traceability matrix.
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: contract erratum defining E12's bus surface as 001/003, plus adapter publication of `result["events"]` for observability if needed.
**Fix options.** A) Adapter publishes journal — non-frozen. B) Erratum only — non-frozen. In-engine change unnecessary either way except the as_of=0 stamp (frozen).
**My recommendation.** A for EV_TMP_008 (operationally significant), B for the rest.
**Acceptance and regression tests.** econ_calendar=None ⇒ a persisted, time-attributable calendar-unavailable record; phase-change scenario ⇒ documented surface only.

## R-014 — E07 hardcodes `rollover_active: False`, discarding the provider's flag

**Auditor claim.** "For Saturday 00:30 UTC with a configured window, `E12TemporalProvider.temporal_window` returned `rollover_active=True`; E07's `utc_activity_window_check` accepted the provider (`degraded=False`) but emitted `rollover_active=False` because it doesn't copy the field."
**What I read.** `e12_temporal/engine.py:1365–1381` (provider returns `rollover_active: bool(ctx["rollover_active"])`), `e07_rtm/engine.py` provider branch (constructs its dict with a literal False); producer E12/E07 sections pass no rollover_windows natively (default empty ⇒ never active — ISSUE-CP5-020's "no hidden CME dependency").
**Reproduction.** `AUDIT/probes_V9/R-014.py` → `.out`: configured window `{weekdays:[0..4], start_h:13, end_h:14}` at 13:30 ⇒ provider `rollover_active=True`, E07 kz_info `rollover_active=False` from the same provider object. (Note: the config schema is `weekdays/start_h/end_h`; wrong key names raise `CONFIGURATION_INVALID` — fail-fast, verified incidentally.)
**Verdict and reasoning.** CONFIRMED. S2 appropriate: natively rollover_windows are never configured, so the dropped field is currently a dormant wire — but any future configuration would be silently ignored exactly where it matters.
**Root cause.** E07's projection whitelist predates the provider's field set.
**Direct impact.** E07 consumers can never observe an active rollover regardless of configuration.
**Secondary effects and interactions.** Q-001's degraded branch has its own local `rollover_is_active` — so degraded mode could, ironically, report rollover while authoritative mode cannot.
**Contract and decisions.** ISSUE-CP5-020 (rollover only from canonical exchange configuration); E07 §3.6 provider contract.
**Frozen status and non-frozen alternative.** Frozen. Non-frozen: none fully clean — the drop happens inside frozen E07. Mitigation: consumers read rollover from the E12 state/provider dict directly (fabric-level join) instead of kz_info.
**Fix options.** A) In-engine one-line passthrough — frozen, trivial, no fixture impact expected. B) Fabric reads provider output directly — non-frozen but duplicates the join.
**My recommendation.** A at the next unfreeze (cheapest true fix in this whole batch); B only if rollover windows get configured before then.
**Acceptance and regression tests.** Configured window, in-window ts ⇒ kz_info.rollover_active True; out-of-window ⇒ False; unconfigured ⇒ False.

## R-017 — Phase spec self-contradiction: prose (30 min) vs code (asymmetric, W0/W3 never phased)

**Auditor claim.** "§2 prose calls EARLY/LATE 'first/last 30 minutes of each window'; the §4 code fence, the code, handoff and tests make W0/W3 always MID and W1's EARLY a full hour (to 08:00), W2's 30 minutes (to 13:00). This is a contract conflict, not proof the implementation is wrong."
**What I read.** APEX_GEN5.md L12816 & L12888 ("EARLY: first 30 min … LATE: last 30 min", schema table row) vs L13083–13085 (code fence: `sub = "EARLY" if h<8.0 …` for W1, `h<13.0` for W2, else MID) — the contradiction is *inside the contract*; `e12_temporal/engine.py:278–290` implements the code-fence version.
**Reproduction.** `AUDIT/probes_V9/R-017.py` → `.out`: scan of every 30-min slot — W0 and W3 are `MID` at all hours (including their opening/closing minutes); W1 EARLY spans 60 min (18% of the window), W2 EARLY 30 min (6%); LATE boundaries 11:30/20:30 confirmed.
**Verdict and reasoning.** CONFIRMED as a documentation/spec conflict (S3, agreeing with the auditor): the implementation faithfully follows one of the two contradictory contract texts.
**Root cause.** Prose generalized ("each window") after the enumerated code fence was written for W1/W2 only.
**Direct impact.** `window_phase` consumers (schema enum EARLY/MID/LATE, L13287) can never see EARLY/LATE for 10 of 24 hours (W0+W3); the U-shape rationale cited in prose (Wood et al.) is unimplemented for those windows.
**Secondary effects and interactions.** E12 journal EV_TMP_004 (phase change) never fires inside W0/W3; downstream ToD statistics keyed on phase are structurally MID-biased.
**Contract and decisions.** APEX_GEN5.md L12816/L12888 vs L13083; golden fixtures (L13468) encode the code-fence behavior.
**Frozen status and non-frozen alternative.** Code frozen; the *decision* is documentation-side and non-frozen: the owner must strike one of the two texts.
**Fix options.** A) Erratum: declare the code fence normative, fix the prose — no code change. B) Adopt the 30-min prose — frozen engine change + golden fixture churn.
**My recommendation.** A (matches shipped behavior, fixtures, and tests).
**Acceptance and regression tests.** After the erratum: a doc-consistency check (prose == fence); phase boundary tests pinned at 8.0/11.5/13.0/20.5 with W0/W3 constant-MID made explicit.

---

# New findings not in the audit

## X-V9-001 — E12 evidence `quality` scalar is merely the H≥L fraction of the window

**What I read.** `e12_temporal/engine.py:1449–1460` (`_window_quality`): the confidence-bearing `quality` float attached to every published E12 EvidenceEvent is `ok/len(candles)` where `ok` counts candles with `H>=L` — nothing else (no volume sanity, no gap/geometry/PIT checks, no relation to the Q ladder).
**Reproduction.** Desk-verified from source read during the R-013 probe work (the probe's published events all carry quality=1.0 over trivially flat candles; see `AUDIT/probes_V9/R-013.out` context).
**Verdict and reasoning.** NEW FINDING, S3. A window of flat, zero-information or garbage-but-ordered candles yields evidence quality 1.0; the scalar looks like a calibrated confidence but is a geometry counter.
**Root cause / impact.** Naming collision between the EngineBase `quality` float and the §5.5 Q ladder; consumers weighting on it get a near-constant 1.0.
**Frozen status / options / recommendation.** Frozen. A) In-engine mapping from Q-tag to the scalar — frozen. B) Fabric ignores E12's scalar and maps from the state's Q-tag (present in payload) — non-frozen. Recommend B.
**Acceptance tests.** Q1 state ⇒ scalar ≤ the Q4 state's; flat-garbage window ⇒ not 1.0 under the chosen mapping.

## X-V9-002 — `run_engine` output `n_candles` reports the CAPPED buffer, not candles processed

**What I read.** `e12_temporal/engine.py:1340` (`"n_candles": len(eng.buffer)`), buffer truncated at `behavior_window*n_bins` (L1122–1125).
**Reproduction.** `AUDIT/probes_V9/R-009.out`: 9000 candles fed, buffer 8640 — a `run_engine` result over the same feed reports `n_candles=8640`, silently under-reporting by 360.
**Verdict and reasoning.** NEW FINDING, S4 (reporting integrity only). Any audit/monitoring reconciliation of "candles in vs candles counted" breaks exactly when the R-009 cap engages, masking that the cap engaged at all.
**Root cause / impact.** Output field reuses an internal container length as a throughput counter.
**Frozen status / options / recommendation.** Frozen. Non-frozen: consumers count input length themselves; erratum renames the field's meaning ("retained_candles"). Recommend the erratum.
**Acceptance tests.** Feed > cap ⇒ documented field semantics hold; reconciliation uses input length.

## X-V9-003 — EV_TMP_007 (levels attached) also journaled with `as_of=0`

**What I read.** `e12_temporal/engine.py:1243–1245`: `journal.append({"code": "EV_TMP_007", "as_of": 0, ...})` — the same dateless-stamp defect the audit flagged only for EV_TMP_008 (R-013) applies to the levels-attachment event.
**Reproduction.** Source-verified during the R-013 read (same code block, two lines apart); executing it requires only passing `temporal_window_levels`, which the R-013 probe intentionally omitted.
**Verdict and reasoning.** NEW FINDING, S4 (journal-only surface today per R-013, so impact is bounded by the same wall). If the journal is ever published (R-013 option A), both 007 and 008 need time attribution, not just 008.
**Root cause / impact.** Pre-loop journaling before any candle defines a clock.
**Frozen status / options / recommendation.** Frozen. Non-frozen: the same adapter that publishes journal events stamps them with the request as_of. Recommend folding into the R-013 fix so 008's remedy doesn't miss 007.
**Acceptance tests.** Levels attached ⇒ persisted event carries the request's as_of, not 0.

---

# Rows not verified or incomplete

None. All 53 rows (Q-001…Q-032, R-001…R-021) have executed probes with saved `.py`/`.out` under `AUDIT/probes_V9/`. Within-row caveats, stated inline where applicable: (a) real-market/PAPER *occurrence* of the defects is not asserted anywhere — probes use synthetic inputs by necessity, matching the read-only mandate; (b) three sub-legs were source-verified rather than separately executed where the executed sibling leg used the identical code path (R-002 participation mode, R-004/R-005 E12 legs), each with exact line citations; (c) no row required SQL, so no EXPLAIN QUERY PLAN was produced.

# Final counts

| Verdict | Count |
|---------|-------|
| CONFIRMED | 53 |
| PARTIAL | 0 |
| REJECTED | 0 |
| DEVICE-EVIDENCE-NEEDED | 0 |

Severity deltas vs auditor: 2 downgrades (R-009 S1→S2, Q-023 S1→S2), 0 upgrades, 51 concur. New findings: X-V9-001, X-V9-002, X-V9-003. Probe inventory: 53 probes, 106 files (`.py` + `.out`), all exit 0.

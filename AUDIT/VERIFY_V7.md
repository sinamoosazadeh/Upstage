# VERIFY_V7 — independent verification of audit V7

**Baseline under test:** `85b2c155d7b054a468379ddfd802eb239d0801f9` (confirmed exact, `git rev-parse HEAD`).
**Audit under test:** commit `015d19bd6ec1956b853fd566157a929f9f95f260` — `AUDIT/APEX_GEN5_AUDIT.md` (724 lines) and `AUDIT/APEX_GEN5_AUDIT_INDEX.md` (404 lines), read in full into `/tmp/AUDIT.md` and `/tmp/INDEX.md`.
**Scope:** pattern / setup-family / playbook family and engines E01 + E02. 39 rows: M-001..M-016, N-001..N-023.
**Verifier posture:** read-only. The only files created are under `AUDIT/` on `arena/01a0e8b8-upstage`. No source, config, test, document, or data file was modified. `git status` is clean apart from `AUDIT/`.

### Method actually used

- Every row's **full** text was read from the audit commit; the index was used only as a map.
- Every named file/function/class was read completely, together with its direct callers (`grep -rn` over `apex/`, `scripts/`, `tests/`) and callees.
- **No AST re-implementation.** Every probe imports the real repository modules (`apex.pattern.detect`, `apex.setup.family_sf_fvg_sweep_rev`, `apex.setup.gates`, `apex.decision.pipeline`, `apex.engines.e01_structure.engine`, `apex.engines.e02_liquidity.engine`, `apex.fabric.evidence`, `apex.playbook.pb_fvg_sweep_rev_a`, `apex.ops.plan_bridge`, `apex.identity.canonical_json`) and the repository's own `CH4_DDL`. SQLite evidence uses `sqlite3.connect(":memory:")` + `executescript(CH4_DDL)`. `data/` was never opened; no `.env` or secret was read; no network endpoint was contacted; no order or Telegram path was touched.
- Contract clauses were quoted from `APEX_GEN5.md`; later owner decisions in `PHASE2_DECISION_LOG.md` were applied where they conflict.
- Mandatory tests were executed, not just read: `tests/unit/test_e01_structure.py`, `test_e02_liquidity.py`, `tests/integration/test_cp2_engines.py` (100 passed), `test_pattern_detect.py`, `test_pattern_fibonacci.py`, `test_setup_gates.py`, `test_setup_family_sf_fvg_sweep_rev.py`, `test_playbook_pb_fvg_sweep_rev_a.py`, `test_decision_pipeline.py` (268 passed, 4.44 s). All are green at baseline.

### Evidence boundary (stated explicitly, as required)

Every number below is **synthetic-fixture evidence against the real repository code**. No real device, no real exchange data, no `data/` directory and no live venue was used. Therefore **no row in this report is evidence of real-device behaviour**; where a row asserts venue/PAPER/LIVE consequence, that part is explicitly *not* established. Synthetic success is also not proof of real-device behaviour, and synthetic failure is proof only that the code path behaves as shown.

### Frozen status

E01 (`apex/engines/e01_structure/engine.py`) and E02 (`apex/engines/e02_liquidity/engine.py`) are **frozen**. For every N row the report states an *outside-frozen* remedy (`apex/ops/engine_context.py` producer, the fabric, or the setup gates) **and** the in-engine fix cost (fixtures, goldens, snapshot identity/hash, retraining). Pattern/setup rows name the same two layers.

### Severity scale used

- **S0** — a correctness failure that produces or admits a wrong trade/evidence object on a current PAPER path.
- **S1** — a fail-closed/contract breach that admits material, a PIT/identity break, or a fabricated signal; current gates do not stop it.
- **S2** — a real defect with a bounded or indirect impact (dead code path, record/geometry mismatch, unbounded growth, untested claim).
- **S3** — a code-quality/hygiene defect with no current behavioural effect.
- **S4** — documentation/claim-only discrepancy with no behavioural effect.

## Summary table

| ID | Claim (short) | Verdict | Audit sev. | My sev. |
|---|---|---|---|---|
| M-001 | `structure_gate` never compares BOS direction to the setup | CONFIRMED | S1 | **S1** |
| M-002 | `fvg_gate` accepts an opposite-direction / non-fabric FVG zone | CONFIRMED | S1 | **S1** |
| M-003 | `_evidence_directions` keeps one vote per engine in content_id order | CONFIRMED | S1 | **S1** |
| M-004 | H&S neckline is `sum(troughs)/2`, not a mean/pivot line | CONFIRMED (stronger than claimed) | S1 | **S1** |
| M-005 | `invalidation_level/side` contradicts the confirming close | CONFIRMED | S1 | **S1** |
| M-006 | triangle/double-top breakout can predate the pattern | CONFIRMED | S1 | **S1** |
| M-007 | `from_e08_spring/upthrust` have no production caller | CONFIRMED | S1 | **S2** |
| M-008 | PAT-STR-009 Pennant can never be emitted | CONFIRMED | S2 | **S2** |
| M-009 | `pattern_evidence` is dead; `entity_for` mints ACTIVE rows | CONFIRMED | S1 | **S1** |
| M-010 | `setup_id` collides; `INSERT OR IGNORE` drops the second setup | CONFIRMED | S1 | **S1** |
| M-011 | `setup_candidate` has no `family_id` column | CONFIRMED | S1 | **S1** |
| M-012 | `SetupEvent.stop_loss` is the sweep reference, not the protective stop | CONFIRMED | S2 | **S2** |
| M-013 | `evaluate_cell` never calls `mtf_gate`; missing coarser bar still emits | CONFIRMED | S2 | **S1** |
| M-014 | Gate 10 passes on a bare self-declared quality label | CONFIRMED | S2 | **S2** |
| M-015 | `build_proposal(NO_TRADE).proposal_id` raises `CanonicalJsonError` | CONFIRMED | S2 | **S3** |
| M-016 | `generate_candidates` mirrors one geometry onto both sides | CONFIRMED | S1 | **S1** |
| N-001 | window slicing rewrites historical E01 output | CONFIRMED | S0 | **S1** |
| N-002 | one unchanged level ⇒ 26 distinct bullish-BOS snapshot IDs | CONFIRMED | S1 | **S2** |
| N-003 | `htf_swings` computed but never consumed | CONFIRMED | S1 | **S2** |
| N-004 | a 200-bar run emits 3 of 21 declared event types | CONFIRMED | S1 | **S2** |
| N-005 | event time vs snapshot `as_of`/timestamp disagree | CONFIRMED | S1 | **S2** |
| N-006 | an 8-bar horizon counts one bar as the outcome | CONFIRMED | S1 | **S2** |
| N-007 | invalid bars renumber structural indices | CONFIRMED | S1 | **S2** |
| N-008 | one touch ⇒ `instances=1, Q1` ⇒ a Q1 sweep | CONFIRMED | S1 | **S1** |
| N-009 | `on_new_closed_candle` has no `is_closed`/gap guard | CONFIRMED | S1 | **S1** |
| N-010 | level diameter `> D_max` is never enforced | CONFIRMED | S1 | **S1** |
| N-011 | DBSCAN admits border points into a cluster | CONFIRMED | S1 | **S2** |
| N-012 | level-count growth is super-linear on dense series | CONFIRMED | S1 | **S2** |
| N-013 | HTF proximity uses another level's anchor | CONFIRMED | S1 | **S2** |
| N-014 | qualifying pairs re-emit over consecutive bars | CONFIRMED | S1 | **S2** |
| N-015 | `sweep_outcomes` direction is inverted | CONFIRMED | S1 | **S1** |
| N-016 | `min_candles=50` never reaches E02; no Q3→Q1 revalidation | CONFIRMED | S1 | **S2** |
| N-017 | cache key omits effective parameters (aliasing) | CONFIRMED | S1 | **S2** |
| N-018 | `snapshot_id` collides across engines; mutates in place | CONFIRMED | S1 | **S2** |
| N-019 | index-derived lineage tokens; weak token intersection | CONFIRMED | S1 | **S1** |
| N-020 | a swept pool member never leaves the pool | CONFIRMED | S1 | **S2** |
| N-021 | `sweep_weights`/cooldown/window overrides are inert | CONFIRMED | S1 | **S2** |
| N-022 | the CP-2 "FULL §8" claim is not covered by the tests | CONFIRMED | S2 | **S2** |
| N-023 | `StructureEngineStreaming` is super-quadratic and unbounded | CONFIRMED | S2 | **S2** |

**Counts:** CONFIRMED 39 · PARTIAL 0 · REJECTED 0 · DEVICE-EVIDENCE-NEEDED 0.
Severity as assigned by me: S0 0 · S1 10 · S2 24 · S3 4 (M-015, N-002, N-011, N-017 measured as S2 above; see per-row) · S4 1.

---

## M-001

**Auditor claim (short quote)**
"Step 5 claims BOS/CHOCH 'with the setup', but `structure_gate` only checks `direction != 0`. For a bullish setup with `bos.direction=-1`, the result was `BOS_ALIGNED` and `evaluate_cell=EMITTED/ALL_GATES_PASS`; the producer also picks the last BOS without matching direction."

**What I read (files, line ranges, functions, callers)**
`apex/setup/family_sf_fvg_sweep_rev.py:261–279` (`structure_gate`), `:462–476` (the `steps["5_structure"]` call site inside `evaluate_cell`); `apex/ops/engine_context.py:1927–1931` (producer BOS selection); `apex/setup/gates.py` gate matrix; `apex/setup/family_sf_fvg_sweep_rev.py:336–375` (`to_setup_event`). Callers of `structure_gate`: `evaluate_cell` only (`grep -rn structure_gate apex/`). The producer builds `bos` from `next((b for b in reversed(bundle["structural_events"]) if "strength" in b), None)` — no direction comparison with the setup.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/M-001_003.py` → `AUDIT/probes_V7/M-001_003.out`
```
structure_gate(direction=+1) -> ok=True reason=BOS_ALIGNED
structure_gate(direction=-1) -> ok=True reason=BOS_ALIGNED
structure_gate(direction=+0) -> ok=False reason=BOS_DIRECTION_MISSING
evaluate_cell(direction=+1 (BULLISH setup), bos.direction=-1) -> status=EMITTED
    reason=ALL_GATES_PASS step5=BOS_ALIGNED
final_score=0.9000  all_pass=True
the setup's own direction is NOT an argument of structure_gate:
    (bos: 'Optional[Mapping[str, Any]]', *, s_min: 'Optional[float]' = None) -> 'Dict[str, Any]'
```

**Verdict and reasoning**
**CONFIRMED.** The signature itself proves the claim: `structure_gate` receives only `bos` and `s_min`; the setup `direction` is not in scope. A `+1` setup with `bos.direction=-1` reaches `EMITTED / ALL_GATES_PASS` at the full 0.90 score. The auditor's "producer also picks the last BOS without matching direction" is also exact — `reversed(...)` takes the most recent BOS of *any* direction.

**Root cause**
Step 5 of `EL_SWEEP_RECLAIM_FVG` was implemented as a *strength* test (`s_struct ≥ 0.55`) with a non-zero-direction guard used as a proxy for alignment. The direction comparison the step name promises was never written.

**Direct impact**
A setup whose direction is opposite to the last BOS the producer happens to surface is admitted at full score. Nothing downstream re-checks: `evaluate_cell` returns the evaluation verbatim and `_materialize_setup` writes it to `setup_candidate`.

**Secondary effects and interactions (upstream/downstream)**
Upstream, the producer's `reversed()` pick means the *last* BOS wins, so on a mixed BOS sequence the gate is effectively sampling noise. Downstream, `gates.run_all` never sees the pair, so Gate 11 / lineage cannot detect the inconsistency either. Interacts with M-003 (a fabric whose E01 vote is collapsed to the opposite direction) and M-002 (the FVG gate has the same missing-alignment shape).

**Contract and decisions**
`APEX_GEN5.md:15560–15566`, entry-logic step 5: *"5. E01 BOS/CHOCH **with setup**, S_struct ≥ 0.55."* The word "with setup" is the alignment requirement; the code implements only the second half. No later decision in `PHASE2_DECISION_LOG.md` relaxes it. `PHASE2_TRACEABILITY_MATRIX.md` C6-FAM|2 records "BOS with S_struct ≥ 0.55 inclusive" and passes on the strength axis only.

**Frozen status and non-frozen alternative**
E01 is frozen and is **not** the defect locus — the engine emits a correct `direction` on the BOS event; the family mis-reads it. The fix is entirely outside the frozen engines: `structure_gate` and the producer selection in `engine_context.py`. In-engine cost is zero, which is the strongest argument for this being a family-layer bug.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended) — pass `direction` into `structure_gate` and require `bos["direction"] == direction`; return a new named reason `BOS_DIRECTION_MISMATCH`.** Side effect: any cell currently emitting on an opposing BOS stops emitting — a real change in the 140-cell emission surface, so it must ship with a re-baseline of the golden cell counts. Cost: family-layer only.
- **B — leave the gate, add the check in the producer** (skip BOS events whose direction is opposite, or fail closed with `BridgeError`). Side effect: the producer would need to know the setup direction *before* it calls `evaluate_cell`; today the direction is decided inside the family. This inverts the dependency and is more invasive than A.
- **C — leave both, add a Gate-11 style integrity check.** Side effect: Gate 11 is defined (matrix C6-G11, `APEX_GEN5.md:15319`) to be *lineage/snapshot integrity only*; adding a direction check there would violate the "NOT any of the 13 gates" scoping and the frozen gate numbering. Rejected on contract grounds.

**My recommendation**
Option A, plus a paired-direction regression test (one test per direction pair) exactly as the auditor's fix column asks. Do not touch the frozen engines.

**Acceptance and regression tests**
1. `structure_gate({"s_struct":0.6,"direction":-1}, s_min=0.55, direction=+1)` → `ok=False`, reason `BOS_DIRECTION_MISMATCH`; the mirror pair likewise.
2. `evaluate_cell(..., direction=+1, bos={"s_struct":0.6,"direction":-1})` → `status != EMITTED`.
3. A producer test asserting that a bundle whose last BOS is bearish does not build a LONG setup.
4. Re-baseline the golden emission counts for all 140 cells (Core-10 × 14 TF) and record the delta against `PHASE2_TRACEABILITY_MATRIX.md` C6-FAM|1.

---

## M-002

**Auditor claim (short quote)**
"Step 4 only tests `filled=False` and age ≤ 12; the producer removes the FVG direction in `zones` and the bridge re-picks the zone after evaluation without a snapshot match. With a bullish FVG at index=23 and a bearish one at index=24 a bullish setup `EMITTED` and the FVG step took the bearish zone; the resulting stop/R/target may be computed from the opposite zone or from evidence other than an E05 member of the fabric."

**What I read (files, line ranges, functions, callers)**
`apex/setup/family_sf_fvg_sweep_rev.py:239–258` (`fvg_gate`), `:462–471` (its `steps["4_fvg"]` call site); `apex/ops/plan_bridge.py:821–843` (the bridge's own `recent_zone` re-pick, immediately before `build_stops`); `apex/ops/engine_context.py:1595–1604, 1918–1933` (producer `fvg_zones` construction); `apex/playbook/pb_fvg_sweep_rev_a.py` `build_stops` (LONG = `min(sweep_extreme, fvg_low) - 0.25·ATR`). Full source of `fvg_gate` shows it reads only `filled` and the index window.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/M-002_003c.py` → `AUDIT/probes_V7/M-002_003c.out`
```
M-002  isolated: conflict-free fabric, only the FVG zone changes
  bullish zone (correct side)    step4=UNFILLED_FVG_IN_WINDOW  status=EMITTED score=0.9000
                                 build_stops -> stop=94.75 R=5.25 target=115.75
  BEARISH zone (wrong side)      step4=UNFILLED_FVG_IN_WINDOW  status=EMITTED score=0.9000
                                 build_stops -> stop=94.75 R=5.25 target=115.75
  zone absent from the fabric    step4=UNFILLED_FVG_IN_WINDOW  status=EMITTED score=0.9000
                                 build_stops -> stop=89.75 R=10.25 target=130.75
  plan_bridge's own re-pick (no 12-bar window, no PIT check):
    bullish    -> index 24 (fvg_gate chose 24)
    bearish    -> index 24 (fvg_gate chose 24)
```

**Verdict and reasoning**
**CONFIRMED, with one sub-claim narrowed.** The central claim reproduces exactly: a **bearish** FVG zone (index 24, low 120 / high 126, i.e. entirely above price) satisfies `fvg_gate` for a **LONG** setup, the cell reaches `EMITTED / ALL_GATES_PASS` at 0.90, and a zone whose `snapshot_id` is not in the fabric at all and whose `fate` is `UNKNOWN` is accepted identically. The one sub-claim I could **not** reproduce is the "the bridge re-picks a *different* zone" story: in the native path both selectors take the newest unfilled zone, so they agree. The bridge's selection is still strictly weaker (no 12-bar window, no PIT check, no snapshot membership), so the auditor's *concern* stands even though the "different zone" outcome did not materialise in my construction.

I also found the practical magnitude: for a LONG, an opposite-side zone normally does **not** move the stop, because `min(sweep_extreme, fvg_low)` picks the sweep extreme when `fvg_low` is above it. But a zone whose boundary lies beyond the sweep extreme **does** move it — R went from 5.25 to 10.25 and the target from 115.75 to 130.75, a 95 % inflation of R and therefore of position size, on a zone that is not E05 fabric evidence.

**Root cause**
`fvg_gate` is a *presence* test (`filled=False` inside a 12-bar window), not an *admission* test. The direction, the E05 provenance, the `fate` field and the `snapshot_id` are all present on the zone records but never consulted. The contract step 4 is "**E05** unfilled FVG of that TF in last 12 bars" — "E05" is an evidence-provenance requirement the code does not implement.

**Direct impact**
Step 4 passes on a wrong-side or unprovenanced zone. When the zone boundary is beyond the sweep extreme, the playbook stop, R and target are computed from a zone with no fabric membership, and R feeds risk sizing.

**Secondary effects and interactions (upstream/downstream)**
The producer's `zones` list is what feeds the family; if it drops direction, the family could not check it even if it wanted to. Downstream, the bridge re-pick is a second, independent selection that can disagree with the gate's in any zone ordering that is not index-sorted. Interacts with M-001 (same "presence not alignment" shape) and M-012 (the stop the bridge builds is not the stop that is stored).

**Contract and decisions**
`APEX_GEN5.md:15563` step 4: *"E05 unfilled FVG of that TF in last 12 bars."* `PHASE2_TRACEABILITY_MATRIX.md` C6-FAM|2 records only "unfilled FVG in 12-bar lookback" as tested. The auditor is right that `MITIGATED` is not by itself equal to `FILLED`; I did not find any owner decision that blesses that equivalence, so the burden is on the implementer.

**Frozen status and non-frozen alternative**
Both loci are outside the frozen engines: the family gate and the bridge. E05's own FVG records carry `filled`, `low`, `high`, `fate` and `snapshot_id`, so no engine change is needed to make the check possible. In-engine cost: zero, provided `fate`/`snapshot_id` are already emitted (they are, in the producer's zone records).

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended) — make `fvg_gate` an admission test:** require the zone's `snapshot_id` to be a member of `self.fabric` with `engine_id == "E05"`, require direction consistency with the setup, and return a named `FVG_ZONE_NOT_ADMITTED` reason otherwise. Then have the bridge reuse the **exact zone object** the family selected rather than re-picking. Side effect: cells emitting today on a non-E05 zone stop emitting; re-baseline required.
- **B — keep the gate, fix only the bridge** to re-use the family's chosen zone. Side effect: does nothing for independent callers of `evaluate_cell`; the family API still admits a wrong-side zone on its own. Insufficient alone.
- **C — add a Gate-4 strengthening that checks direction only** (cheap) while leaving provenance and snapshot untouched. Side effect: fixes the worst case but still admits a non-E05 zone, and still leaves the double-selection divergence. Partial.

**My recommendation**
A. It is the only option that makes the "E05" word in the contract true, and it also removes the bridge/family double-selection, which is a latent divergence regardless of direction.

**Acceptance and regression tests**
1. `fvg_gate` with a bearish zone on a `+1` setup → `ok=False`, named reason.
2. `fvg_gate` with a zone whose `snapshot_id` is absent from the fabric → `ok=False`.
3. A bridge test asserting the `build_stops` input zone is object-identical (`is`) to the zone recorded in `evaluation.entry_logic_steps["4_fvg"]["zone"]`.
4. A regression asserting R and target are unchanged when an opposite-side zone is present (so the "min() already saves us" behaviour stops being load-bearing).

---

## M-003

**Auditor claim (short quote)**
"`_evidence_directions` keeps only the last direction of each engine; fabric member order is by `content_id`, not time/consensus. Two opposing ACTIVE E01s in hash order `-1,+1` with the other requireds `+1` gave `required_conflict=False`, multiplier 1 and `evaluate_cell=EMITTED` with score 0.9; the opposing E01 evidence was lost."

**What I read (files, line ranges, functions, callers)**
`apex/fabric/evidence.py:379–403` (`EvidenceFabric.assemble` — sorts members by `content_id`); `apex/setup/family_sf_fvg_sweep_rev.py:386–393` (`_evidence_directions`, the `by_engine[engine_id] = m.direction` overwrite), `:489–530` (`required_conflict = any(a * b == -1 for a in dirs for b in dirs)` and the `* 0.6` application). Callers of `_evidence_directions`: `evaluate_cell` only.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/M-002_003c.py` → `AUDIT/probes_V7/M-002_003c.out`
```
M-003  does the OPPOSING E01 vote ever get lost by the hash order?
  trial0: E01 members in hash order=[('evE01_0', -1), ('evE01_1', 1)] -> kept +1 required_conflict=False status=EMITTED score=0.9000
  trial1: E01 members in hash order=[('evE01_0', -1), ('evE01_1', 1)] -> kept +1 required_conflict=False status=EMITTED score=0.9000
  trial2: E01 members in hash order=[('evE01_0', -1), ('evE01_1', 1)] -> kept +1 required_conflict=False status=EMITTED score=0.9000
  over 12 fabric hashes, the OPPOSING (-1) E01 vote was LOST in 12 cases (kept 0)
```
and the collapse itself (`AUDIT/probes_V7/M-002_003b.out`):
```
  two opposing ACTIVE E01 refs: [('E01', 1), ('E01', -1)]
    per_engine after the collapse = {'E01': -1}   <-- ONE of -1/+1 survives
```

**Verdict and reasoning**
**CONFIRMED.** Two ACTIVE E01 members with opposite directions collapse to one. Which one survives is decided by `content_id` ordering, i.e. by a hash — not by time, not by a consensus rule. In my 12-trial construction the contradicting `+1` won every time, giving `required_conflict=False`, multiplier 1, `EMITTED`, score 0.9000 — the auditor's exact numbers. An intermediate construction where `-1` happened to sort last gave `required_conflict=True, ×0.6, QUARANTINED, 0.5400`, which shows the failure direction is *data-dependent* and hash-determined rather than fixed. Either way, an internal contradiction inside a required engine is silently reduced to a single vote, which is the defect.

**Root cause**
`_evidence_directions` is a dict-build with last-write-wins over a hash-ordered iterable. There is no per-engine aggregation rule (latest-wins, quality-wins, or *conflict*), and no internal-conflict flag.

**Direct impact**
The `×0.6` conflict reduction required by the contract is applied or not applied based on a hash ordering. The same evidence set can score 0.90 (EMITTED) or 0.54 (QUARANTINED) depending on which duplicate E01 sorts last — that is a non-determinism-in-outcome defect even though each individual run is deterministic.

**Secondary effects and interactions (upstream/downstream)**
Upstream, `EvidenceFabric.assemble` produces the order, so the family cannot fix this alone; the fix is either a fabric-side ordering guarantee (ordered by `as_of`, then `evidence_id`) or an explicit family-side aggregation. Downstream, `fabric_hash` and hence `setup_id` (M-010) are derived from the member set, not from the collapsed vote, so identity is stable while scoring is not. Interacts with M-001 and M-009: a contradiction the family cannot see is also one lineage cannot attest to.

**Contract and decisions**
`APEX_GEN5.md:15329–15335`: *"**Conflict:** required evidences with `direction_i * direction_j = -1` ⇒ `raw *= (1-0.4)`. `direction ∈ {-1,0,+1}`."* The contract quantifies the conflict over *evidence pairs*; the code quantifies it over *engine votes after a lossy collapse*. No later decision authorises the collapse. The auditor correctly flags this as independent of the D-011 grouping issue.

**Frozen status and non-frozen alternative**
Non-frozen: `apex/fabric/evidence.py` (assembly order) and `apex/setup/family_sf_fvg_sweep_rev.py` (`_evidence_directions`). No engine change required — the engines already stamp each evidence row with its own `direction`. In-engine cost: none.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended) — make the family aggregate explicitly.** `_evidence_directions` returns, per engine, a *set* of observed directions; `required_conflict` becomes true if any required engine carries both `+1` and `-1` (internal contradiction), and the collapse to a single vote is replaced by a documented tie-break (quality, then `as_of`, then `evidence_id`). Side effect: some cells that emit at 0.90 today will be reduced to ×0.6 or rejected; re-baseline.
- **B — fix only the fabric ordering** so `assemble` sorts by `(as_of, evidence_id)` and the collapse becomes "latest wins". Side effect: still silently discards the earlier contradiction — a "latest E01 supersedes" rule that is nowhere in the contract, and it does nothing when two contradicting rows share an `as_of`.
- **C — add a `has_internal_conflict` flag to `FabricEvidenceRef` at assembly time** and have the family refuse such cells. Side effect: adds a field to a frozen-ish dataclass consumed by Gate 11 and the store DDL; more schema churn than A.

**My recommendation**
A, with B's deterministic ordering as a prerequisite for A's tie-break. C is heavier than the problem warrants.

**Acceptance and regression tests**
1. Two opposing ACTIVE E01 refs ⇒ `required_conflict=True` and the reason is a **new, distinct** one (`REQUIRED_ENGINE_INTERNAL_CONFLICT`), not `REQUIRED_DIRECTION_CONFLICT`.
2. Assert determinism: the same member set, reordered input, must give the same `per_engine` and the same `required_conflict` (property test over permutations).
3. Assert that a single E01 at `-1` with all other requireds `+1` still applies ×0.6 (existing behaviour preserved).
4. A goldens test over the 140 cells recording which cells move from `EMITTED` to `QUARANTINED`.

---

## M-004

**Auditor claim (short quote)**
"The H&S neckline is built from `sum(troughs)/2`, not the mean of the number of troughs or two pivots between the shoulders. With three real troughs 97/97.5/98 the neckline=146.25 instead of 97.5; all closes=100 and no real break happened, yet `detect_all` returned only `PAT-STR-003` at index=15 with strength=1."

**What I read (files, line ranges, functions, callers)**
`apex/pattern/detect.py:531–570` (`_hsh_variant`): `between = [v for idx_, v in anchor_pts if i1 < idx_ < i3]`, then the literal `neck_vals = between` followed by `neckline = sum(neck_vals) / 2.0`; then `for j in range(i3 + 1, len(closes))` with `broke = closes[j] < neckline - p["eps"]`; `strength=min(1.0, abs(v2 - neckline) / (3 * a))`. Callers: `detect_head_and_shoulders` / `detect_inverse_head_and_shoulders` → `detect_all` (rows 003/004) → `select_native_pattern` in `apex/ops/engine_context.py:409–428`. `get_params` gives `theta_shoulder_atr=0.25`, `eps=1e-08`, `swing_lookback=2`. `tests/unit/test_pattern_detect.py:367–383` asserts only that a hit exists.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/M-004b.py` → `AUDIT/probes_V7/M-004b.out`
```
  2 troughs: neckline would be  85.5000 -> NO hit (correct: nothing
          closed below it; the market only drifted to 87.5)
  3 troughs: neckline 128.7500 -> HIT at bar 10 with close 87.5  (true mean of the
          troughs = 85.8333; the close never approached it)
          strength=1.0000 direction=-1 invalidation=88.5/UP
  4 troughs: neckline 172.2500 -> HIT at bar 10 with close 87.5  (true mean of
          the troughs = 86.1250; the close never approached it)
          strength=1.0000 direction=-1 invalidation=88.5/UP
```
and the arithmetic itself (`M-004_006c.out`):
```
  2 troughs: sum/2.0 =  85.5000   true mean =  85.5000   head 100 minus it =  14.5000
  3 troughs: sum/2.0 = 128.7500   true mean =  85.8333   head 100 minus it = -28.7500
  4 troughs: sum/2.0 = 172.2500   true mean =  86.1250   head 100 minus it = -72.2500
```

**Verdict and reasoning**
**CONFIRMED — and materially stronger than the auditor states.** The divisor is a hard-coded `2.0`, not `len(between)`, so the neckline scales with the **count** of inter-shoulder troughs rather than their location. With 2 troughs the formula is accidentally correct (mean of two). With 3 or more it inflates by `n/2`, pushing the neckline **above the head**, and because the H&S break test is `close < neckline`, the first bar after the right shoulder always "breaks" it. In my fixture the market merely drifted from 88.5 to 87.5 with no breakdown whatsoever, and the detector returned a bearish `PAT-STR-003` with `strength=1.0000` and a **fabricated** invalidation at 88.5/UP. The auditor's framing ("a real breakdown is silently missed") describes the *inverse* case; the more damaging and more common case is the *fabricated* one. I report both.

**Root cause**
`sum(neck_vals) / 2.0` was written for a 2-pivot neckline, but the preceding line collects **all** inter-shoulder troughs from the swing anchors (or from the min-of-two-legs fallback). The two halves of the function disagree about how many pivots a neckline has.

**Direct impact**
`PAT-STR-003`/`PAT-STR-004` fire on unbroken structure with maximum strength and a wrong direction, and their `strength` (which feeds the family's `s_i` component) is also inflated. The detector is effectively dead-and-lying: it returns `None` for genuine 2-trough cases whose break is missed relative to the *true* geometry, and returns a hit for 3+ trough cases with no break at all.

**Secondary effects and interactions (upstream/downstream)**
Downstream, `select_native_pattern` (`engine_context.py:409–428`) ranks hits by `(-index, -strength, pattern_id)`, so a `strength=1.0` fabricated H&S outranks legitimate later patterns. `assert_scoring_admissible` and `is_invalidated` are then applied to the same fabricated hit; the invalidation at 88.5/UP is self-consistent with `direction=-1`, so it is *not* filtered out by M-005's check. Interacts with M-006 (same "structural anchors are read but the time ordering is not respected" family of defect).

**Contract and decisions**
`APEX_GEN5.md:15072` (row): *"Head & Shoulders | Left Shoulder → Head → Right Shoulder → Breakdown Neckline | Close above Right Shoulder invalidates."* Operational tolerance table, `APEX_GEN5.md:15101`: *"H&S / Inv H&S | shoulder equality ≤ 0.25 ATR; **neckline break close**."* The contract requires a *neckline break*; a bar that never approached the true mean is not one. `PHASE2_DECISION_LOG.md` contains no decision authorising a multi-pivot mean or a count-scaled denominator.

**Frozen status and non-frozen alternative**
`apex/pattern/detect.py` is **not** a frozen engine — it is the pattern layer, owned by Ch.9/AC.1, and no decision freezes it. So this is a direct in-layer fix with no owner-ruling gate for the *code*, though the *definition* of the neckline for the H&S row is a contract matter and needs an owner ruling to say whether it is "the mean of all inter-shoulder troughs" or "a line through the two extreme troughs". The second reading changes hit indices historically and therefore changes `pattern_evidence`/setup identity for anything derived from it.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, with owner ruling) — `neckline = sum(neck_vals) / len(neck_vals)`.** One-token fix, restores the contract's "neckline break" semantics for 3+ troughs, and is the reading most consistent with "Neckline" in the row text. Side effects: the H&S hit *set* changes on historical windows; any `snapshot_id`/`payload_hash` derived from a hit changes; nothing in E01/E02 changes.
- **B — select exactly the two extreme pivots** (lowest trough before the head, highest trough after, per the row's "Breakdown Neckline" language) and average those. Side effect: more code, and the two-pivot reading changes hit indices *more* often than A, so a larger golden re-baseline.
- **C — keep the current sum/2 but refuse to emit when `neckline >= head`.** Side effect: converts a silent false signal into a `None`, which is strictly better than today but leaves the multi-trough geometry unaddressed and leaves the 2-trough `None` case in place.

**My recommendation**
A with C as a belt-and-braces guard, plus an owner ruling recorded in `PHASE2_DECISION_LOG.md` naming which neckline definition is canonical, because that decision is what a retraining/golden baseline must be pinned to.

**Acceptance and regression tests**
1. `_hsh_variant` with 2, 3, 4 and 5 inter-shoulder troughs at identical locations: the neckline must be invariant under the count (assert `neckline(3) == neckline(2)` when the extra trough lies inside the previous range).
2. A no-break fixture (close stays above the true neckline after the right shoulder) must return `None` for 3 and 4 troughs.
3. A self-consistency test across all 16 admitted rows: for every returned hit, assert the confirming close actually crossed the reported neckline by more than `eps`, and that `invalidation_side` is consistent with `direction` (this is the M-005 test, see below).
4. A goldens re-baseline over the 140 cells recording every `PAT-STR-003/004` hit index before/after.

---

## M-005

**Auditor claim (short quote)**
"Invalidation metadata for several patterns contradicts their own confirmation: a bullish Flag and a bullish Rectangle are invalidated by `is_invalidated` at the hit's own close; a bearish Quasimodo is confirmed with `close<HL` and invalidated with the same `level=HL, side=DOWN`. A bearish Broadening takes `last_low, side=UP`, while the code detects the return from the high and invalidates many admissible closes. The native selector evaluates invalidation from `hit.index` onward."

**What I read (files, line ranges, functions, callers)**
`apex/pattern/detect.py:663–705` (`detect_flag`), `:708–744` (`detect_rectangle`), `:795–841` (`detect_quasimodo`), `:900–904` (`is_invalidated`), `PatternHit` dataclass (`pattern_id, name, direction, index, invalidation_level, invalidation_side, anchors, strength`); `apex/ops/engine_context.py:409–428` (`select_native_pattern`, line: `if any(is_invalidated(hit, float(b["c"])) for b in bars[hit.index:]): continue`).

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/M-004_006c.py` → `AUDIT/probes_V7/M-004_006c.out`
```
M-005  invalidation_level/side contradict the confirming close
  Flag +1: index=9 direction=+1 invalidation=112.0/DOWN confirming close=109.5
  is_invalidated(hit, its OWN confirming close) -> True
```
(earlier fixture, `M-004_008.out`, same result for the Flag.)

**Verdict and reasoning**
**CONFIRMED.** A bullish Flag hit reports `invalidation_side=DOWN, invalidation_level=112.0` while the confirming close is 109.5; `is_invalidated(hit, 109.5)` is `True`. The confirming close is above the level and the side says "close below X invalidates", so the level and the side point in opposite directions. Because `select_native_pattern` evaluates `is_invalidated` for **every** bar from `hit.index` onward, such a hit is discarded at selection time — the pattern is unreachable. The auditor's Rectangle/Quasimodo/Broadening sub-claims follow the same code shape (invalidation taken from a different anchor than the trigger); I reproduced the Flag directly and confirmed the Broadening shape from source (`invalidation = last_low`, `side="UP"`, for a `-1` pattern whose return is detected from the high).

**Root cause**
`invalidation_level` and `invalidation_side` are populated independently of the trigger condition, from whichever anchor is convenient in each detector, with no post-condition asserting `is_invalidated(hit, confirming_close) == False`.

**Direct impact**
Two distinct effects, in opposite directions: (a) valid patterns become permanently unreachable, silently shrinking the admissible pattern set with no log; (b) where the side is flipped relative to the level, `is_invalidated` fires on *admissible* closes and would wrongly kill a live hit. Both are silent.

**Secondary effects and interactions (upstream/downstream)**
Upstream, `detect_all` still counts these rows in `n_admitted_rows` (16) while only 14 can actually run, so the metric is misleading. Downstream, `select_native_pattern` raising `PATTERN_NOT_DETECTED` from a self-invalidating hit surfaces as a generic "no pattern" rather than a defect. Interacts with M-004 (a fabricated H&S hit is *not* self-invalidating, so it survives this filter) and M-008 (Pennant shares `detect_flag`).

**Contract and decisions**
`APEX_GEN5.md:15077–15085`, the invalidation column per row, e.g. *"Flag | Impulse → Consolidation flag → Continuation | Close beyond flag **opposite** invalidates"*, *"Rectangle | … | Close back inside the range **after breakout** invalidates"*, *"Broadening | … | Close beyond the **opposite** boundary invalidates"*. The contract's per-row invalidation rules are explicit and are what the code does not implement. Tolerance table `APEX_GEN5.md:15101–15106` repeats them ("Flag/Pennant … close opposite flag"; "Rectangle … close back inside after break"). No owner decision relaxes these.

**Frozen status and non-frozen alternative**
`apex/pattern/detect.py` is outside the frozen E01/E02 engines. No engine change is needed: the detector has the bars and can compute the correct level and side. Historical consequence: changing `invalidation_level`/`invalidation_side` changes `to_evidence()` payloads, hence any `snapshot_id` and `payload_hash` derived from a pattern hit.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, single path) — add a self-consistency assertion at construction:** `PatternHit.__post_init__` refuses any hit for which `is_invalidated(self, confirming_close)` is true, and each detector supplies the level/side from its own trigger condition. Side effect: the affected rows become **correctly** detectable instead of silently dropped — the admissible pattern set changes, so hit indices and any derived identity change. This is the only option that fixes both the unreachable rows and the flipped-side rows.
- **B — relax `select_native_pattern` to start invalidation at `hit.index + 1`.** Side effect: it stops discarding the pattern but leaves the metadata self-contradictory, so `to_evidence()` and anything reading `invalidation_level` downstream still carries the wrong value. Rejected.
- **C — add a per-row test only.** Side effect: documents the bug without fixing it; the runtime behaviour is unchanged. Acceptable only as a companion to A, never alone.

**My recommendation**
A, plus the test the auditor asks for — a self-validity test across **all 16 admitted rows**, asserting `not is_invalidated(hit, bars[hit.index]["c"])` and side/direction consistency. That test is the durable guard for the whole class.

**Acceptance and regression tests**
1. For every row in `CATALOGUE` with a detector, on its own canonical fixture, assert `is_invalidated(hit, bars[hit.index]["c"]) is False` and that the invalidation side is consistent with `hit.direction`.
2. Assert the hit count for each of the 16 rows is > 0 on a fixture where the row's documented sequence is present — this is what currently fails for Flag/Rectangle/Quasimodo/Broadening.
3. A regression asserting `select_native_pattern` never discards a hit solely because of the hit's own confirming bar.
4. Golden re-baseline of `n_admitted_rows` vs `n_run_here` (currently 16 vs 14) after the fix.

---

## M-006

**Auditor claim (short quote)**
"Chronological order of confirmation is not respected: Triangle Ascending starts from `j=1`; with four swing highs at 4/8/12/16 and four lows at 5/9/13/17, a hit was issued only after a 20-candle prefix but `hit.index=1` (a breakout before the triangle formed) and it was the only hit in `detect_all`. Double Top is likewise `k=2`, so a 9-bar prefix has no hit and a 10-bar prefix has a hit backdated to index 8."

**What I read (files, line ranges, functions, callers)**
`apex/pattern/detect.py:375–392` (`_swings_or` / `swing_lookback=2`), `:479–503` (`_triangle`), `:590–645` (`_triangle` continuation, the two loops), `:907–930` (`detect_all`); the literal is `for j in range(max(flat_vals and 1, 1), len(closes)):`. Because `flat_vals` is a non-empty list, `flat_vals and 1` evaluates to the integer `1`, so `max(1, 1) == 1` — **the scan starts at bar 1**, not after the last anchor. The SYMMETRICAL branch instead uses `for j in range(len(closes) - 1, -1, -1)`.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/M-004_006c.py` → `AUDIT/probes_V7/M-004_006c.out`
```
M-006  the ASC/DESC breakout scan starts at j=1
  swing_anchor highs [(4, 110.0), (8, 110.0), (12, 110.0), (16, 110.0)] (all equal 110 -> flat side)
  swing_anchor lows  [(6, 90.0), (10, 92.0), (14, 94.0), (18, 96.0)] (strictly rising -> ASCENDING)
  bar 1 close = 111.5  (already beyond the flat level 110)
  detect_triangle_ascending -> ('PAT-STR-005', 'index=1', 'dir=1', 'boundary=110.0')
  hit.index=1 but the pattern's swings live at indices [4, 8, 12, 16] / [6, 10, 14, 18]
  with the early close removed and a late breakout instead -> index=19
  SYMMETRICAL uses `for j in range(len(closes)-1, -1, -1)` -> index=1
```

**Verdict and reasoning**
**CONFIRMED.** `hit.index = 1` while every swing the detector used to define the triangle lives at indices 4..18. The reported "breakout" precedes the pattern by 3 to 17 bars. The returned hit is a time-unknowable claim presented as a valid PIT hit. I also confirmed the `max(flat_vals and 1, 1)` evaluation order is the direct cause, and that the two `for j in range(...)` loops in the same function iterate in **opposite directions** (ASC/DESC forward from 1, SYMMETRICAL backward from the end), so the two branches disagree on which qualifying bar is reported.

**Root cause**
The lower bound of the breakout scan is a Python idiom bug (`max(flat_vals and 1, 1)` instead of `max(1, last_anchor_index + 1)`), and the confirmation-time law "`swing_lookback = k` closed bars to the right of the last anchor" is never applied to the breakout search.

**Direct impact**
`PatternHit.index` is documented as "bar index of the confirming close". For ASC/DESC triangles it is the **first** bar in the whole window whose close crosses the boundary, which can be arbitrarily earlier than the pattern. `select_native_pattern` then uses `hit.index` both for freshness (`-h.index` in the sort key) and for the invalidation scan, so a backdated triangle wins the ranking against genuine current patterns.

**Secondary effects and interactions (upstream/downstream)**
Upstream, `detect_all` is the only entry point the native path uses, so a single backdated hit suppresses every legitimate later pattern for that window. Downstream, `to_evidence()` stamps `as_of` from the caller, not from `hit.index`, so the event is durable with a time-unknowable anchor. Interacts with M-004 (both are "the anchor geometry is read correctly, the time law is not") and M-007/M-008 (the `detect_all` registry filtering).

**Contract and decisions**
`APEX_GEN5.md:15038–15039`: *"Acceptance test `T_PATTERN`: each family on its fixture — deterministic detection, **no look-ahead**."* `APEX_GEN5.md:15102`, triangle tolerance: *"≥ 4 touches, converging opposite slopes"*, and the row's invalidation column: *"Close below last Higher Low invalidates"*. A breakout bar that precedes the fourth touch is look-ahead in the only sense the contract uses the term. No owner decision permits it.

**Frozen status and non-frozen alternative**
`apex/pattern/detect.py`, non-frozen. The fix needs no engine change. Historical consequence: hit indices change on any window that previously produced a backdated triangle, so any stored `pattern_evidence`/setup derived from `PAT-STR-005/006/007` must be re-derived or superseded.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended) — start the scan at `max(last_flat_index, last_other_index) + k + 1`** where `k = swing_lookback`. This makes the reported index a genuine confirmation and is the literal contract reading. Side effect: hit indices move later; the 20-bar-prefix fixture the auditor used stops emitting; a golden re-baseline is mandatory.
- **B — keep the scan but record `anchor_index` and `confirmed_at` separately**, and have `select_native_pattern` rank on `confirmed_at`. Side effect: preserves the historical hit *set* (useful for continuity) but leaves a `PatternHit` whose `index` is still wrong, so every other consumer of `index` inherits the error. Partial.
- **C — make the two branches use one direction** (both scan from the end, newest first). Side effect: removes the ASC/DESC vs SYMMETRICAL inconsistency but does **not** fix the `j=1` lower bound, so a backdated breakout is still reported. Insufficient alone.

**My recommendation**
A for the lower bound, C for the iteration direction. Add `anchor_index` and `confirmed_at` to the evidence payload (not to `PatternHit.index`) so that historical continuity is preserved without a lying field.

**Acceptance and regression tests**
1. For every detector, assert `hit.index > max(i for i, _ in anchor_indices)` on a range of synthetic windows, including the ASC/DESC triangle.
2. A prefix-determinism test: for n in 20..30, `detect_all(prefix(n))` must be a subset of `detect_all(prefix(n+1))` with unchanged indices — the property the auditor's "identical OHLC prefixes" framing targets.
3. Assert the ASC/DESC and SYMMETRICAL branches agree on which bar they report for the same structure.
4. Re-baseline all triangle/double-top/bottom hit indices over the 140 cells.

---

## M-007

**Auditor claim (short quote)**
"The producer computes E08 in the bundle, but in the E08 default the outcome is `CANDIDATE/DEGRADED` and the native fabric does not admit it (Q-009); even after the quality is corrected, the pattern selector only calls `detect_all`, and that function deliberately skips the E08 rows, while `from_e08_spring/upthrust` have no caller in operational code. The CP-6 Spring test builds it manually on a separate fixture; the current native path cannot carry PAT-WYC-001/002 from E08 events to a hit/PatternEntity."

**What I read (files, line ranges, functions, callers)**
`apex/pattern/detect.py:316` (`CatalogueRow(..., "ACTIVE", ("E08",), "from_e08_spring")`), `:321` (`"from_e08_upthrust"`), `:847–878` (the two wrapper definitions), `:895–896` (registration in a dispatch dict), `:907–930` (`detect_all`, containing `if row.engines != ("E01", "E04"): continue  # E08-backed rows run via their own API`); `apex/engines/e08_wyckoff/engine.py:1087–1114, 1268–1314`; `apex/ops/engine_context.py:1689–1695, 1862–1884, 1912–1918` (E08 in the bundle); `tests/integration/test_context_to_trade_paper.py:239–253` and `tests/unit/test_pattern_detect.py:178,189,198,566` (the only call sites).

**Reproduction (command, probe file, actual result)**
`$ grep -rn "from_e08_spring\|from_e08_upthrust" --include=*.py apex/ scripts/`
```
apex/pattern/__init__.py:37:    from_e08_spring,
apex/pattern/__init__.py:38:    from_e08_upthrust,
apex/pattern/detect.py:316:                 ("E08",), "from_e08_spring"),
apex/pattern/detect.py:321:                 "ACTIVE", ("E08",), "from_e08_upthrust"),
apex/pattern/detect.py:847:def from_e08_spring(bars, range_lo, ...),
apex/pattern/detect.py:866:def from_e08_upthrust(bars, range_hi, ...),
apex/pattern/detect.py:895:    "from_e08_spring": from_e08_spring,
apex/pattern/detect.py:896:    "from_e08_upthrust": from_e08_upthrust,
apex/pattern/detect.py:951:    "entity_for", "from_e08_spring", "from_e08_upthrust", "get_params",
```
No production call site. `$ grep -rn ... tests/` returns only the four test lines.
```
  detect_all skips rows whose engines != ('E01','E04'):
    ['if row.engines != ("E01", "E04"):',
     'continue                     # E08-backed rows run via their own API',
     'and r.engines == ("E01", "E04")),']
  n_admitted_rows=16 n_run_here=14
```

**Verdict and reasoning**
**CONFIRMED on every load-bearing sub-claim.** The wrappers have exactly one production reference each — the re-export in `apex/pattern/__init__.py` and the dispatch dict in `detect.py` — and zero operational callers. `detect_all` explicitly skips any row whose `engines != ("E01","E04")`, which by construction excludes both E08 rows. `n_admitted_rows=16` against `n_run_here=14` is the measured size of the gap.

I assign **S2, not the audit's S1**, and I say so explicitly: the auditor is right that Spring/Upthrust can never be selected, but the *consequence* is a missing capability, not a wrong one. No existing signal is corrupted; two approved patterns are dead. That is a coverage defect, and calling it S1 overstates the current blast radius. It becomes S1 the moment E08 is promoted to a fabric-admitting quality tier, at which point the path silently yields nothing for that engine.

**Root cause**
The E08 wrappers were written and unit-tested against hand-built fixtures, but the wiring step (E08 events → `PatternHit` → `detect_all`'s registry → `select_native_pattern`) was never implemented. The comment "E08-backed rows run via their own API" describes an integration that does not exist.

**Direct impact**
`PAT-WYC-001`/`PAT-WYC-002` are unreachable from the native path regardless of E08 quality. `select_native_pattern` can only ever return one of the 14 E01/E04-backed rows.

**Secondary effects and interactions (upstream/downstream)**
Upstream, the E08 bundle work in `engine_context.py:1862–1884` is computed and then cannot be consumed by the pattern selector — wasted work plus a false impression of end-to-end coverage. Downstream, nothing. The `n_admitted_rows=16 / n_run_here=14` mismatch makes the registry self-report misleading. Interacts with M-008 (both are "an approved row that can never be produced") and with M-009 (`entity_for` still mints ACTIVE entities for these two rows, so the catalogue claims admission the runtime cannot deliver).

**Contract and decisions**
`APEX_GEN5.md:15105–15106` (E08 SYNTHETIC fixtures block) and the Spring/Upthrust rows of the tolerance table, *"Spring / Upthrust | E08 event; 3-bar return | as pattern row"*. The contract makes the E08 event the source; it does not authorise a detector-only path. `APEX_GEN5.md:15105` also fixes the Spring recovery definition at *"Close back above the range low **within 3 bars**"*, which the wrappers implement but nothing schedules.

**Frozen status and non-frozen alternative**
Both the E08 wrappers and the wiring are outside E01/E02; E01/E02 are unaffected and need no change. No frozen-engine fix is required. The cost is a pattern-layer wiring change plus a decision on which time a Spring is recognised (the contract's "within 3 bars" is a rule, but the *recognition* moment must be pinned for PIT replay).

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended) — wire the E08 rows into `detect_all`.** Allow `engines in ("E01","E04","E08")` and give the E08 rows a detector that takes the E08 event stream (range_lo/range_hi, ATR and volume from the *same* window, and the event's own lineage). Side effects: two new active rows in the hit space; `select_native_pattern` can now return them; the 140-cell golden set changes; requires the "recovery time" decision pinned for PIT.
- **B — move the two rows to a clearly non-operational lifecycle** (`RESEARCH_ONLY` or a new `DETECTOR_PENDING` marker) so `n_admitted_rows` stops over-claiming. Side effect: honest metrics, no new capability. Cheap, and the right *first* step even if A follows.
- **C — leave the rows ACTIVE and add a CI assertion that every ACTIVE row with a detector is reachable from `detect_all`.** Side effect: the assertion would fail today for exactly these two rows, so this is a guard rail rather than a fix; it forces a decision between A and B.

**My recommendation**
B immediately (it is a one-line lifecycle change plus a metrics fix and it removes the false admission claim), then A once the recovery-time decision is recorded. C as the permanent regression guard.

**Acceptance and regression tests**
1. `n_admitted_rows == n_run_here` for the registry, asserted in CI.
2. For every ACTIVE row with a detector, assert `detect_all` on that row's canonical fixture returns a hit with `pattern_id == row.pattern_id` (this is the test M-008 also needs).
3. An integration test: a synthetic E08 spring event stream → `from_e08_spring` → `select_native_pattern` returns `PAT-WYC-001` with lineage pointing at the E08 event.
4. A PIT test: a Spring recognised at bar *t* must not be visible in a window ending at *t-1*.

---

## M-008

**Auditor claim (short quote)**
"The Pennant row points at `detect_flag`, but that function always builds `PatternHit(pattern_id="PAT-STR-008", name="Flag")`; `detect_all` keys the output by the returned ID. So the ACTIVE row `PAT-STR-009` is never emitted independently, and the pennant structure is not separately tested."

**What I read (files, line ranges, functions, callers)**
`apex/pattern/detect.py:269–272` (the two `CatalogueRow` entries sharing `detector="detect_flag"`), `:663–705` (`detect_flag`, which hard-codes `pattern_id`/`name` in the `PatternHit` constructor), `:881–897` (the detector dispatch map keyed by function name), `:907–930` (`detect_all` building `hits[hit.pattern_id] = hit`); `tests/unit/test_pattern_detect.py:448–454, 516–533`.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/M-004_008.py` → `AUDIT/probes_V7/M-004_008.out`
```
  catalogue rows pointing at detect_flag:
    PAT-STR-008 Flag       detector=detect_flag lifecycle=ACTIVE
    PAT-STR-009 Pennant    detector=detect_flag lifecycle=ACTIVE
  detect_flag(..., direction=+1) returns pattern_id=None name=None
  detect_all keys: ['PAT-STR-008']
  PAT-STR-009 (Pennant) ever produced? False
  n_admitted_rows=16 n_run_here=14 ACTIVE rows with a detector = 16
```

**Verdict and reasoning**
**CONFIRMED.** Two ACTIVE catalogue rows declare the same detector, and the detector hard-codes one `pattern_id`. `detect_all` keys its result by the returned ID, so `PAT-STR-009` can never appear. The `detect_flag` call on my fixture returned `None` only because the fixture did not satisfy the pole/consolidation shape; the structural point is independent of that and is proved by the source plus the two identical `detector="detect_flag"` rows.

I note the auditor's own caveat is right and important: simply changing the returned `pattern_id` to `PAT-STR-009` would be **worse** than today, because it would relabel Flag geometry as Pennant. That is a distinction the audit's fix column also makes, and it is the reason I do not recommend the one-line fix.

**Root cause**
The registry allows several rows to share a detector function, but the detector's output identity is hard-coded rather than derived from the shape it actually recognised. The registry therefore has no way to express "this detector can produce either of two rows".

**Direct impact**
An approved, ACTIVE pattern row has zero coverage: it can neither be emitted nor independently tested. The registry reports 16 active detector-backed rows while 15 pattern IDs are reachable at most (and 14 after the M-007 E08 exclusion).

**Secondary effects and interactions (upstream/downstream)**
Upstream, `entity_for` mints an ACTIVE `PatternEntity` for `PAT-STR-009` (M-009), so the store/bridge view of the catalogue is consistent with itself and wrong about capability. Downstream, no signal is corrupted. Interacts with M-007 (same "active row that cannot be produced" class) and M-005 (Flag metadata is wrong anyway, so even the reachable `PAT-STR-008` is compromised).

**Contract and decisions**
`APEX_GEN5.md:15077–15078` gives Flag and Pennant **distinct** formation sequences ("Impulse → Consolidation **flag** → Continuation" vs "Impulse → **Pennant consolidation** → Continuation") and distinct invalidation rules, and the tolerance table at `15102` groups them only for the pole/consolidation *sizes*, not for identity. `APEX_GEN5.md:15113` (Registry governance, Round 3) requires an explicit AC.1 record per row and says rows are "not automatically mapped". No decision authorises two IDs from one hard-coded detector.

**Frozen status and non-frozen alternative**
`apex/pattern/detect.py`, non-frozen; no E01/E02 impact. If Pennant is later given a real detector, the hit space gains one ID and the 140-cell goldens change.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended) — give Pennant its own detector** with the documented pennant geometry (a narrowing continuation wedge, typically with a short-duration consolidation and often a volume contraction that Flag does not require), emitting `PAT-STR-009` only when that geometry is satisfied. Side effect: one new active row; new hit space; goldens change; needs the owner's tolerance numbers for the wedge convergence.
- **B — mark `PAT-STR-009` non-operational** (`RESEARCH_ONLY` or `DETECTOR_PENDING`) until A can be built, and state that in the registry comment. Side effect: the catalogue stops over-claiming; no new capability. Correct as an interim step.
- **C — make `detect_flag` shape-selective and return the matching ID.** Side effect: this is the "just change the ID" trap the auditor warns about; it would relabel flag geometry as pennant. Rejected on correctness grounds.

**My recommendation**
B now, A when the owner supplies the pennant tolerance. Never C. Add the CI guard from M-007 fix option C (every ACTIVE row with a detector must be reachable and must emit its own ID) — that single assertion covers both M-007 and M-008 permanently.

**Acceptance and regression tests**
1. For every ACTIVE row with a detector, `detect_all` on its canonical fixture must contain `row.pattern_id` and must not contain any other flag-family ID (the regression that would catch a relabelling).
2. `n_admitted_rows == n_run_here == number of distinct pattern_ids reachable from `detect_all``.
3. A negative test: a pure Flag fixture must **not** produce `PAT-STR-009`, and a true pennant fixture must not produce `PAT-STR-008`.

---

## M-009

**Auditor claim (short quote)**
"The Round-3 contract says catalogue=legacy and, until an AC.1 record is registered in `pattern_evidence` and promoted, no row is admissible; the `entity_for` code automatically creates ACTIVE and the bridge accepts it without looking up this table. On a fresh DB with zero `pattern_evidence`, `_pattern_entity("PAT-STR-001")` became ACTIVE; with a supplied entity for PAT-STR-005 and a requested ID of PAT-STR-001 it also accepted the inconsistent ID. The absence of `pattern_hit` is likewise not a default refusal."

**What I read (files, line ranges, functions, callers)**
`APEX_GEN5.md:15038, 15093, 15168, 15285` (Round-3 registry governance); `apex/pattern/detect.py:199–213` (`assert_scoring_admissible`), `:236–368` (`CatalogueRow`, `entity_for`), `:169–170` (`to_pattern_evidence_row`, the only place a `pattern_evidence` row is *produced*); `apex/ops/plan_bridge.py:490–503` (`_pattern_entity`), `:750–758` (the accept path); `apex/data_catalog/store/sqlite_store.py:121–139` (the `pattern_evidence` DDL). `grep -rnE "FROM pattern_evidence|INTO pattern_evidence" --include=*.py apex/` returns **nothing**.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/M-009_011.py` → `AUDIT/probes_V7/M-009_011.out`
```
  a FRESH repository CH4_DDL database: pattern_evidence rows = 0
  _pattern_entity('PAT-STR-001') on that EMPTY db -> pattern_id=PAT-STR-001
    lifecycle_status=ACTIVE contribution=s_i_component
    provenance_class=ACTIVE
  a caller-supplied PAT-STR-005 entity, requested as PAT-STR-001 -> ACCEPTED, entity.pattern_id=PAT-STR-005
  SELECT/INSERT against pattern_evidence anywhere in apex/:
  -> NONE.  The table is declared in CH4_DDL and never read or written.
  there is no `pattern_hit` table in CH4_DDL: ['market_observation', 'quality_vector',
      'snapshot_pit', 'evidence_event', 'pattern_evidence', 'setup_candidate', 'ledger', 'outcome']
```

**Verdict and reasoning**
**CONFIRMED.** The `pattern_evidence` table is declared in the frozen CH4 DDL and is read and written by nothing. `entity_for` constructs a `PatternEntity` directly from the legacy `CatalogueRow` and hard-codes `lifecycle_status` and `provenance_class` from the row's own `lifecycle_status` string — so "legacy catalogue row" and "ACTIVE operational entity" are the same value. On a database with zero `pattern_evidence` rows the bridge admits `PAT-STR-001` as ACTIVE with `setup_score_contribution_class="s_i_component"`. Separately, `_pattern_entity(pattern_id, supplied)` returns `supplied` **without checking that `supplied.pattern_id == pattern_id`**, so a `PAT-STR-005` entity is accepted when `PAT-STR-001` was asked for. And there is no `pattern_hit` table anywhere, so "no hit" has nothing to fail against: the accept path only refuses when `context.get("pattern_detected") is False`, an explicit producer flag.

**Root cause**
The data-plane registry required by AC.1 was never wired. The legacy catalogue is being used simultaneously as (a) the human reference and (b) the runtime admission authority, which is precisely what Round 3 forbids. The `supplied` short-circuit additionally has no ID-consistency assertion.

**Direct impact**
Any pattern ID in `CATALOGUE` is operationally admissible without a registered, promoted `PatternEntity`, and a caller can pass an entity whose `pattern_id` disagrees with the requested one. Both then feed `select_native_pattern` and the setup path.

**Secondary effects and interactions (upstream/downstream)**
Upstream, `entity_for`'s hard-coded ACTIVE also means M-007/M-008's unreachable rows still present as ACTIVE entities, so the store view and the capability view disagree. Downstream, `assert_scoring_admissible` only ever sees ACTIVE, so its RESEARCH_ONLY branch is reachable only for the three demoted harmonics. Interacts with M-011: because `family_id` is not stored, there is no durable record of *which* admitted pattern produced a setup, so post-hoc audit cannot close this loop.

**Contract and decisions**
`APEX_GEN5.md:15038`: *"The operational `pattern_evidence` registry (the Data Plane) is the authoritative materialization of AC.1 Pattern Entity records; **a catalogue row is not operationally admitted merely because it appears in Pattern Intelligence.**"* `APEX_GEN5.md:15113` (Round 3): *"its rows are **not automatically mapped** to AC.1 and do not acquire operational admission merely by appearing here. Any row intended for operational use requires an explicit AC.1 Pattern Entity record, a unique `PAT-<family>-<seq>` identifier, all mandatory AC.1 fields, and **materialization in the Data Plane `pattern_evidence`**."* Round 3 is a later owner decision than the Ch.9 catalogue, so it **overrides** any reading of Ch.9 that lets the catalogue self-admit. This precedence is decisive: the code is non-compliant with the governing decision, not merely with descriptive prose.

**Frozen status and non-frozen alternative**
The `pattern_evidence` **table** is part of the frozen CH4 DDL — the schema must not change. The **wiring** is entirely outside the frozen engines: `apex/ops/plan_bridge.py` and `apex/pattern/detect.py`. So the non-frozen remedy is: seed `pattern_evidence` from a promotion step, and make `_pattern_entity` read it. In-engine cost: zero. Cost of the non-frozen remedy: a one-time data migration of *content* (not schema) into an existing table, plus an owner ruling on which of the 16 rows are initially promoted.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended) — make `_pattern_entity` read `pattern_evidence` and fail closed on a miss.** Load the row by ID; if absent, raise `BridgeError("PATTERN_NOT_ADMITTED", pid)`. Add an explicit `supplied.pattern_id != pattern_id` check. Side effects: until the table is seeded, **every** pattern is refused and the PAPER path stops producing setups. That is the correct fail-closed behaviour but it needs a seeded migration in the same change, otherwise it is an outage.
- **B — keep the catalogue fallback but mark it explicitly.** Store a `provenance_class="CATALOGUE_LEGACY"` and a `promotion_state="UNPROMOTED"`, and refuse anything not PROMOTED. Side effect: equivalent refusal to A, with a worse audit trail. Weaker.
- **C — seed `pattern_evidence` at start-up from `entity_for` output.** Side effect: this *launders* the legacy catalogue into the operational registry, which is exactly the mapping Round 3 forbids; it makes the violation invisible rather than fixed. Rejected on contract grounds.

**My recommendation**
A, shipped together with an owner-ruled promotion list written into `pattern_evidence` so the two changes land atomically. C must be avoided — it would satisfy the letter of "materialized in `pattern_evidence`" while defeating its purpose, and it would be invisible in later audits.

**Acceptance and regression tests**
1. On a fresh `CH4_DDL` database with zero `pattern_evidence` rows, `_pattern_entity("PAT-STR-001")` must raise `PATTERN_NOT_ADMITTED`.
2. After seeding one promoted row, that ID is admitted and **every other** ID is refused — proving the registry is selective rather than a blanket gate.
3. `_pattern_entity("PAT-STR-001", entity_for(PAT-STR-005_row))` must raise (ID mismatch).
4. A CI assertion that `entity_for` is never called on the admission path without a preceding `pattern_evidence` lookup (a lint rule, so the legacy path cannot silently return).
5. A test that a `RESEARCH_ONLY` row present in `pattern_evidence` is refused by `assert_scoring_admissible` — proving the demoted harmonics are now enforced through the registry, not through the catalogue string.

---

## M-010

**Auditor claim (short quote)**
"`setup_id` is built only from a shortened symbol/timeframe/as_of/direction/fabric_hash; two evaluations with different stop/confidence/pattern/regime get the same ID. `_materialize_setup` used `INSERT OR IGNORE`, silently skipped the second row and kept the first; idempotency does not check content."

**What I read (files, line ranges, functions, callers)**
`apex/setup/family_sf_fvg_sweep_rev.py:336–372` (`to_setup_event`, the `setup_id` construction: `"setup-" + sha256_hex(canonical_json({"symbol","timeframe","as_of","direction","fabric_hash"}))[:32]`), `:482–485`; `apex/ops/plan_bridge.py:978–1006` (`_materialize_setup`, the literal `INSERT OR IGNORE INTO setup_candidate`), `:175–183` (`_SETUP_COLUMNS`, 21 names); `apex/data_catalog/store/sqlite_store.py:141–163` (the `setup_candidate` DDL with `setup_id TEXT PRIMARY KEY`). Callers of `to_setup_event`: `_materialize_setup` only.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/M-009_011.py` → `AUDIT/probes_V7/M-009_011.out`
```
  evaluation A: setup_id=setup-aa123951a9524ce6f4cc236ee3d3fe13
                stop_loss=99.0 confidence=None regime=None
  evaluation B: setup_id=setup-aa123951a9524ce6f4cc236ee3d3fe13
                stop_loss=99.0 confidence=None regime=None
  SAME setup_id for materially different setups? True
    A: atr=1.0 raw=0.9000 final=0.9000 risk_reference=99.0
    B: atr=3.0 raw=0.1800 final=0.1800 risk_reference=99.0
  after two INSERT OR IGNORE of DIFFERENT payloads sharing the id: 1 row(s)
    ('setup-aa123951a9524ce6f4cc236ee3d3fe13', '99.0', None, None, 'Q1')
  -> the second evaluation is silently discarded; no revision, no error.
```

**Verdict and reasoning**
**CONFIRMED.** Two evaluations of the same `(symbol, timeframe, as_of, direction, fabric)` cell — one with `atr=1.0 / final_score=0.90 / quality=Q1` and one with `atr=3.0 / final_score=0.18 / quality=QX` — produce the **identical** `setup_id`. The ID has no `payload_hash` component, even though a `payload_hash` column exists and is populated with the *fabric* hash rather than the setup payload. `INSERT OR IGNORE` then keeps the first row and drops the second with no error, no revision and no `supersedes` link. I additionally observed that `confidence` and `regime` are persisted as `None` in both cases, so the durable row is missing two more of the fields the audit lists as differing — the collision is even less recoverable than the audit states.

**Root cause**
Identity is derived from *inputs* while the record that must be unique is an *output*, and the write path uses `OR IGNORE`, which makes the collision a silent no-op rather than a detectable condition. `payload_hash` is populated from `fabric_hash`, so the column that exists precisely to detect this is present but inert.

**Direct impact**
Two materially different setups in the same cell share one durable row, and the persisted `quality` can disagree with the later evaluation. Any read of `setup_candidate` by `setup_id` therefore cannot tell which evaluation the record represents, and the `INSERT OR IGNORE` gives no signal that a second decision was taken.

**Secondary effects and interactions (upstream/downstream)**
Downstream, `outcome.setup_id` (present in the DDL) inherits the ambiguity, so pooled family statistics (M-011) cannot be attributed. Upstream, `fabric_hash` is the only content-bound component, so two setups on the same fabric but different bars/ATR collide. Interacts with M-003 (the score itself is hash-order dependent, so the row that "wins" the `OR IGNORE` is whichever ran first, which may be the 0.90 or the 0.18 evaluation).

**Contract and decisions**
`APEX_GEN5.md:15363–15369` (AD.1): *"`family_id` … is **immutable once a setup event is recorded**"*, and the amendment is described as *"forward-compatible: all existing 21-field contract implementations accommodate this field as an optional data extension without breaking."* Nothing in the contract authorises a key that ignores content. `PHASE2_TRACEABILITY_MATRIX.md` C6-FAM|3 records *"no-fabricated-score law: rejected cells report final_score 0.0 + entry None, never assume"* — the inverse problem (a silent keep-first) is not covered. I am not aware of any decision in `PHASE2_DECISION_LOG.md` governing `INSERT OR IGNORE` semantics for `setup_candidate`; the choice is therefore un-ratified and open to an owner ruling.

**Frozen status and non-frozen alternative**
The `setup_candidate` DDL is frozen (`setup_id TEXT PRIMARY KEY` cannot change). The **key derivation** and the **write semantics** are outside the frozen engines: `family_sf_fvg_sweep_rev.to_setup_event` and `plan_bridge._materialize_setup`. A sidecar versioned `payload_hash` is already an available column, so the non-frozen fix needs no schema change. In-engine cost: zero.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended) — derive `setup_id` from the setup payload, not the cell inputs**, and populate the existing `payload_hash` column with the same digest. Idempotency then becomes content-addressed: the same content re-inserts harmlessly, different content produces a different row. Side effect: **every** `setup_id` changes, so any already-persisted `outcome` rows orphan; requires a migration/backfill and a supersedes link. This is the only option that makes `OR IGNORE` semantically correct.
- **B — keep the key, detect the conflict and raise.** On insert, read the existing row; if `payload_hash` differs, raise `BridgeError("SETUP_CONTENT_CONFLICT", …)`. Side effect: fail-closed (good) but turns today's silent case into a hard stop on a live path, so it will surface in production as an outage until the conflict is understood. Pair with A eventually.
- **C — add a monotonically increasing `revision` suffix to the key on conflict.** Side effect: the key is no longer stable, so external references (`outcome.setup_id`) must be resolved by `(setup_id, revision)`. It is the cheapest non-outage option but it degrades the identity model the frozen DDL is built on.

**My recommendation**
A + B together: content-addressed identity as the target, and the explicit conflict check as the guard that proves A is in force. Migration cost is real and must be scheduled; it should be raised to the owner because it touches every historical `setup_id`.

**Acceptance and regression tests**
1. Two `to_setup_event()` calls differing only in `atr`/`risk_reference`/`final_score` must produce different `setup_id` values, and the `payload_hash` column must equal the digest of the setup payload.
2. Re-inserting the *same* `SetupEvaluation` must be a no-op (idempotency preserved) — assert the row count stays at 1 and no error is raised.
3. A property test over the 140 cells asserting `setup_id` uniqueness across differing payloads within one `as_of`.
4. A migration test: after the backfill, every pre-existing `outcome.setup_id` still resolves to exactly one `setup_candidate` row.

---

## M-011

**Auditor claim (short quote)**
"AD.1 `family_id` is field 22 and an immutable link to the pooled outcome result. `to_setup_event` supplies the value, but `setup_candidate` has no column and the bridge inserts only 21 columns; `outcome` does not write `family_id` either. So family membership cannot be reconstructed from the durable setup/outcome rows; the matrix test only passes the basic INSERT."

**What I read (files, line ranges, functions, callers)**
`APEX_GEN5.md:15365–15376` (AD.1 Field 22), `:15524–15530` (juncture 2, "family_id … binds each individual setup execution to a registered family"); `apex/setup/family_sf_fvg_sweep_rev.py:336–372` (`to_setup_event`, which *does* set `"family_id": self.family_id` and comments "additive AD.1 field 22"); `apex/ops/plan_bridge.py:175–183` (`_SETUP_COLUMNS`, with the comment *"Frozen setup DDL columns. `family_id` and gate/pattern detail remain in the producer payload/trace as required by AD.1; no frozen column is added."*), `:978–1004` (`_materialize_setup`, the per-column loop); `apex/data_catalog/store/sqlite_store.py:141–163` (`setup_candidate`), `:182–206` (`outcome`); `PHASE2_TRACEABILITY_MATRIX.md:210` (C6-FAM|3).

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/M-009_011.py` → `AUDIT/probes_V7/M-009_011.out`
```
  setup_candidate columns (21): ['setup_id', 'timestamp', 'symbol', 'timeframe',
      'pattern_ids', 'direction', 'entry_price', 'stop_loss', 'take_profit',
      'risk_reward', 'confidence', 'quality', 'validity', 'snapshot_id',
      'parent_ids', 'payload_hash', 'regime', 'utc_activity_window_id', 'lineage',
      'authority', 'authority_scope']
  family_id in setup_candidate? False
  outcome columns: ['outcome_id', 'entry_price', 'exit_price', 'pnl', 'fees',
      'slippage', 'mfe', 'mae', 'duration', 'exit_reason', 'risk_used',
      'forecast', 'setup_id', 'regime', 'context']
  family_id in outcome? False
  to_setup_event() keys: [... 'family_id' ...]
  family_id value produced by the family: SF_FVG_SWEEP_REV
  AD.1 says family_id is field 22, but the durable DDL stops at 21
  rows stored with only 6 of 21 columns: 2
```

**Verdict and reasoning**
**CONFIRMED.** `to_setup_event` produces `family_id = "SF_FVG_SWEEP_REV"`, the AD.1 value; the durable table has 21 columns and none is `family_id`; `outcome` likewise. The bridge's code comment is an explicit, deliberate decision to keep `family_id` "in the producer payload/trace" — so the value exists in memory and in the trace dict but never reaches a durable record. I also verified that the 21 frozen columns are all nullable in practice (I inserted a row with only 6 of them), so the schema offers no incidental protection.

The consequence stated by the auditor is exact: after the process exits, **no** durable artefact records which family a setup belonged to. The Promotion Protocol's pooled sampling unit — the union of outcomes across all symbols for a family (`APEX_GEN5.md:15524`) — cannot be computed from the store.

**Root cause**
A direct conflict between an additive contract amendment (AD.1 field 22) and a frozen base DDL (21 columns) was resolved by dropping the field at the persistence boundary rather than by adding the sanctioned sidecar. `AD.1` calls itself "forward-compatible", which is a claim about *consumers*, not about the frozen table; the implementation honoured the table and lost the field.

**Direct impact**
Pooled/UNPOOLED status and the pooled statistics that drive promotion are unrecordable and therefore unauditable. The UNPOOLED rule (`family_id = NULL` ⇒ forever research-only) has no durable representation, so an unpooled setup could not be distinguished from a pooled one after the fact even if one existed.

**Secondary effects and interactions (upstream/downstream)**
Upstream, `_materialize_setup` accepts a `store.insert_setup_event` fast path; if a future store implements it, the same drop would occur unless that method also persists `family_id`. Downstream, `outcome` inherits it, so promotion gates (Wilson lower bound, benchmark, Sharpe, PBO) have no grouping key. Interacts with M-010 (no stable `setup_id`) and M-009 (no durable pattern record), so two of the three durable keys needed for post-hoc audit are absent or ambiguous.

**Contract and decisions**
`APEX_GEN5.md:15365–15369`: *"Every SetupEvent (21-field contract) receives one additional field, applied **retroactively to all schema consumers**: **Field 22: `family_id`** … `NULL` if the setup is unpooled. A setup event with `family_id != NULL` is eligible for promotion."* `APEX_GEN5.md:15526` (juncture 2): *"The family_id is **immutable once a setup event is recorded**; it enables post-hoc aggregation of outcomes by family for pooled statistics computation."* And `APEX_GEN5.md:15526` (juncture 4) makes the Research Plane *"the single source of truth for family statistics and audit trail."* The contract therefore requires a durable, immutable, queryable field. The auditor's own fix column correctly notes the frozen schema must not be broken without permission — that permission is the missing step.

**Frozen status and non-frozen alternative**
`setup_candidate` is frozen CH4 DDL; an `ALTER TABLE` inside the migration path is exactly the kind of change that needs an owner ruling, and there is an explicit frozen-evidence event stream (`evidence_event`) in the same DDL that may be the sanctioned carrier. The non-frozen alternative is a **versioned sidecar** — either a new table keyed by `setup_id` (additive, non-breaking) or an `evidence_event` row of a new `feature_id` carrying the AD.1 binding — plus the same on the outcome side. In-engine cost: zero (the family already emits the value).

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended) — owner-ruled additive sidecar table** `setup_family_membership(setup_id TEXT PRIMARY KEY, family_id TEXT NOT NULL, family_schema_version TEXT, recorded_at TEXT, supersedes TEXT)` written in the same transaction as `setup_candidate`, plus the mirrored binding on `outcome`. Side effects: a schema addition (additive only, no frozen column altered or dropped); two stores must be written atomically; backfill required for historical rows. Fully satisfies `15526`'s immutability because the PK prevents a second binding and `supersedes` makes corrections reconstructible.
- **B — `ALTER TABLE setup_candidate ADD COLUMN family_id TEXT`.** Side effect: this *does* modify a frozen DDL table. It is the simplest solution and the contract's own "21-field base + AD.1 amendment" framing arguably describes precisely this. But the bridge's own comment asserts *"no frozen column is added"*, which reads like a standing constraint; adding one without an explicit ruling would be me breaking a freeze I was told not to break.
- **C — keep `family_id` in the trace only, and make the trace the audit record.** Side effect: traces are in-memory (`self.traces[...]`) and are lost on restart; promotion statistics would have no durable basis at all. Not viable as a primary mechanism.

**My recommendation**
A, and I would put option B to the owner explicitly as a question rather than assume it — the audit's constraint and the contract's wording pull in opposite directions, and only the owner can resolve which governs. C is not a substitute for either.

**Acceptance and regression tests**
1. After a full `evaluate_cell` → `_materialize_setup` round-trip on the repository's in-memory `CH4_DDL`, assert a durable record exists carrying `family_id == "SF_FVG_SWEEP_REV"` and that it is joinable to `setup_id`.
2. Assert the same binding is present (or explicitly NULL with a reason) on the outcome side.
3. A migration test: the additive sidecar applies to a database already containing rows, without altering any existing table, and a re-run is a no-op.
4. An immutability test: a second `INSERT` for the same `setup_id` with a different `family_id` must fail or record an explicit `supersedes` chain — never silently overwrite.
5. Update `PHASE2_TRACEABILITY_MATRIX.md:210` so C6-FAM|3 asserts the field is *durable*, not merely present in the in-memory payload.

---

## M-012

**Auditor claim (short quote)**
"`SetupEvent.stop_loss` is the sweep `risk_reference`, not the playbook's protective stop, which for a long is `min(sweep_low,fvg_low)-0.25ATR`; `take_profit` and `risk_reward` stay NULL, even though the plan is built from the real stop/target/R. In the setup row the trade geometry attributed to the same setup is incomplete/different."

**What I read (files, line ranges, functions, callers)**
`apex/setup/family_sf_fvg_sweep_rev.py:336–365` (`to_setup_event`: `"stop_loss": repr(self.risk_reference)`, `"take_profit": None`, `"risk_reward": None`), `:482–485`; `apex/playbook/pb_fvg_sweep_rev_a.py:379–417` (`build_stops`); `apex/ops/plan_bridge.py:821–843` (`build_stops` call, `fvg_low`/`fvg_high` sourced), `:866–870`, `:963–1004` (`_materialize_setup` called **after** `stops` is computed, with the `SetupEvent` dict only); `apex/data_catalog/store/sqlite_store.py:141–163`. Callers of `build_stops`: `plan_bridge` only.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/M-009_011.py` → `AUDIT/probes_V7/M-009_011.out`
```
M-012  SetupEvent.stop_loss is the sweep risk_reference, not the
        protective stop the playbook actually sends
  SetupEvent stop_loss   = 99.0
  SetupEvent take_profit = None
  SetupEvent risk_reward = None
  build_stops(LONG)       -> stop=94.75 target=115.75 R=5.25
  SetupEvent stop_loss == protective stop? False  (risk_reference is the sweep low)
  as persisted: [('99.0', None, None)]
  the plan that was actually built carried stop=94.75 target=115.75 R=5.25
```

**Verdict and reasoning**
**CONFIRMED.** The durable `setup_candidate` row stores `stop_loss = 99.0` (the swept low, a *reference*), while the order the same evaluation produced carries a protective stop at `94.75` with `target = 115.75` and `R = 5.25`. `take_profit` and `risk_reward` are written as literal `None`. A reader of `setup_candidate` alone therefore sees a stop 4.25 points tighter than the real one (an ~95 % overstatement of the risk unit if the row were used for sizing) and no target and no R at all.

I want to be precise about one thing the audit leaves implicit: the `SetupEvent` is materialised **after** `stops` is computed, so the correct values are in scope at the call site and are simply not passed. That makes this a wiring omission, not an architectural impossibility.

**Root cause**
`SetupEvent` is treated as the *setup's own* record and is filled from the family's internal state, while the trade geometry is computed later by the playbook. Nothing carries the playbook's output back into the setup record, and there is no versioned link from the setup row to the plan that carries the real terms.

**Direct impact**
Any post-hoc consumer that reads the setup row — research analytics, the Research Plane's pooled statistics, an operator reviewing a past setup — sees incomplete and wrong geometry. The real stop and target exist only in the plan, which is not joined to the setup row by any key.

**Secondary effects and interactions (upstream/downstream)**
Upstream, `risk_reference` and the protective stop differ by the FVG boundary plus `0.25·ATR`; the gap is data-dependent, so the error is not a constant offset. Downstream, `outcome.risk_used` exists in the DDL and would be the only real risk figure, but it is per-outcome, not per-setup, so a never-filled setup has no way to record its intended risk. Interacts with M-002 (the FVG boundary that moves the stop may itself be an unadmitted zone) and M-010 (the collision means a re-evaluation's geometry may never be persisted at all).

**Contract and decisions**
`PHASE2_TRACEABILITY_MATRIX.md` C6-FAM|2 records `risk_reference = swept extreme` as the **entry-logic** field, which is exactly right — the audit is not claiming `risk_reference` is wrong, only that it is stored in a column named `stop_loss`. `APEX_GEN5.md:15526` (juncture 2) requires the setup record to bind "each individual setup execution"; a record that does not contain the executed terms does not bind the execution. The contract does not explicitly say which column the protective stop belongs in, so an owner ruling on the *semantics* of `setup_candidate.stop_loss` is required before changing it.

**Frozen status and non-frozen alternative**
The 21-column `setup_candidate` DDL is frozen, and `stop_loss` is one of those columns — so the schema cannot be extended here. The non-frozen remedy is: (a) have the bridge pass the playbook output into the setup event so `stop_loss`/`take_profit`/`risk_reward` are populated with the *real* terms, and (b) keep `risk_reference` in the trace (where the matrix already places it) under an explicitly named key so the two are never confused. The frozen-schema alternative is the same sidecar as M-011. In-engine cost: zero.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended) — populate the three columns from `build_stops` output.** `plan_bridge` already has `stops` in hand at the `_materialize_setup` call; pass them in. Side effects: `stop_loss` changes meaning for every existing row, so a reader must be told the new semantics; historical rows stay wrong and need a backfill or an explicit "schema_version" marker. This is the only option that makes the row match the order.
- **B — leave `stop_loss` as the reference and add a versioned sidecar with the executed geometry.** Side effect: honest about the frozen column's meaning and preserves history, but every consumer must be taught to join the sidecar; risk that consumers keep reading `stop_loss`.
- **C — rename nothing, but null out `stop_loss` so it cannot be mistaken for a protective stop.** Side effect: loses a genuinely useful reference field and breaks the C6-FAM|2 assertion that the extreme is recorded. Rejected.

**My recommendation**
A, with B as the migration vehicle for history, plus a `setup_geometry_schema_version` marker so the semantics change is auditable. The naming problem should be raised with the owner: if `stop_loss` is contractually required to be the protective stop, then A is mandatory, not optional.

**Acceptance and regression tests**
1. For a LONG and a SHORT fixture, assert the persisted `setup_candidate` row's `stop_loss`, `take_profit` and `risk_reward` equal the plan's `stops['stop']`, `stops['target']` and `stops['R']` exactly.
2. Assert `risk_reference` remains available in the trace under its own key and is **not** stored in `stop_loss` (the regression that stops the two concepts being re-merged).
3. Assert `R` in the row is consistent with `|entry − stop|`, so a future geometry change cannot silently desynchronise the two.
4. A read-side test asserting that the Research-Plane aggregation over `setup_candidate` now sees a non-null target and R for every EMITTED setup.

---

## M-013

**Auditor claim (short quote)**
"`mtf_gate` in `1d` with `available_closes={}` gives `MISSING_REQUIRED_COARSER_BAR`; but `evaluate_cell` with the same empty closes and `mtf_state=ALIGNED/context_confidence=0.9` never calls that helper and reached `EMITTED/ALL_GATES_PASS` with otherwise-valid synthetic data. Gate 6 only sees the `mtf_state` string and the existence of a theoretical tier (`not vacuous`), not the actual bars; this is independent of D-015 where the required close was present. The current producer `mtf_projection` rejects a missing required coarser close earlier; a PAPER-native bypass is not concluded from this probe."

**What I read (files, line ranges, functions, callers)**
`apex/setup/family_sf_fvg_sweep_rev.py:172–208` (`relative_mtf`, `mtf_gate`), `:293–305`, `:396–418`, `:425–503` (`evaluate_cell`), `:547–570`; `apex/setup/gates.py:235–246` (`gate6_mtf_sufficient`); `apex/ops/engine_context.py:343–401` (`mtf_projection`, the producer that *does* raise `BridgeError("MTF_INSUFFICIENT", tf)` / `("MTF_STALE", tf)`), `:2000–2003`; `PHASE2_TRACEABILITY_MATRIX.md:200` (C6-G06); `APEX_GEN5.md:15333–15338`. Caller check: `"mtf_gate" in inspect.getsource(evaluate_cell)` → `False`. `inspect.signature(evaluate_cell)` **does** accept `available_closes: Optional[Mapping[str, Any]] = None` — the parameter exists and is never used for the MTF check.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/M-009_011.py` → `AUDIT/probes_V7/M-009_011.out`
```
  'mtf_gate' appears in evaluate_cell source? False
  gate6_mtf_sufficient source: ... passed = (mtf_state != "INSUFFICIENT") or (not has_coarser_bars)
  gate6_mtf_sufficient('ALIGNED')  -> passed=True
  gate6_mtf_sufficient('ALIGNED', has_coarser_bars=False) -> passed=True
  relative_mtf('1d') = {'setup': '1d', 'intermediate': '1mo', 'htf': '1mo', 'vacuous': False, ...}
  mtf_gate(timeframe='1d', available_closes={}) -> {'ok': False, 'reason': 'MISSING_REQUIRED_COARSER_BAR', 'missing': ['1mo', '1mo'], ...}
  mtf_gate(timeframe='1h', available_closes={}) -> {'ok': False, 'reason': 'MISSING_REQUIRED_COARSER_BAR', 'missing': ['4h', '8h'], ...}
    mtf_gate('1h', available_closes={'4h': 1000, '8h': 1000}) -> {'ok': True, 'reason': 'MTF_BARS_PRESENT', ...}
  and its own step 6 for 1d: None
  evaluate_cell(timeframe='1d', NO coarser bars supplied, no available_closes
    argument) -> status=EMITTED reason=ALL_GATES_PASS
    step6 = None
```

**Verdict and reasoning**
**CONFIRMED, and I raise the severity to S1.** The family ships a fully working `mtf_gate` — it correctly refuses `1h` with `missing: ['4h','8h']` and correctly passes when those closes are supplied — and `evaluate_cell` never calls it. The `available_closes` parameter is accepted by the signature and then ignored, which is the strongest possible evidence that the check was intended and simply not wired. `evaluate_cell(timeframe='1d', …)` with no coarser bars at all returns `EMITTED / ALL_GATES_PASS`, and its own `entry_logic_steps` has **no `6_mtf` entry at all** (`None`), so there is not even a recorded step. Meanwhile `gate6_mtf_sufficient` returns `passed=True` for *any* state other than the literal string `INSUFFICIENT`, and `has_coarser_bars` defaults to `True`, so the gate can essentially never block.

The auditor correctly limits the claim to the independent-API path, and I keep that limit: `mtf_projection` in the producer does raise `MTF_INSUFFICIENT`/`MTF_STALE` before the family is called, so I have **not** demonstrated a current PAPER-native bypass. The defect is that the family's own contract is unenforced and its API advertises a parameter that does nothing — which is an S1 exposure the moment any caller other than `mtf_projection` reaches the family, and an S2-by-construction gate (C6-G06) that can never fail.

**Root cause**
`mtf_gate` was written as a helper and exercised only by its own unit tests; `evaluate_cell` composes a different, weaker check that routes through `gates.gate6_mtf_sufficient`, which is a string comparison on `mtf_state` rather than a bar-presence test. The `available_closes` parameter was threaded into the signature without being wired.

**Direct impact**
`evaluate_cell` can emit on any timeframe, including `1d`, with no coarser bar ever having been observed — exactly the case the relative-MTF law says "does not emit". Every gate reports pass and no step is even recorded for MTF, so the trace cannot show the omission.

**Secondary effects and interactions (upstream/downstream)**
Upstream, `mtf_projection` returning `mtf_state="ALIGNED"` is currently the only thing preventing the bypass, and that is a single point of defence in a different file. Downstream, the emitted setup carries no MTF evidence, so a post-hoc audit cannot tell whether the MTF gate was satisfied. Interacts with M-001/M-002 (the same "presence string standing in for evidence" pattern) and with `PHASE2_TRACEABILITY_MATRIX.md:200`, which claims C6-G06 passes on "missing-required ≠ vacuous" — a claim the `has_coarser_bars` default makes unverifiable through the gate itself.

**Contract and decisions**
`APEX_GEN5.md:15333–15338`: *"**Relative MTF** … intermediate required coarsest available among L[i+2] else L[i+1] if strictly coarser; HTF required L[i+4] if exists else coarsest > T; if no coarser TF exists, HTF/intermediate gates **vacuous pass**. **Missing required coarser bar → that cell does not emit.**"* `PHASE2_TRACEABILITY_MATRIX.md:200` (C6-G06) restates it: *"MTF data unavailable on a TF WITH coarser tiers ⇒ block; the 1mo relative-MTF law is a documented vacuous PASS (no coarser TF exists); **missing-required ≠ vacuous**."* The two cases the contract distinguishes are exactly the two `gate6_mtf_sufficient` conflates. No decision in `PHASE2_DECISION_LOG.md` overrides this; the D-015 cross-reference is about a *present* required close and is, as the auditor says, a different case.

**Frozen status and non-frozen alternative**
E01/E02 are frozen and supply the MTF context; neither needs to change. The non-frozen remedy is a single call to `mtf_gate` inside `evaluate_cell`, using the `available_closes` parameter that is already in the signature. In-engine cost: zero.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended) — call `mtf_gate(timeframe, available_closes)` inside `evaluate_cell` and return `NOT_EMITTED` with the helper's own named reason when it fails**, while honouring the documented vacuous pass only when `relative_mtf(timeframe)["vacuous"]` is actually `True`. Side effect: cells that currently emit without coarser bars stop emitting; the 140-cell golden set shrinks; `entry_logic_steps` gains a real `6_mtf`. This also makes C6-G06 verifiable through the gate.
- **B — keep the producer as the sole enforcer and make the family fail loudly when it is called without `available_closes`.** Side effect: makes the contract enforceable but leaves the family unable to emit legitimately, and it does not close the "one point of defence" problem.
- **C — strengthen `gate6_mtf_sufficient` to require `has_coarser_bars` when the tier exists.** Side effect: the gate would need the bar data threaded into it, duplicating `mtf_gate`; and gate 6 is a frozen gate contract (C6-G06 with boundary tests), so changing its semantics ripples into the gate matrix. Possible but heavier than A.

**My recommendation**
A. It uses code that already exists and is already correct, it activates a parameter that is currently a lie in the signature, and it produces the `entry_logic_steps["6_mtf"]` record the trace is missing.

**Acceptance and regression tests**
1. `evaluate_cell(timeframe='1d', available_closes={})` → not `EMITTED`, reason `MISSING_REQUIRED_COARSER_BAR`, and `entry_logic_steps['6_mtf']` populated.
2. `evaluate_cell(timeframe='1h', available_closes={'4h':…, '8h':…})` → still `EMITTED` (no regression on the legitimate path).
3. A test for the documented vacuous pass: a timeframe with **no** coarser tier must still pass, distinguishing it from "missing required".
4. A test asserting `available_closes` is actually read — e.g. a sentinel that fails the test if the parameter is removed or ignored.
5. Re-baseline the 140-cell emission counts and update C6-G06's evidence pointer to the family-level test.

---

## M-014

**Auditor claim (short quote)**
"The Gate 10 docstring claims a 'full P/U/C contract' and rejects an incomplete record, but it only reads `quality/q_forecast` and a boolean `bootstrap_prior`: `gate10_forecast_quality({"quality":"Q3"}, environment="LIVE")` passed in the probe, with no `p_hat/u/c` and no identity/calibration; at the `run_all` level it also passes when the other values are filled separately. The current bridge runs `build_forecast` beforehand and sends only quality/bootstrap/h_norm from the ForecastRecord to the setup; passing the builder itself or a LIVE trade with this incomplete input is not demonstrated. H-014 concerns the validity of the calibrated-package label in the builder, not the schema inequality of Gate 10."

**What I read (files, line ranges, functions, callers)**
`apex/setup/gates.py:275–307` (`gate10_forecast_quality`, read in full — the only inputs consulted are `"q_forecast" in forecast`, `"quality" in forecast`, `forecast.get("bootstrap_prior", False)`, and the class value), `:310–346` (`gate11_snapshot_lineage`), `run_all`; `apex/ops/plan_bridge.py:760–817` (the `build_forecast` call and the fields forwarded); `APEX_GEN5.md:15317–15322` (the gate table), `:16066–16113`; `PHASE2_TRACEABILITY_MATRIX.md:204` (C6-G10). Callers of `gate10_forecast_quality`: `gates.run_all`.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/M-009_011.py` → `AUDIT/probes_V7/M-009_011.out`
```
  gates.gate10_forecast_quality({'quality':'Q3'}, environment='LIVE') ->
      GateResult(number=10, name='FORECAST_QUALITY', passed=True, measured='Q3',
                 threshold='Q2', reason='FORECAST_QUALITY_OK')
  gate10_forecast_quality({}, environment='LIVE') ->
      passed=False, reason='GATE10_FORECAST_QUALITY_MISSING'
  gate10_forecast_quality({'quality':'Q3','bootstrap_prior':True}, environment='LIVE') ->
      passed=False, reason='GATE10_BOOTSTRAP_PRIOR_NOT_LIVE_ELIGIBLE'
  fields the body actually reads:
    ['if "q_forecast" not in forecast and "quality" not in forecast:',
     'bootstrap = bool(forecast.get("bootstrap_prior", False))',
     'cls = forecast.get("quality", forecast.get("q_forecast"))', ...]
  an evidence/identity/calibration field is never consulted:
    ['snapshot_id', 'lineage', 'p_hat', 'evidence', 'calibration', 'package_version']
```

**Verdict and reasoning**
**CONFIRMED.** The docstring states two fail-closed conditions, one of which is that *"the forecast record must carry the full P/U/C contract"*. The body reads exactly three keys and consults none of `p_hat`, `u`, `c`, `snapshot_id`, `lineage`, `calibration` or `package_version`. A single self-declared string — `{"quality": "Q3"}` — passes Gate 10 in **LIVE**. The two conditions that *are* implemented both work correctly: an empty record fails, and a bootstrap prior is refused for LIVE. So the defect is a **docstring/claim-versus-implementation gap** on one of the two declared conditions, not a broken gate.

I accept the auditor's boundary: the current bridge runs `build_forecast` first and forwards only `quality`/`bootstrap`/`h_norm`, and I have **not** demonstrated a live trade on this incomplete input, nor that the builder itself can be bypassed. That is a claim-coverage defect, which is why I hold **S2** (and would hold S3 if the docstring were not the artefact other documents cite).

**Root cause**
The gate is written against a *quality label* interface while its documentation describes a *full forecast record* interface. The producer satisfies the gate by constructing a minimal dict, so the mismatch is never exercised.

**Direct impact**
A caller with a single self-asserted string satisfies a gate that the contract and the matrix both describe as validating a complete P/U/C forecast. The `bootstrap_prior` default is `False`, so an **omitted** flag is read as "not a bootstrap prior" — i.e. absence is treated as the live-eligible value.

**Secondary effects and interactions (upstream/downstream)**
Upstream, `build_forecast` producing the real record makes the current path safe, so there is no live consequence today. Downstream, Gate 12 (`q_forecast`) and Gate 13 (package) read neighbouring fields from the same dict, so the record's completeness is unevenly enforced across gates 10/12/13. Interacts with M-009 and M-012: nothing downstream binds the forecast to an identity, so a label cannot be traced to the record that justified it.

**Contract and decisions**
`APEX_GEN5.md:15317–15322` gate table: row 10 *"forecast quality fail | QUARANTINED BLOCK"*. `PHASE2_TRACEABILITY_MATRIX.md:204` (C6-G10) is precise and notably does **not** claim the P/U/C schema check: *"forecast package quality ≥ Q2 AND bootstrap prior REFUSED for LIVE … environment is an input, never inferred."* So the matrix matches the code and the **docstring** is the outlier. That is an important precedence observation: the traceability matrix is the more specific and more recent artifact, and it is the docstring that over-claims. I therefore read this as a documentation defect with a real risk of being cited as a control, rather than as a control failure.

**Frozen status and non-frozen alternative**
`apex/setup/gates.py` is the setup-gate layer, not a frozen engine. The non-frozen remedy is either to enforce the claim (bind the full record and its identity) or to retract it (rewrite the docstring and the Ch.13 cross-reference). In-engine cost: zero.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended) — retract the claim.** Rewrite the `gate10_forecast_quality` docstring to describe what it actually enforces (quality class + bootstrap eligibility), and correct the Ch.13 cross-reference so no other document cites it as a P/U/C validator. Side effects: none at runtime; the control inventory loses an overstated entry, which is the correct state. Cheap and truthful.
- **B — enforce the claim.** Require `p_hat`, `u`, `c` to be present and finite, and require a `snapshot_id`/`lineage` that Gate 11 can check. Side effects: every current caller must be updated, the producer's minimal dict becomes invalid, and Gate 10 starts failing on paths that pass today — a real behavioural change needing a re-baseline.
- **C — do both, in the order A-then-B.** Side effect: the docstring change is a small PR and the enforcement change is a larger one; combining them hides the cheap correction behind the expensive one. Rejected as sequencing.

**My recommendation**
A now, B as a separately scheduled change with its own re-baseline. The audit's own acceptance column proposes exactly this ordering ("either bind Gate 10 to a real validated P/U/C record, or remove the 'full record' claim from doc/test/matrix"), and I endorse it — with the note that in this case the **matrix is already correct** and only the docstring needs to change.

**Acceptance and regression tests**
1. A docstring-conformance test (or a lint) asserting that every phrase of the form "must carry X" in a gate docstring corresponds to a key the function reads — this class of defect is otherwise invisible to tests.
2. If B is adopted: `gate10_forecast_quality({"quality":"Q3"}, environment="LIVE")` must fail with a new named reason, and the producer must be updated so the current path still passes.
3. An explicit test that an **omitted** `bootstrap_prior` is not silently treated as `False` in LIVE — or a documented decision that omission *is* the non-bootstrap case.
4. Update `PHASE2_TRACEABILITY_MATRIX.md:204` only if B is adopted; it is currently accurate and should not be touched by A.

---

## M-015

**Auditor claim (short quote)**
"`build_proposal(direction=NO_TRADE)` deliberately sets `EU=-inf` and builds a valid NO_TRADE object, but the public `proposal_id` property and `to_dict` hand that same `-inf` to `canonical_json` and fail with `CanonicalJsonError: float NaN/Inf is forbidden`. The NO_TRADE test only checks shape/EU, not the ID; the ID test only covers a trading proposal. The native bridge refuses before building such a proposal, so a native trade failure is not proven."

**What I read (files, line ranges, functions, callers)**
`apex/decision/pipeline.py:411–459` (`StrategyProposal` dataclass, `to_dict`), `:462–493` (`build_proposal`, with `EU=float("-inf")` for `NO_TRADE`); `apex/identity/canonical_json.py:75–83, 128–144` (the `float NaN/Inf is forbidden` guard); `apex/ops/plan_bridge.py:905–914` (the native path refuses with a `BridgeError` before calling `build_proposal` with `NO_TRADE`); `tests/unit/test_decision_pipeline.py:310–334` (the NO_TRADE test) and `:136–148` (the ID test). `grep -rn proposal_id apex/ tests/` shows `proposal_id` is consumed only by the property and the tests.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/M-009_011.py` → `AUDIT/probes_V7/M-009_011.out`
```
M-015  build_proposal(NO_TRADE).proposal_id raises
  EU = -inf
  proposal_id -> CanonicalJsonError: float NaN/Inf is forbidden in canonical payloads
  canonical_json(p.to_dict()) -> CanonicalJsonError: float NaN/Inf is forbidden in canonical payloads
  the same call for a TRADE proposal:
    proposal_id = sp-7272e658ed64ebcdcdd5d400caefd3a3
```

**Verdict and reasoning**
**CONFIRMED.** A `NO_TRADE` proposal is a first-class return value of `build_proposal` with a valid shape, but any attempt to identify it or serialise it canonically raises. A trading proposal of the same call gets `sp-7272e658ed64ebcdcdd5d400caefd3a3` without difficulty. I hold **S3**: there is no current path that serialises a `NO_TRADE` proposal — the native bridge refuses earlier — and the auditor is explicit that they did not prove a native failure. The defect is that a documented, first-class output of a public API cannot be serialised or identified, which is a robustness/API-contract issue rather than a trading risk. It becomes S2 the moment anything persists a refusal record (which is a plausible next step, since a NO_TRADE is exactly what one would want to log).

**Root cause**
`EU = -inf` is the correct modelling choice for "worst possible utility" and would be right inside a ranking, but it is stored in a field that later flows into the canonical identity/serialisation path, where non-finite values are forbidden by design. The sentinel and the serialiser were never reconciled.

**Direct impact**
`proposal.to_dict()` and `proposal.proposal_id` both raise for `NO_TRADE`, so a caller that logs a refusal, writes a ledger entry, or attaches lineage gets an exception instead of a record. The `EU` ordering semantics that motivate `-inf` are unaffected, because `rank()` sorts in Python and never canonicalises.

**Secondary effects and interactions (upstream/downstream)**
Upstream, `arbitrate`/`select` produce NO_TRADE outcomes that flow into `_proposal_from`, which builds a *different* (playbook-level) dict that does not carry `EU` — so the practical blast radius today is small. Downstream, any future persistence of refusals inherits the exception. Interacts with M-016 (both are `build_proposal` API-surface defects) and with the canonical-JSON rule that other rows (N-002, N-017) depend on.

**Contract and decisions**
`apex/identity/canonical_json.py:75–83` is a hard rule: non-finite floats are forbidden in canonical payloads — this is an integrity control, not a style choice, and the auditor is right that it must not be relaxed to accommodate the sentinel. `apex/decision/pipeline.py:137–154` (`units_of_r`) shows the house convention for representable sentinels: it raises a named `DecisionError` rather than storing a non-finite value. No decision in `PHASE2_DECISION_LOG.md` governs `NO_TRADE` identity, so this needs an owner ruling.

**Frozen status and non-frozen alternative**
`apex/decision/pipeline.py` and `apex/identity/canonical_json.py` are outside the frozen E01/E02 engines and outside the frozen store DDL. The non-frozen remedy is to build the NO_TRADE identity from an explicit, finite, deterministic representation (for example an explicit `"decision":"NO_TRADE"` enum plus a `None`/omitted `EU`). In-engine cost: zero.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended) — exclude `EU` from the canonical payload for NO_TRADE and put an explicit finite sentinel in the identity input.** E.g. hash `{"setup_id", "direction":"NO_TRADE", "conflict_state", "snapshot_id", "eu_class":"REJECTED"}` with `eu_class` a string, while `EU` stays `-inf` in memory for ranking. Side effect: `to_dict()` output for NO_TRADE no longer contains a numeric `EU`, so any consumer that reads `to_dict()["EU"]` must handle the field's absence — but that is exactly the correct signal. No frozen control is relaxed.
- **B — set `EU` to a finite floor (e.g. the minimum representable) for NO_TRADE.** Side effect: the sentinel stops being order-equivalent to "worst", and if any future code compares floats it could rank a NO_TRADE equal to a real proposal. Rejected.
- **C — formally declare that a NO_TRADE proposal has no ID**, and make `proposal_id` raise a named `DecisionError("NO_TRADE_HAS_NO_ID", …)` instead of a `CanonicalJsonError`, documenting the contract. Side effect: explicit, but it still blocks logging the refusal, so it is a documentation improvement rather than a fix.

**My recommendation**
A. It preserves the `-inf` ranking semantics, keeps the canonical-JSON integrity rule untouched, and makes the refusal loggable — which is the obvious thing a caller will want. I explicitly reject any option that relaxes `canonical_json`.

**Acceptance and regression tests**
1. `build_proposal(..., direction=NO_TRADE).proposal_id` returns a deterministic hex id, and calling it twice gives the same value.
2. `canonical_json(p.to_dict())` succeeds for a NO_TRADE proposal, and the payload contains no `-inf`/`NaN`.
3. Assert `EU == -inf` is still preserved on the in-memory object (so ranking semantics are unchanged) — the fix must be in the serialisation, not the value.
4. Extend the existing NO_TRADE test to assert the ID, and extend the ID test to cover the NO_TRADE case — the exact gap the auditor identifies.
5. A negative test asserting `canonical_json` still raises for an explicitly non-finite `EU` supplied by a caller, so the integrity control remains independently covered.

---

## M-016

**Auditor claim (short quote)**
"`generate_candidates` copies one geometry and one P onto both LONG and SHORT without a side-specific reconstruction; with entry=100, stop=97, target=109, P=.6 both sides give `RR=3, EU=1.38` and a fake SHORT was produced. `build_proposal(direction='SHORT', …)` with this stop below entry and target above entry also returned EU=1.38 and a valid sizing request, because `units_of_r` takes absolute distances; CP-7 does not re-check the geometry when converting a proposal. The native bridge builds a direction-aware `build_stops` earlier and takes **only the intended-direction candidate** for the proposal; the fake side remains in the `ranked`/`selected` trace, not in the proven native plan."

**What I read (files, line ranges, functions, callers)**
`apex/decision/pipeline.py:137–154` (`units_of_r`: `stop_distance = abs(float(entry) - float(stop))`, `target_distance = abs(float(target) - float(entry))`, `rr = target_distance / stop_distance`, no sign check), `:220–249` (`generate_candidates`: `for side in ("LONG","SHORT")` over one `setup["entry"]/["stop"]/["target"]` triple), `:245–250` (`rank`), `:462–493` (`build_proposal`, which calls `units_of_r` and returns `sizing_request`); `apex/ops/plan_bridge.py:838–843, 866–921, 967–975` (the native path: `build_stops` is direction-aware, and only the intended-side candidate is passed to `build_proposal`); `apex/playbook/pb_fvg_sweep_rev_a.py:379–414` (`build_stops`); `apex/execution/fsm.py:288–345`; `tests/unit/test_decision_pipeline.py:39–41, 136–148`.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/M-009_011.py` → `AUDIT/probes_V7/M-009_011.out`
```
M-016  generate_candidates mirrors one geometry onto BOTH sides;
        units_of_r uses abs() so inverted geometry passes
  side=LONG  RR=3.0000 R=3.0000 EU=1.3900   (LONG wants stop<entry<target; SHORT wants target<entry<stop)
  side=SHORT RR=3.0000 R=3.0000 EU=1.3900   (LONG wants stop<entry<target; SHORT wants target<entry<stop)
  -> a SHORT with stop 97 BELOW entry 100 and target 109 ABOVE entry 100 is ranked at full EU 1.3900
  rank() order: ['LONG', 'SHORT']
  build_proposal(direction='SHORT', stop=97 < entry=100 < target=109)
    -> EU=1.3900 sizing_request={'requested': True, 'R_unit': 3.0, 'RR': 3.0,
        'stop_distance': 3.0, 'target_distance': 9.0}
    direction='SHORT' stop=97.0 targets=(109.0,)
  units_of_r(entry=100, stop=97, target=109) = {'R': 3.0, 'RR': 3.0, 'G': 9.0, 'L': 3.0, ...}
  units_of_r(entry=100, stop=103, target=91) [a genuine SHORT] = {'R': 3.0, 'RR': 3.0, 'G': 9.0, 'L': 3.0, ...}
```

**Verdict and reasoning**
**CONFIRMED, including the auditor's important boundary.** `generate_candidates` produces exactly two candidates from one geometry, with **identical** `RR`, `R` and `EU`, and the fake side is not marked as fake. `units_of_r` uses `abs()` on both distances, so `(entry=100, stop=97, target=109)` and the genuine short `(entry=100, stop=103, target=91)` are numerically indistinguishable — both return `R=3, RR=3`. `build_proposal(direction="SHORT", stop=97.0, targets=(109.0,))` returns a **valid sizing request** (`requested: True, R_unit: 3.0`) for a short whose stop is below entry and whose target is above it: a short that would be immediately profitable and immediately stopped. I verified the auditor's mitigation: the native bridge builds a direction-aware `build_stops` and passes only the intended-side candidate, so I do **not** claim a native trade failure. The residual exposure is (a) the fake side sits in the `ranked`/`selected` trace that operators and any consumer of the selection list read, and (b) any other caller of the public `generate_candidates`/`build_proposal` API.

**Root cause**
`generate_candidates` iterates over sides but reads a single side-agnostic geometry instead of reconstructing the mirror geometry per side; and `units_of_r`, which is the natural place to enforce directional consistency, deliberately uses absolute distances (correct for a magnitude, wrong as a validity check). No layer performs the sign check for the direction.

**Direct impact**
The public decision API can produce a profitable-looking, correctly-sized proposal for a side whose stop and target are inverted. `sizing_request` is populated, so a downstream risk layer that trusts `direction` plus `sizing_request` would size a trade whose stop is on the wrong side of entry.

**Secondary effects and interactions (upstream/downstream)**
Upstream, `family_sf_fvg_sweep_rev` produces a single direction per evaluation, so the family never supplies both sides — the mirroring is introduced purely by `generate_candidates`. Downstream, the `selected` list can contain a candidate for a side the setup never contemplated, and `composite_rank_score`/`arbitrate` operate over those candidates. Interacts with M-015 (same function, different defect) and with M-002 (a wrong-side FVG already shows that side-awareness is not enforced elsewhere).

**Contract and decisions**
`apex/decision/pipeline.py:137–154` (the `units_of_r` docstring): *"`R = |entry − stop|` and `RR = target_distance / stop_distance`. D59: `RR < min_rr` is a refusal `DECISION_NO_TRADE:RR_BELOW_MIN`."* The contract fixes the **magnitude** definitions; it does not authorise a directional validity check to be omitted, and `build_proposal`'s `sizing_request` implies a real, executable order. `apex/playbook/pb_fvg_sweep_rev_a.py` `build_stops` is direction-aware (`min(...)` for LONG, `max(...)` for SHORT), which establishes the house convention that side determines geometry. `APEX_GEN5.md` and the decision log contain no decision permitting sign-inverted geometry, and D59's refusal rule is on `RR`, which is identical for both cases.

**Frozen status and non-frozen alternative**
E01/E02 are frozen and are not the locus; the family already produces one direction per evaluation. The non-frozen remedy is entirely in `apex/decision/pipeline.py` (and, for defence in depth, an assertion at the plan boundary). In-engine cost: zero.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended) — make the direction explicit in `units_of_r` and require it everywhere.** Add a `direction` parameter and validate: LONG ⇒ `stop < entry < target`; SHORT ⇒ `target < entry < stop`; raise a named `DecisionError("GEOMETRY_DIRECTION_INCONSISTENT", …)` otherwise, while keeping `abs()` for the magnitude. Also have `generate_candidates` reconstruct the mirror geometry per side instead of copying, or emit only the side the setup actually describes. Side effects: callers must be updated; a behaviour change on any currently-passing inverted input; sizing requests become fail-closed.
- **B — validate only at `build_proposal`.** Side effect: fixes the order-construction boundary but leaves `ranked`/`selected` polluted with a fake side, which is precisely the residual exposure the auditor names. Insufficient alone.
- **C — mark the mirrored candidate `"synthetic": True` and exclude it from `select`.** Side effect: preserves the candidate for diagnostics (which may be what the trace is for) while removing it from selection. Cheap, and complementary to A, but on its own it leaves `build_proposal` able to build an inverted proposal.

**My recommendation**
A as the target, implemented in two steps so the blast radius is visible: first the validation in `units_of_r`/`build_proposal` (fail-closed, B-strength), then the per-side reconstruction in `generate_candidates` (which is the real fix and the one that empties the fake side out of the trace). C is a reasonable interim marker but should not be the endpoint.

**Acceptance and regression tests**
1. For every (entry, stop, target) triple with a sign-inverted side, `build_proposal` must raise a named error and must **not** return a `sizing_request`.
2. `generate_candidates` on a single setup must return at most one candidate per side, and a candidate for a side the setup does not describe must be either absent or explicitly marked and excluded from `select`.
3. A property test over randomised finite triples asserting `direction`-consistent input never raises and `direction`-inconsistent input always raises.
4. An integration assertion on the native path that the `ranked`/`selected` trace contains only the intended direction — the mitigation the auditor identified, made into a permanent guard.
5. A test that `units_of_r`'s magnitude outputs (`R`, `RR`, `G`, `L`) are **unchanged** for all valid inputs, so the fix does not alter any calibrated figure.

---

## N-001

**Auditor claim (short quote)**
"E01's `run_pipeline` slices `candles[:idx+1]`, so a BOS at bar b is re-evaluated at every later i; the same support event that emitted EV_STR_004 at bar 34 in a 70-bar window emits a different event at bar 62 in a 200-bar window. Growing the window changed the emitted set and the `at_bar` of already-emitted events."

**What I read (files, line ranges, functions, callers)**
`apex/engines/e01_structure/engine.py:545–559` (the `for i in range(...)` loop with `candles[:i+1]`), `detect_bos`, `detect_swings_williams`, `run_pipeline`, `StructureEngineStreaming` (`:1212–1246`); `apex/ops/engine_context.py:1339–1349, 1434–1455` (the producer takes a 300-bar window and calls `run_pipeline`); callers of `run_pipeline`: `engine_context.py` and `StructureEngineStreaming` (`grep -rn run_pipeline apex/`).

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/N-001_002_003.py` → `AUDIT/probes_V7/N-001_002_003.out`
```
N-001  window slicing structurally guarantees old output equality; growing
       windows removed historical BOS 0/62, 0/62, 34/62, and 62/62 at
       lengths 70/100/130/200.
```

**Verdict and reasoning**
**CONFIRMED.** I reproduced the exact instability the auditor describes: the same support event yields `(0, 62)`, `(0, 62)`, `(34, 62)`, `(62, 62)` depending only on the total window length. The mechanism is structural, not statistical: every `i` re-evaluates a *prefix*, so the last prefix always wins and earlier ones are discarded; a growing window therefore silently replaces historical `at_bar` values and can remove them entirely. My probe deliberately used trend-bearing synthetic data, because smooth fixtures produce no E01 events at all (that dead end is recorded in the errors section).

**Root cause**
The pipeline is defined as "for every prefix, run the detector and keep the last non-empty result", instead of "run the detector incrementally on the newest bar and keep the incremental result". Prefix recomputation is a batch convenience that was mistaken for a streaming contract.

**Direct impact**
Any E01 output is a function of the window length, not of the data. Historical events are not stable under a longer window, so a re-run over a longer history rewrites the event stream, and the `at_bar` recorded in evidence changes for events already persisted. `snapshot_id`s derived from E01 payloads (N-018) inherit the instability.

**Secondary effects and interactions (upstream/downstream)**
Upstream, `engine_context.py` slices a fixed 300-bar window, so the same 300 bars always give the same answer — the instability is latent on the current path but unavoidable for any consumer that varies the window (research, backtest, the streaming class in N-023). Downstream, the fabric's `as_of` and every E01 `snapshot_id` are window-dependent, so a replay at a later `as_of` with a longer lookback produces different identities for the same structure. Interacts with N-002, N-004, N-005, N-007, N-017 and N-023 — all of which are downstream expressions of the same "no stable per-bar identity" problem.

**Contract and decisions**
`APEX_GEN5.md:15333–15338` and the E01 §8.3 no-future-leak law (matrix row E01-11, `PHASE2_TRACEABILITY_MATRIX.md:384`): *"§8.3 no-future-leak (mutate t+1 + prefix invariance)"*. **Prefix invariance is written into the traceability matrix as a CP-2 acceptance criterion, and the engine does not satisfy it.** I reproduced this directly with the repository's own generator in `AUDIT/probes_V7/N-022_test_coverage.out`: `no_future_leak_check(lcg_candles(n, seed=3))` returns `True` at n=60, 61, 80, 120 and **`False` at n=165, 200, 300**. No decision in `PHASE2_DECISION_LOG.md` relaxes prefix invariance; D35 concerns ATR memoisation and output parity within a run, not window-length stability.

**Frozen status and non-frozen alternative**
E01 is frozen, so an in-engine fix needs an owner ruling. The non-frozen remedy is producer-side: fix the window length and the lookback policy in `apex/ops/engine_context.py` so the window is a governed constant, and record the window length in the `snapshot_id` inputs so a change in window is a visible identity change rather than a silent one. In-engine cost, if the owner rules for a change: the `EV_STR_*` goldens and the `FIX_001–010` fixtures are all prefix-sensitive, so every golden must be regenerated, every `snapshot_id` recorded in `evidence_event` becomes a historical value that no longer reproduces, and any calibration fitted on E01 output must be refit. **No retraining of a model is implied** (E01 is rule-based, not learned), but the identity/golden cost is total.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, outside frozen) — govern the window and expose it in identity.** Fix the producer's lookback to a single governed constant and fold the window length into the E01 `snapshot_id` pre-image. Side effect: no E01 change at all; the identity change is a deliberate, visible version bump; consumers that already stored E01 snapshots keep them as historical.
- **B — incrementalise `run_pipeline` into a per-bar step** inside the engine (owner ruling required). Side effect: full golden regeneration, every E01 `snapshot_id` changes, and the `FIX_001–010` fixtures plus the §8.2 deterministic-replay tests must be rewritten. This is the correct long-term fix and the most expensive one.
- **C — keep the batch semantics but define stability as "stable for a fixed governed window"** and reword the matrix's "prefix invariance". Side effect: cheapest, and it makes the contract match the code; but it removes a genuine PIT guarantee that the rest of the system relies on, and a reviewer could reasonably read it as weakening a control to match a bug. I would not recommend it without an explicit owner decision.

**My recommendation**
A now (it is cheap, outside the freeze, and makes the problem visible in identity), and B proposed to the owner with the full golden/identity cost written out. C only with an explicit, recorded owner decision.

**Acceptance and regression tests**
1. For every window length in a fixed set (e.g. 70, 100, 130, 200, 300), assert that the set of `(event_type, at_bar)` pairs for bars `< L_min` is **identical** — the direct statement of prefix invariance.
2. Run the repository's own `no_future_leak_check` at n = 60, 120, 165, 200, 300 on several seeds; it must return `True` at every length. Today it returns `False` at n ≥ 165 (see `N-022_test_coverage.out`).
3. Assert the window length appears in the `snapshot_id` pre-image, so a policy change is detectable from identity alone.
4. A golden test pinning the full EV_STR_* event list for the 300-bar governed window, so any future incrementalisation has a baseline to compare against.

---

## N-002

**Auditor claim (short quote)**
"One unchanged level generated 26 distinct bullish-BOS snapshot IDs on consecutive closes; the same structure over the same history yields a different snapshot_id per close, so an event cannot be re-identified."

**What I read (files, line ranges, functions, callers)**
`apex/engines/e01_structure/engine.py` `detect_bos` (the `generate_snapshot_id` call site and its payload), `apex/engines/base.py` (`generate_snapshot_id`, `snapshot_id` helpers), `apex/ops/engine_context.py:1912–1934` (the producer attaching `snapshot_id` to the BOS `bos` dict it builds and passes to the family). Callers of `generate_snapshot_id` across E01: `grep -rn generate_snapshot_id apex/engines/e01_structure/`.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/N-001_002_003.py` → `AUDIT/probes_V7/N-001_002_003.out`
```
N-002: one unchanged level generated 26 distinct bullish-BOS snapshot IDs on consecutive closes.
```

**Verdict and reasoning**
**CONFIRMED.** A single unchanged structural level, with nothing about the structure changing, produced 26 different `snapshot_id` values across consecutive closes. The identity therefore tracks the *observation bar* rather than the *structural fact*, which is the opposite of what a content-addressed identity is for. I assign **S2** (the audit says S1) because there is no current incorrect behaviour: every emitted id is unique and no collision occurs. The harm is that ids are not re-identifiable, which is an auditability and dedup problem — significant, but not a wrong trade or a fabricated signal.

**Root cause**
The snapshot pre-image includes the emitting bar (or an equivalent per-observation field), so the same structure at a different observation time is a different object. Whether that is deliberate ("every observation is its own evidence") or accidental cannot be determined from the code; the contract language on E01 snapshot identity points towards the accidental reading.

**Direct impact**
An E01 event cannot be matched across runs, across producers, or across replay. Deduplication, supersession and correction tracking all require a stable structural key, which does not exist.

**Secondary effects and interactions (upstream/downstream)**
Upstream, the producer copies `bos_native["snapshot_id"]` into the family input, so the family's own `fabric_hash` inherits the volatility. Downstream, `setup_candidate.snapshot_id`/`payload_hash` (M-010) transit the same instability. Interacts with N-017 (a cache key that omits the parameters), N-018 (snapshot collision across engines) and N-001 (window dependence) — the four together mean there is currently no stable E01 identity at any layer.

**Contract and decisions**
`APEX_GEN5.md:14672–14768` (the evidence/snapshot law): snapshot identity must be the hash of the canonical payload so that the same content always yields the same id and different content never collides. `PHASE2_TRACEABILITY_MATRIX.md` C6-G11 requires Gate 11 to recompute `snapshot_id == sha256(canonical_json(payload))` — which passes here (the ids *are* correct hashes) while still being unusable for re-identification, because the payload itself carries the bar index. The control is satisfied in letter and defeated in purpose. `tests/unit/test_e01_structure.py` asserts `s1 == s2` for two identical candle sets (determinism), which is a different and weaker property than re-identifiability.

**Frozen status and non-frozen alternative**
E01 is frozen. Non-frozen remedy: the producer can key E01 evidence by the *structural* content (level price, direction, swing index) rather than the emitting bar when building the fabric member, leaving the engine's per-observation id intact. In-engine cost if the owner rules for a change: the `snapshot_id` becomes structural, so every E01 id in `evidence_event` and every dependent `setup_candidate.snapshot_id` becomes a historical value; the §8.7 serialisation goldens and the §8.2 replay fixtures must be regenerated. No model retraining is implied.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, outside frozen) — add a structural key alongside the observational id.** Have the producer derive a `structural_key` (direction + level price + swing index) for matching/dedup, and keep `snapshot_id` as the per-observation evidence id. Side effect: a new key in the fabric layer; no engine change; Gate 11 continues to validate `snapshot_id` unchanged; dedup and supersession become possible.
- **B — change the engine's snapshot pre-image to drop the bar** (owner ruling). Side effect: two structurally identical BOS at different bars become the **same** id, which is a collision risk for legitimate repeated evidence — so a `revision`/`occurrence` counter would be needed, which reintroduces the ambiguity. Expensive and semantically worse.
- **C — declare per-observation identity as intended and document that re-identification is out of scope.** Side effect: honest, but then supersession/correction (which `APEX_GEN5.md:14700`-ish requires for lineage) has no key to operate on, so the documentation gap moves rather than closes.

**My recommendation**
A. It is entirely outside the freeze, preserves Gate 11 exactly as written, and gives the system the structural key it currently lacks for N-018, N-019 and correction tracking.

**Acceptance and regression tests**
1. Re-run the same 26-bar fixture and assert the **structural key** is constant across all 26 closes, while `snapshot_id` remains distinct (documenting both properties explicitly).
2. Assert a structurally identical BOS in a different window (N-001's growth test) yields the same structural key — this is the property that currently fails and is the real fix.
3. Assert Gate 11 still passes for every id (no weakening of C6-G11).
4. A dedup test: two fabric members with the same structural key and different `snapshot_id`s must be reconciled by the producer, not both admitted as independent evidence.

---

## N-003

**Auditor claim (short quote)**
"`run_pipeline` returns events, swings, atr, meta; the producer computes `htf_swings` and puts it in the context, but `run_pipeline`'s signature has no `htf_swings` and the value is never read by any consumer."

**What I read (files, line ranges, functions, callers)**
`apex/engines/e01_structure/engine.py` `run_pipeline` (return dict and signature); `apex/ops/engine_context.py` (the E01 section that builds `htf_swings` and puts it in the context dict); `grep -rn htf_swings apex/` and `grep -rn proximity_HTF apex/`; the E02 side reads `set_htf(htf_levels, atr_htf)` and computes `p_htf` in `_update_fates`/`compute_salience` — so the HTF concept is live for E02 and dead for E01.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/N-001_002_003.py` → `AUDIT/probes_V7/N-001_002_003.out`
```
N-003: `run_pipeline` has no `htf_swings`; producer context value is never read.
```

**Verdict and reasoning**
**CONFIRMED.** `htf_swings` is produced by the producer and appears in no consumer. The HTF relationship exists and is implemented for E02 (`set_htf`, `_nearest_htf`, `compute_salience`'s `p_htf`) but has no E01 counterpart. I assign **S2**: dead computation, wasted work, and a misleading signal of HTF-aware structure detection. No current output is wrong.

**Root cause**
An HTF-structure capability was built for E02 and mirrored in the producer's context for symmetry, but E01's `run_pipeline` never received a parameter for it and no E01 consumer was written.

**Direct impact**
None on values. Cost is a false impression in the context/trace that E01 outputs are HTF-aware, plus compute spent building swings nobody reads.

**Secondary effects and interactions (upstream/downstream)**
Upstream, the producer pays for the computation on every cell. Downstream, `select_native_pattern` and the family receive no HTF structural input, so any future rule that assumes E01 HTF context will silently see `None`. Interacts with N-013 (MTF evidence is likewise asserted at the string level rather than measured) — the same "the MTF relationship is declared but not enforced" family of gap.

**Contract and decisions**
`APEX_GEN5.md:15333–15338` defines relative MTF for the *setup family*, not for E01 internals, so the contract does not require E01 to consume HTF swings. The governing requirement is efficiency and truthfulness of the context. I found no `PHASE2_DECISION_LOG.md` entry authorising or describing this producer field, so it is un-ratified.

**Frozen status and non-frozen alternative**
E01 is frozen, so adding an `htf_swings` parameter to `run_pipeline` would require an owner ruling. The non-frozen remedy — and the one I recommend — is to delete the dead producer computation, which is outside the freeze entirely. In-engine cost if the owner later wants the feature: a new parameter, goldens regenerated, E01 `snapshot_id` payloads change if the HTF context enters any evidence payload.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended) — remove the dead computation from the producer.** Single path: side effect is a small performance win and the loss of a misleading context key; if a future E01 HTF feature is approved it can be re-added deliberately with its own design. This is the only option that makes the code say what it does.
- **B — wire it into E01** (owner ruling; new parameter). Side effect: full golden regeneration, changed `snapshot_id` pre-images, and a genuine semantic change to E01 outputs. Justified only if a rule actually needs it — none does today.
- **C — leave it and add a comment.** Side effect: none functionally; the misleading context key persists and a future reader may build on it. Weakest.

**My recommendation**
A. There is no consumer, no contract requirement and no rule that would use it, so carrying it is pure cost and a trap.

**Acceptance and regression tests**
1. A test asserting the producer context contains no key that is absent from the set of keys read downstream — a generic "no dead context" lint that would catch this class cheaply.
2. If B is ever adopted: an E01 test asserting HTF swings change the emitted structure in the direction and magnitude the contract specifies.
3. Assert the E01 output is byte-identical before and after the removal (it must be — that is the point).

---

## N-004

**Auditor claim (short quote)**
"A 200-bar run emitted only 3 of 21 declared structure event types; the declared `EV_STR_001..021` catalogue is not actually implemented, and the docstrings/§9 tables list event types the code never emits."

**What I read (files, line ranges, functions, callers)**
`apex/engines/e01_structure/engine.py` (`run_pipeline`, `detect_bos`, `detect_swings_williams`, and the declared event-type strings), `apex/engines/base.py`; `apex/ops/engine_context.py` (the consumer that filters by `event_type`, e.g. `if ev["event_type"].startswith("EV_STR_007") or ev["event_type"].startswith("EV_STR_008")` in the CP-2 redundancy test and the BOS selection at `:1927–1931`); `tests/unit/test_e01_structure.py` (which asserts specific `EV_STR_*` ids exist, so the suite only covers the emitted subset); `PHASE2_TRACEABILITY_MATRIX.md:374–397` (E01-10/E01-11).

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/N-001_002_003.py` → `AUDIT/probes_V7/N-001_002_003.out`
```
N-004: a 200-bar run emitted only 3 of 21 declared structure event types.
```

**Verdict and reasoning**
**CONFIRMED.** A 200-bar run produced events from only 3 distinct `event_type` values, against 21 declared in the engine's own tables/docstrings. The consumer code, however, only ever branches on a small subset (`EV_STR_007`/`EV_STR_008` in the redundancy test, "any event with `strength`" for the BOS pick), so nothing downstream is currently broken. I assign **S2**: the defect is a real completeness gap between declared and implemented surface, with wasted consumer complexity and a contract that over-describes the engine, but no wrong output.

**Root cause**
The engine's declared event catalogue was written ahead of (or independently of) the implementation, and the prefix-recompute design (N-001) means the detectors are few and coarse rather than 21 fine-grained event types.

**Direct impact**
The published E01 surface is not the implemented surface. Any consumer, review or integration written against the declared 21 will find at most 3.

**Secondary effects and interactions (upstream/downstream)**
Downstream, `engine_context.py` contains `startswith("EV_STR_007")`/`("EV_STR_008")` branches; if those ids are among the 18 never emitted, the corresponding consumer logic is dead. Interacts with N-005 (timing semantics of the events that *are* emitted) and with `PHASE2_TRACEABILITY_MATRIX.md:374–397`, whose E01-10/E01-11 rows describe a "FULL battery: FIX_001–010" whose coverage cannot be assessed against declared ids that do not exist in output.

**Contract and decisions**
`PHASE2_TRACEABILITY_MATRIX.md:384` (E01-11) claims *"FULL battery: FIX_001–010, §8.2 deterministic replay, §8.3 no-future-leak …, §8.4 ablation, §8.5 Wilson/z, §8.7 serialization"* and records `tests/unit/test_e01_structure.py (44 tests) | PASS(2026-09-12)`. I ran the suite: 44 tests pass. But passing tests over 3 emitted event types cannot evidence a 21-type contract. `APEX_GEN5.md:2914–2925` and `:3033–3049` define E02's event semantics in detail; the equivalent E01 section is what declares the 21. The precedence point: the matrix is the more specific acceptance artifact, and it is accurate about *what was tested* while the engine's own §9 tables are accurate about *what is declared* — neither establishes that all 21 exist.

**Frozen status and non-frozen alternative**
E01 is frozen, so neither adding the missing event types nor removing them from the documentation can be done unilaterally. Non-frozen remedies: (a) the producer can stop branching on ids that are never emitted, and (b) the documentation (`APEX_GEN5.md` §9 / the engine docstrings) can be corrected to the implemented set. In-engine cost if the owner rules to implement the missing 18: each new event type needs a definition, a PIT rule, a `snapshot_id` pre-image and a golden; the §8.7 serialisation fixtures and the E01-11 goldens are all regenerated, and downstream consumers that switch on `event_type` must be updated. Substantial.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended) — reconcile the declared surface with the implemented one.** Either mark the 18 unimplemented ids as reserved/not-implemented in the documentation and in the matrix, or, if the owner wants them, raise a scoped implementation request with the golden cost stated. Side effect: documentation change only for the first half; no runtime change; it stops the false surface claim immediately.
- **B — implement the 18 (owner ruling).** Side effect: full golden and identity regeneration, downstream `event_type` branches must be re-checked, and the §8 battery must be re-evidenced. Very expensive for no current consumer.
- **C — leave both and add a CI assertion that every declared id is either emitted on the fixture set or explicitly listed as reserved.** Side effect: cheap, and it is the guard that stops the drift from recurring. Complementary to A.

**My recommendation**
A + C, and explicitly **not** B — nothing consumes the 18 today, so implementing them is unjustified cost inside a freeze. I would put B to the owner only if a downstream requirement appears.

**Acceptance and regression tests**
1. A CI check that the declared `EV_STR_*` set equals the set emitted across the fixture corpus, with an explicit `RESERVED_EVENT_TYPES` allow-list — the audit's underlying point turned into a permanent guard.
2. Assert the CP-2 redundancy test's `EV_STR_007`/`EV_STR_008` branches are exercised; if those ids are never emitted, the test is currently vacuous and must be marked as such or removed.
3. A documentation test asserting the §9 event table lists only ids present in `EVENT_TYPES`.

---

## N-005

**Auditor claim (short quote)**
"Emitted events use close time, `_to_evidence` uses timestamp/as-of, gap events use open time, and swing availability is absent; the same instant is described by three different times and a consumer cannot tell which is the observation time."

**What I read (files, line ranges, functions, callers)**
`apex/engines/e01_structure/engine.py` (the event construction sites: `detect_bos` and the gap detector use `open_time`/`close_time` from the candle dict; `to_evidence`/`_to_evidence` builds the evidence with `as_of` and a `timestamp`); `apex/engines/base.py` (the evidence/snapshot helpers); `apex/ops/engine_context.py` (the consumer that assembles the fabric from `_to_evidence` output and the producer that sets `as_of`); `tests/unit/test_e01_structure.py` (what the suite asserts about timestamps).

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/N-001_002_003.py` → `AUDIT/probes_V7/N-001_002_003.out`
```
N-005: emitted events use close time, `_to_evidence` uses timestamp/as-of,
       gap events use open time, and swing availability is absent.
```

**Verdict and reasoning**
**CONFIRMED.** Within one output I observed three different notions of time for the same bar: the event payload uses `close_time`, the evidence wrapper carries its own `timestamp` and the caller's `as_of`, and gap events use `open_time`. Swing availability (whether the swing was confirmable at that instant) is not recorded at all. I assign **S2** (the audit says S1): the times are individually well-defined and self-consistent within their own producer, so nothing is calculated wrongly; the defect is that a consumer cannot determine the true observation instant, which is an evidence-quality and replay hazard rather than a wrong trade.

**Root cause**
The engine emits domain events (natural to time-stamp at close, and at open for a gap) while the evidence layer re-wraps them with a generic `timestamp`/`as_of` pair. No schema field states which is authoritative, and no availability bit records whether a referenced swing was itself still provisional.

**Direct impact**
A consumer doing PIT reconstruction cannot tell whether an event was knowable at its stated time, and replay at a given `as_of` has no reliable basis for inclusion. Gap events additionally assert something about an `open_time` before the bar has closed.

**Secondary effects and interactions (upstream/downstream)**
Upstream, the fabric's `as_of` and the engine's `close_time` are different fields, so a fabric assembled "as of" a moment can legitimately contain an event whose `close_time` is later. Downstream, Gate 11 checks the snapshot hash, not the time semantics, so it cannot catch this. Interacts with N-001 and N-006 (both are PIT-realisation problems) and with N-019 (lineage tokens derived from bar indices rather than from the actual observation).

**Contract and decisions**
`APEX_GEN5.md:14672–14768` requires evidence to carry a PIT-defensible `as_of` and forbids a future `as_of` ("Future as_of → INVALID (PIT)"). `PHASE2_TRACEABILITY_MATRIX.md:384` (E01-11) claims the §8.3 no-future-leak requirement is met, and I confirmed from `N-022_test_coverage.out` that the suite's leak test only checks bar-count invariance (`no_future_leak_check` on prefixes), never the time fields. So the matrix's PIT claim rests on a test that does not examine timestamps at all — a precedence-relevant gap.

**Frozen status and non-frozen alternative**
E01 is frozen. Non-frozen remedy: the producer (`apex/ops/engine_context.py`) can normalise event times into a single documented field on the way into the fabric, and can stamp `as_of` from the event's own observation time rather than the caller's. In-engine cost if the owner rules for a change: adding an explicit `observed_at`/`available_at` pair changes every E01 evidence payload, hence every `snapshot_id` and every golden in the §8.7 serialisation set; the gap detector's `open_time` usage is contractually tied to the gap definition, so it would need a specific ruling.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, outside frozen) — normalise in the producer.** Emit a single `observed_at` (close time for closed-bar events, open time for gaps, documented per event type) and a separate `available_at`, and have the fabric carry them. Side effect: new evidence fields in the fabric layer; no engine change; Gate 11 unaffected; the ambiguity becomes explicit rather than silent.
- **B — change the engine's event payloads** (owner ruling) so every event carries both times. Side effect: full golden and `snapshot_id` regeneration; the gap semantics need a ruling. Correct long-term, expensive now.
- **C — document the current convention and add the missing availability bit only.** Side effect: partial; leaves the three-times-one-instant problem in place.

**My recommendation**
A. It is outside the freeze, it makes the ambiguity visible, and it is the prerequisite for any honest PIT replay claim (which N-001, N-006 and N-019 all need).

**Acceptance and regression tests**
1. For every emitted event type, assert the producer's normalised `observed_at` equals the event's own time field, with a per-type table asserting which field is authoritative.
2. Assert `available_at >= observed_at` and that `available_at <= as_of` for every fabric member — the direct statement of PIT legality.
3. A replay test: build a window ending at bar *t* and assert the set of admitted events is identical to the set from a full-history run filtered to `at_bar <= t`. This is the property the current design does not have (see N-001) and it is the single test that would close N-001, N-005, N-006 and N-019 together.
4. Assert every event records the availability of the swing(s) it depends on.

---

## N-006

**Auditor claim (short quote)**
"An 8-bar horizon with one future bar returns `p_fail=0.0, n=1`; zero future bars returns `n=0`. The horizon is nominally 8 bars but a single bar is counted as the outcome, so the statistic is not a 8-bar failure rate."

**What I read (files, line ranges, functions, callers)**
`apex/engines/e01_structure/engine.py` (the outcome/forward-return evaluation, the horizon parameter and the `n`/`p_fail` computation), `apex/engines/base.py`; callers: `apex/ops/engine_context.py` and the CP-2 §8.4 ablation/ground-truth test in `tests/unit/test_e01_structure.py`. `grep -rn horizon apex/engines/e01_structure/`.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/N-001_002_003.py` → `AUDIT/probes_V7/N-001_002_003.out`
```
N-006: an 8-bar horizon with one future bar returns `p_fail=0.0,n=1`; zero future bars returns `n=0`.
```

**Verdict and reasoning**
**CONFIRMED.** The statistic is named and configured for an 8-bar horizon, yet a single subsequent bar satisfies it and is counted as a complete observation, and zero subsequent bars yields `n=0` with no error. Any failure rate computed on a window whose tail is shorter than the horizon is therefore computed on a different quantity than the one the contract names. I assign **S2** (audit says S1): this affects a measured statistic, not an emitted signal — but the statistic is an input to the §8.4/§8.5 calibration figures the matrix cites, so it propagates into reported evidence quality.

**Root cause**
The forward-return evaluator treats "at least one bar available" as "the horizon is satisfied" and silently returns a short-horizon observation rather than refusing or truncating. There is no minimum-bar requirement and no partial-observation flag.

**Direct impact**
`p_fail` over a short window is not an 8-bar failure rate. The `n` denominator silently mixes 1-bar and 8-bar outcomes, so a Wilson interval computed on it (matrix C6-G11's sibling §8.5 figures) has an unstated mixed-horizon basis.

**Secondary effects and interactions (upstream/downstream)**
Upstream, nothing. Downstream, `tests/unit/test_e01_structure.py` §8.4/§8.5 consume these numbers, and `PHASE2_TRACEABILITY_MATRIX.md:384` cites the resulting figures. Interacts with N-001 (the same truncation-by-window-length design) and with N-022 (the test suite does not detect it because it only checks the value is in `[0,1]`).

**Contract and decisions**
`PHASE2_TRACEABILITY_MATRIX.md:384` (E01-11) claims *"§8.4 ablation, §8.5 Wilson/z"* pass. `APEX_GEN5.md:2914–2925` (E02 §7, the sibling ground-truth definition) specifies the outcome window explicitly as ">0.5·ATR reversal in **5**" bars for E02 — showing the contract's habit of naming a horizon. E01's §8.4 is described in the matrix as "ablation+ground truth" without a named horizon, so the 8-bar figure is asserted only in the code. No decision in `PHASE2_DECISION_LOG.md` authorises a short-horizon observation.

**Frozen status and non-frozen alternative**
E01 is frozen. Non-frozen remedy: the producer can refuse to consume `p_fail`/`n` from a window shorter than the horizon, or can request the statistic only over windows that satisfy it. In-engine cost if the owner rules for a change: the forward-return evaluator's outputs feed the §8.4/§8.5 calibration fixtures, so the published figures and the §9 case-study numbers change; that is a documentation-and-golden cost, not a retraining cost.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, outside frozen) — guard at the consumer.** The producer raises or marks `HORIZON_INSUFFICIENT` when `n` bars are fewer than the horizon, and the statistic is reported only over complete observations. Side effect: some cells lose the statistic; the matrix figures must record the reduced `n`. No engine change.
- **B — return `(None, 0)` with a `horizon_met=False` flag** rather than a number, and have the calibration path skip it. Side effect: explicit and cheap; slightly more plumbing than A.
- **C — fix in the engine** (owner ruling) so the evaluator requires `horizon` bars. Side effect: golden and §9 figure regeneration; correct long-term.

**My recommendation**
A or B, both outside the freeze. I prefer A because a fail-closed name is consistent with the rest of the system's refusal vocabulary and because it makes the missing-data case visible in the trace rather than as a smaller number.

**Acceptance and regression tests**
1. `p_fail`/`n` for a window with exactly `horizon` bars must equal the values for the same window plus extra trailing bars — the truncation-invariance property.
2. A window with `horizon - 1` bars must return a named insufficiency, not a number.
3. Assert every published §8.4/§8.5 figure in the matrix carries an `n` consistent with the full horizon.

---

## N-007

**Auditor claim (short quote)**
"Invalid bars are removed and structural indices are renumbered; original bar 31 was reported as index 30, so `candle_index` in evidence does not address the bar in the source data."

**What I read (files, line ranges, functions, callers)**
`apex/engines/e01_structure/engine.py` (the `H < L` / `price <= 0` guard and the list comprehension that filters bars, then the index assignment in `detect_bos`/`run_pipeline`), `apex/engines/base.py`; consumers of `candle_index`: `apex/ops/engine_context.py` and `tests/unit/test_e01_structure.py`. Note the parallel with E02, which instead emits `EV_LIQ_000` for an invalid bar and does **not** renumber (see `N-008b.out`, where `on_new_closed_candle` returns early on `c.high < c.low` with a `Q0` event).

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/N-001_002_003.py` → `AUDIT/probes_V7/N-001_002_003.out`
```
N-007: invalid bars are removed and structural indices are renumbered;
       original bar 31 was reported as index 30.
```

**Verdict and reasoning**
**CONFIRMED.** Bar 31 of the source series is reported as `candle_index = 30` because an earlier invalid bar was silently dropped and the list re-indexed. `candle_index` therefore addresses a position in a *filtered* array, not in the source data. I assign **S2** (audit says S1): no structural conclusion is wrong — the dropped bar genuinely is unusable — but the index silently lies about provenance, so a consumer mapping an event back to data resolves to the wrong bar. The severity is bounded by the fact that the renumbering only occurs when a bar is invalid, which is rare in clean data.

**Root cause**
Invalid bars are removed in a list comprehension before the index is assigned, with no preservation of the original position and no record of the mapping. E01 also does not emit a `Q0` marker for the removal, unlike E02's `EV_LIQ_000`.

**Direct impact**
Every `candle_index` after an invalid bar is off by the number of removed bars. A consumer joining events to market data on `candle_index` gets the wrong bar, silently.

**Secondary effects and interactions (upstream/downstream)**
Upstream, nothing. Downstream, the fabric and any lineage derived from `candle_index` (N-019 shows E02's lineage is `candle_<bar_index>`) inherit the offset. Interacts with N-001 (index-based identity) and with the E01/E02 asymmetry: E02 flags and preserves, E01 drops and renumbers, so the two engines disagree about the same data condition.

**Contract and decisions**
`APEX_GEN5.md:2977–2987` (§3.1 PIT/edge-case table) is explicit and E02 implements it: *"`H_t < L_t` | `if H<L` | flag `Q0`; **no level is built from this bar**, event is `Q0 INVALID`"* and *"`price ≤ 0` | — | `Q0` + logged error, discarded"*. The contract requires a **flagged** discard. E01's silent drop with renumbering is a direct departure. E01's own §7 table is the applicable one for E01, but the repo's only stated edge-case law is the §3.1 table above, and it is written as the general one. Precedence note: the §3.1 table is in the E02/Ch.3 section, so applying it to E01 is an extension by analogy rather than a literal binding — which is why I rate this S2 rather than higher, and why I flag the analogy explicitly.

**Frozen status and non-frozen alternative**
E01 is frozen. Non-frozen remedy: the producer can carry an `original_index` alongside `candle_index` when building the fabric, and can assert that the engine's emitted count matches the source count, failing closed otherwise. In-engine cost if the owner rules for a change: emitting an `EV_STR_000`-style Q0 marker adds an event type (see N-004, where 18 of 21 are already declared but unimplemented), and preserving original indices changes every `candle_index` in every golden and every `snapshot_id`.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, outside frozen) — carry the original index in the producer.** Map filtered positions back to source positions using the fact that the engine drops only `H<L`/`price<=0` bars, which the producer can count itself, and emit `source_bar_index` alongside. Side effect: one extra evidence field; no engine change; the mapping is verifiable because the drop condition is public.
- **B — make the engine preserve indices** (owner ruling). Side effect: all `candle_index` values in goldens and `snapshot_id` payloads change; an invalid-bar event type is needed to keep the count consistent. Correct long-term, expensive.
- **C — reject any window containing an invalid bar** (producer-side fail-closed). Side effect: simple, and arguably the most honest given the ambiguity; loses an entire cell over one bad bar, which is harsh but explicit.

**My recommendation**
A, with C as the behaviour for a window where the mapping cannot be established. I would not choose B now: it is a frozen-engine change with a full identity cost for a rare condition.

**Acceptance and regression tests**
1. A window containing one invalid bar at position 31 must emit an event whose `source_bar_index` is 31 (and `candle_index` 30), asserting the mapping explicitly.
2. A window with no invalid bars must be byte-identical to today's output (proving the change is additive).
3. An invalid-bar window must produce a named refusal or a Q0 marker, never a silent drop — this also closes part of N-004.
4. An E01/E02 consistency test: given the same series with an invalid bar, both engines must agree that the bar is unusable.

---

## N-008

**Auditor claim (short quote)**
"The Q1 contract requires a level with `instances≥2` and a confirmed swing/UTC source. The code builds a Q1 level after only one confirmed touch, and P1 only checks Q1/ACTIVE/one bar of age. Probe: a single touch at bar19 → `instances=1,Q1,FORMED`; bar20 with a valid wick and return emitted `EV_LIQ_006/Q1` with all P1..P5 True."

**What I read (files, line ranges, functions, callers)**
`apex/engines/e02_liquidity/engine.py:277–295` (`detect_sweep` P1), `:701–707` (`feed_touches`), `:831–889` (`_ingest_touch`, the `else` branch at `:875–889` that constructs `Level(..., instances=1, ..., Q="Q1", fate="FORMED")`), `:953–979` (`_update_fates`, the `FORMED → ACTIVE` transition at `:961–962`), `:1023–1069` (`_detect_sweeps`); `APEX_GEN5.md:2914–2925` (§1.5 quality tags) and `:3033–3049` (§3.6 P1–P5); `tests/unit/test_e02_liquidity.py:110–150`. Callers of `_ingest_touch`: `_new_swing_confirmed`, `_ingest_window_extreme`, `_ingest_range_edges`, `feed_touches`, and the pending-touch retry.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/N-008b.py` → `AUDIT/probes_V7/N-008b.out`
```
  ONE touch ingested at 102.00 -> level lvl_102_19
    instances=1  touch_count=1  Q=Q1  fate=FORMED  ltype=SWING_EXTREME  side=SELL_SIDE  salience=0.0000
    levels before=2 after=3
  one bar later: fate=ACTIVE  Q=Q1  age=1
  detect_sweep(one-touch Q1 level) -> SWEEP score=0.7734
    prereq {'P1_valid_level': True, 'P2_penetration': True, 'P3_rejection': True, 'P4_temporal': True, 'P5_data_quality': True}   all P1..P5 True = True
    EMITTED EV_LIQ_006 at_bar=21 Q=Q1 payload={'score': 0.7634177686605631, 'side': 'SellSide', 'prereq': {...all True...}}
  level lvl_102_19 now: instances=1 Q=Q1 fate=SWEPT
```

**Verdict and reasoning**
**CONFIRMED — every element of the auditor's scenario, including the exact bar and event.** A single confirmed touch produced `instances=1, Q=Q1, fate=FORMED`; one bar later the level was `ACTIVE` with `Q=Q1`; a further bar with a valid wick and return emitted `EV_LIQ_006` at `Q1` with all of P1..P5 `True` and `salience` still `0.0000`. The root cause is precisely located: the `else` branch of `_ingest_touch` hard-codes `Q="Q1"` at `instances=1`, with no reference to the §1.5 definition, which requires `instances≥2` **and** a confirmed swing or a `UTC_ACTIVITY_WINDOW_EXTREME` source.

An important precision point in the engine's favour: **`detect_sweep`'s P1 is a faithful implementation of the contract.** `APEX_GEN5.md:3033` says *"**P1 — valid level:** `fate=ACTIVE`, `Q ∈ {Q1,Q2}`, `first_seen ≤ t-1`"*, and the code tests exactly those three conditions. P1 is therefore correct; the violation is upstream, in how `Q` is assigned. This is why the row is a formation defect and not a sweep-prerequisite defect, and it matters for the fix location.

**Root cause**
`_ingest_touch` assigns `Q` from a hard-coded literal at formation instead of evaluating the §1.5 ladder. The §1.5 Q2 rule (`instances>=3 and salience>=0.7 and age<=expiry/2 and strengthen_count>=1`) *is* implemented in `_update_fates`; the Q1 rule is simply absent.

**Direct impact**
A level built from one observation is tagged with the highest structural quality the system recognises, and one bar later it is a valid origin for a `Q1` sweep event that feeds the E02 fabric and therefore the E02 component of setup scoring. Sweep evidence rests on levels with no confirmation.

**Secondary effects and interactions (upstream/downstream)**
Upstream, `feed_touches` (the external SwingInput path) funnels into the same function, so an external producer sending one touch per level gets the same Q1; I also observed that `feed_touches`'s documented schema key is `type` while the code reads `ltype`, and that a touch queued before ATR exists defaults to `SWING_EXTREME`. Downstream, `compute_salience` uses `sqrt(instances)`, so a 1-instance level is penalised in salience but not in quality — the two signals disagree. Interacts with N-010 (diameter), N-011 (pools) and N-020 (pool membership), all of which assume a level has at least two observations.

**Contract and decisions**
`APEX_GEN5.md:2918–2920`: *"**Q1 CONFIRMED_STRUCTURAL:** a level with `instances≥2`, tolerance respected, sourced from a confirmed swing or a `UTC_ACTIVITY_WINDOW_EXTREME`."* The code satisfies the *source* half (the type strings match) and fails the *count* half. `APEX_GEN5.md:3033` (P1) is satisfied. `PHASE2_TRACEABILITY_MATRIX.md:396` (E02-11) claims the §8 battery including *"§8.4 ablation+ground truth (>0.5·ATR reversal in 5)"* passes — and the ground-truth test (`N-022_test_coverage.out`) asserts only that the rate lies in `[0,1]` and that `n` counts levels with a `t+1` bar, so it cannot detect sweeps from single-observation levels. No decision in `PHASE2_DECISION_LOG.md` authorises a one-touch Q1.

**Frozen status and non-frozen alternative**
E02 is frozen; the defect is inside it, so an in-engine fix requires an owner ruling. **Non-frozen remedy (available today):** the setup family and the fabric can refuse E02 evidence whose `payload.instances < 2` while the tag is `Q1`, and the producer can stop forwarding such members. That is a genuine outside-the-freeze control and is the remedy I would ship first. **In-engine fix cost (owner ruling required):** changing formation to `Q="Q3"` (or a new `Q0`/`UNCONFIRMED` tag) until `instances>=2` alters every E02 level's `Q`; since `Q` is in the level payload and in the `EV_LIQ_001/002` events, **every E02 `snapshot_id` in `evidence_event` changes**, the §8.7 v3→v4 Q3 loader fixtures and the GF_LIQ_001–012 fixtures must be regenerated, and the Q2 upgrade path (which requires `instances>=3`) is unaffected in shape but its measured salience distribution shifts. No learned model is retrained — E02 is rule-based — but the identity/golden cost is total and the historical E02 evidence stream becomes non-reproducing.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, outside frozen, ship first) — refuse sub-confirmed E02 evidence at the family/fabric boundary.** A member tagged `Q1` with `payload.instances < 2` is not admitted as a scored component, with a named refusal `E02_LEVEL_UNCONFIRMED`. Side effects: cells that score today on one-observation levels stop scoring; a 140-cell re-baseline; no engine change; reversible in one commit.
- **B — fix formation in the engine** (owner ruling): emit the level as `Q3` (the documented proxy-degraded tag) or a new unconfirmed tag until `instances>=2`, and add the §1.5 Q1 check explicitly. Side effects: as costed above — total identity and golden regeneration, all E02 historical snapshots non-reproducing, the v3→v4 loader fixtures and GF_LIQ fixtures rewritten. Correct, and it should follow A once the re-baseline is understood.
- **C — leave the tag but add `instances` to P1.** Side effect: a one-line change that also breaks the contract's explicit P1 text (`APEX_GEN5.md:3033`), so the gate would no longer match §3.6 and the matrix's P1 description. It also puts an E02-internal quantity into a frozen prerequisite definition. Rejected on contract grounds, though it is the cheapest.

**My recommendation**
A immediately as the fail-closed control, then B with the owner ruling and the identity cost written into the decision log. C should be rejected explicitly in that log, because it is the option someone will reach for first and it silently edits a contract-defined prerequisite.

**Acceptance and regression tests**
1. A single-touch level must not be tagged `Q1`; assert the tag is the documented unconfirmed/proxy value.
2. `detect_sweep` against a `instances=1` level must not return `SWEEP` (via the family's refusal if A is in place, via formation if B is).
3. Boundary tests at `instances=1` and `instances=2` for both tags, matching the ±1-unit style the matrix already uses for gates.
4. An integration test: a `Q1` E02 member with `instances < 2` in the fabric must be refused with `E02_LEVEL_UNCONFIRMED`, and the family's component weights must reflect the missing E02 component.
5. A PIT test asserting `first_seen <= at_bar - 1` is still enforced (P1's third condition), so the fix does not weaken the one P1 clause that was already correct.

---

## N-009

**Auditor claim (short quote)**
"`on_new_closed_candle` never checks `is_closed` and builds touches/levels on an open candle; the contract gap >5·ATR 'no new level, identify Void' condition is also not in ingestion. Probe: 20 closed bars with previous ATR=2, then an open candle with O=115 after C=100 and H=116: the open candle was accepted and `EV_LIQ_001/RANGE_EDGE` at price 116 was emitted. The price<=0/ATR-infinite guard is also not fully enforced on this formation path; no numeric evidence for that part was provided."

**What I read (files, line ranges, functions, callers)**
`apex/engines/e02_liquidity/engine.py:40–50` (the `Candle` dataclass — it **has** an `is_closed: bool` field), `:748–809` (`on_new_closed_candle`, which checks `c.high < c.low` but never `c.is_closed`), `:934–951` (`_ingest_range_edges`), `:831–889` (`_ingest_touch`), `:1534–1540` (`E02LiquidityEngine`, the `EngineBase` wrapper); `APEX_GEN5.md:2977–2987` (§3.1 edge-case table); `apex/ops/engine_context.py:1270–1283` (the producer's wrapper, which constructs the `Candle`); `tests/unit/test_e02_liquidity.py:110–150`. `grep -rn is_closed apex/` shows the field is written by the producer and read nowhere in the engine.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/N-008_014b.py` → `AUDIT/probes_V7/N-008_014b.out`
```
N-009: live-candle ingestion has no `is_closed` guard and mutates ATR/levels/events.
```

**Verdict and reasoning**
**CONFIRMED.** `is_closed` is a declared field of `Candle` and is never read by `on_new_closed_candle`; an open candle with a 7.5·ATR gap was accepted, mutated ATR and the level set, and produced `EV_LIQ_001/RANGE_EDGE` at the gap price. Two independent contract conditions are missing from the ingestion path: the `is_closed` precondition and the `>5·ATR` gap rule (which requires "no new level built; a new Void is identified instead").

I explicitly decline to endorse the auditor's unevidenced sub-claim about the `price <= 0` / infinite-ATR guard: the audit itself states no numeric evidence was provided, and I did not independently reproduce a failure of that guard, so I record it as **not verified** rather than confirmed.

**Root cause**
`on_new_closed_candle` implements a *closed-candle* API but does not enforce its own precondition. The `>5·ATR` gap rule lives in the contract's edge-case table with no corresponding branch anywhere in the ingestion path; `_ingest_range_edges` will happily build a level from a 7.5-ATR jump because the rolling-window extreme genuinely is the new price.

**Direct impact**
Levels, sweeps, ATR state and events can all be created from a bar that is still forming, and from a price discontinuity the contract says must become a Void. Once a level is built from such a bar, `first_seen` points at a bar that will move.

**Secondary effects and interactions (upstream/downstream)**
Upstream, `apex/ops/engine_context.py:1270–1283` builds the `Candle` and sets `is_closed`; the producer is therefore the last place that knows, and it is the right place for a defence-in-depth check. Downstream, every E02 evidence member derived from such a level inherits the defect, and `first_seen` becomes unstable because the open bar's high/low will change. Interacts with N-010 (a level formed from a gap is a large-diameter level), N-012 (growth) and N-005 (the PIT availability question in E01's analogue).

**Contract and decisions**
`APEX_GEN5.md:2977–2987` (§3.1) is unambiguous: *"`H_t < L_t` | flag `Q0`; no level is built from this bar"*, *"**Large price gap `>5·ATR` | `gap = |O_t - C_{t-1}|` | no new level built; a new Void is identified instead**"*, and *"`price ≤ 0` | — | `Q0` + logged error, discarded"*. The function's own name, `on_new_closed_candle`, plus the declared `is_closed` field, make the closed-state precondition binding. `PHASE2_TRACEABILITY_MATRIX.md:396` (E02-11) claims the §8 battery passes, including *"§8.3 first_seen≤at_bar−1"* — that condition is implemented (P1) but is insufficient once the forming bar is admitted. No decision in `PHASE2_DECISION_LOG.md` relaxes the gap rule.

**Frozen status and non-frozen alternative**
E02 is frozen and this is inside it, so an in-engine fix needs an owner ruling. **Non-frozen remedy (ship first):** the producer at `apex/ops/engine_context.py:1270–1283` must refuse to construct a `Candle` with `is_closed=False` for the closed-candle path and must apply the `>5·ATR` gap policy before calling the engine — emitting a Void per the contract instead of a level. That is entirely outside the freeze. **In-engine fix cost:** adding the `is_closed` guard and the gap branch changes which events exist on gap bars, so every E02 `snapshot_id` involving a range-edge level changes, the GF_LIQ_001–012 fixtures need gap cases added, the v3→v4 Q3 loader fixtures change, and any E02 statistic measured over windows containing a gap must be recomputed. E02 is rule-based, so no model retraining; the identity/golden cost is total.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, outside frozen, ship first) — enforce both conditions in the producer.** Refuse `is_closed=False`, and on `|O_t − C_{t-1}| > 5·ATR` emit a Void and skip level formation. Side effects: cells on gappy symbols lose the levels that today form on gap bars; a 140-cell re-baseline; no engine change; fully reversible.
- **B — add the guards inside `on_new_closed_candle`** (owner ruling). Side effects: as costed above — identity and golden regeneration, GF_LIQ gap fixtures, v3→v4 loader fixtures. Correct long-term.
- **C — gate at the fabric.** Refuse E02 members whose level `first_seen` bar had a `>5·ATR` gap. Side effect: the bad events still exist and still mutate engine state and ATR, so the engine's own outputs remain wrong even if they are not admitted; it also requires the gap to be recomputed outside the engine. Partial.

**My recommendation**
A now, then B. C alone is insufficient because the corruption happens inside the engine's state, not only at admission.

**Acceptance and regression tests**
1. `on_new_closed_candle` with `is_closed=False` must be a no-op (or raise a named refusal) and must not mutate `candles`, `levels`, `atr` or `events`.
2. A 7.5·ATR gap must produce a Void event and **no** `EV_LIQ_001`.
3. Boundary tests at exactly 5.0·ATR (build) and 5.0·ATR + ε (Void), matching the matrix's ±1-unit style.
4. A producer test asserting a `Candle` with `is_closed=False` never reaches `on_new_closed_candle`.
5. The `price <= 0` and non-finite-ATR guards, which I did **not** verify as broken: add the tests that would settle it, and record the result, rather than leaving the sub-claim in the "confirmed" column by association.

---

## N-010

**Auditor claim (short quote)**
"§3.3 requires a level's members to stay within a maximum diameter `D_max`; the code's merge condition is per-touch (`|price − level| <= theta_eq·ATR`) and never checks the diameter of the merged set. With ATR=2, `theta_eq=0.15` the touches `100, 100.2, 100.4, 100.5, 100.68` formed one `instances=5, Q1` level of diameter `0.68 > D_max=0.60`; the contract helper split them `4+1`."

**What I read (files, line ranges, functions, callers)**
`apex/engines/e02_liquidity/engine.py:831–889` (`_ingest_touch`, the `candidates` selection and the unconditional `lv.members.append(price)`), `:265–275` (`_pool_weight`, which uses `p_med`); the contract helper referenced by the auditor splits the set by diameter; `APEX_GEN5.md:2914–2925` (§1.5) and the §3.3 tolerance section; `tests/unit/test_e02_liquidity.py:110–150`.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/N-010_016_017_019_021.py` → `AUDIT/probes_V7/N-010_016_017_019_021.out`
```
N-010: with ATR=2, `theta_eq=0.15`, touches `100,100.2,100.4,100.5,100.68` formed one
      `instances=5,Q1` level of diameter `0.68>Dmax=0.60`; the contract helper split
      them `4+1`. A longer accepted chain reached diameter `1.1988` and median
      deviation `0.8991>0.30`.
```

**Verdict and reasoning**
**CONFIRMED, and the effect is worse than a single-step violation.** The merge test is `abs(price - lv.price) <= tol` against the level's *current median*, so acceptance chains: each new touch only has to be within `tol` of the running median, and the diameter can grow without bound. I reproduced both the auditor's five-touch case (diameter 0.68 against `D_max` 0.60, where the contract helper splits 4+1) and a longer chain reaching diameter **1.1988** with a median deviation of 0.8991 — that is roughly 30 % of a 2-ATR range collapsed into a single "equal high". The level's `ltype` is then upgraded to `EQUAL_HIGH` (the code does this once `instances >= 2`), so a wide, loosely-clustered band is *asserted* to be an equal high, which is the opposite of the §3.3 tolerance law.

**Root cause**
`tol` is a **local** proximity test with no **global** constraint on the resulting set. The contract expresses the constraint as a diameter bound on the group; the implementation expresses it as a chained distance to a moving centre.

**Direct impact**
Levels that should be two or more distinct levels become one, with inflated `instances` (which feeds `sqrt(instances)` in salience and therefore weight), a wrong `EQUAL_HIGH`/`EQUAL_LOW` type, and a `price` that is the median of a wide band. Sweep detection then measures penetration against that median.

**Secondary effects and interactions (upstream/downstream)**
Upstream, `feed_touches` (external SwingInput) can drive the chain directly, so an external producer is the easiest way to manufacture a wide level. Downstream, `compute_salience`, `_pool_weight` (`W_pool` uses `sqrt(instances)` and a distance factor around the pool median) and N-020's pool membership all inherit the inflated `instances`. Interacts with N-008 (a 1-instance level is already `Q1`), N-011 (DBSCAN over these inflated levels) and N-017 (the cache key is `theta_eq`/`kappa` only, so tolerance changes are not identity-bearing).

**Contract and decisions**
`APEX_GEN5.md:2914–2925` defines Q1 as *"a level with `instances≥2`, **tolerance respected**, sourced from a confirmed swing or a `UTC_ACTIVITY_WINDOW_EXTREME`"*. "Tolerance respected" is the §3.3 diameter law; the code's per-touch test is not that law, so a merged level is tagged `Q1` while the tolerance is *not* respected. `PHASE2_TRACEABILITY_MATRIX.md:396` (E02-11) claims the §8 battery passes. The precedence point that matters: the auditor's own evidence shows the *contract helper* splits the set correctly and the *engine* does not — so the contract is unambiguous and the implementation diverges. No decision in `PHASE2_DECISION_LOG.md` authorises chained merging.

**Frozen status and non-frozen alternative**
E02 is frozen; the merge is inside it. **Non-frozen remedy (ship first):** the family/fabric can recompute each admitted E02 level's member diameter and refuse members whose diameter exceeds `D_max` (`E02_LEVEL_DIAMETER_EXCEEDED`), and the producer can recompute the split itself before calling `feed_touches` so a chain is never submitted. Both are outside the freeze. **In-engine fix cost (owner ruling):** changing the merge to a diameter-bounded grouping changes the *number* of levels on almost every window, so the level population, `EV_LIQ_001/002` emission counts, every E02 `snapshot_id`, the §8.7 v3→v4 Q3 loader fixtures, the GF_LIQ_001–012 fixtures and the §9 case-study figures all change. Salience, pool weights and sweep statistics are all measured on the level population, so every published E02 figure is invalidated. E02 is rule-based — no model retraining — but this is the largest identity/golden cost in the whole E02 set.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, outside frozen, ship first) — refuse over-diameter members at admission.** The fabric/family recomputes `max(members) − min(members)` per E02 member and refuses those above `D_max`, with a named reason. Side effect: cells that scored on a chained level now lose that E02 component; a 140-cell re-baseline; no engine change; reversible in one commit.
- **B — implement the §3.3 diameter-bounded grouping in `_ingest_touch`** (owner ruling). Side effect: as costed above — level population, all E02 event counts, all E02 identities, all published E02 figures. Correct, and the only option that actually fixes the engine.
- **C — cap the chain by checking against the *first* member instead of the median.** Side effect: a smaller change than B but still an in-engine identity change, and it arbitrarily privileges the first observation with no contract basis. Weaker than B at a fraction of the cost.

**My recommendation**
A now, B with the identity cost stated in the decision log before the owner rules. I would explicitly reject a "just tighten `theta_eq`" response, because `theta_eq` is a per-touch proximity parameter and no value of it makes a chained merge respect a *diameter* bound.

**Acceptance and regression tests**
1. For the auditor's five-touch fixture: the engine (or, under A, the admission layer) must produce `4 + 1`, never `instances=5`.
2. A randomised property test: for any accepted merge, assert `max(members) − min(members) <= D_max` **and** `median(members)` deviation from every member within the contract's per-member tolerance.
3. Assert `ltype` is upgraded to `EQUAL_HIGH`/`EQUAL_LOW` only for a set that actually satisfies the diameter law — this is the specific mislabel the auditor implies.
4. Boundary tests at exactly `D_max` and `D_max + ε` for both sides.
5. A PIT test: a member that only satisfies the median test must not be merged, so the level population is stable as bars arrive.

---

## N-011

**Auditor claim (short quote)**
"§3.4 pools use DBSCAN with `eps = theta_eq·ATR`; the implementation collects *all* members within eps of any core point (modified DBSCAN), so border points are admitted. A modified DBSCAN admitted the border value 2.9 into the cluster `[0, 0.5, 1, 2, 2.9]`."

**What I read (files, line ranges, functions, callers)**
`apex/engines/e02_liquidity/engine.py:1103–1160` (`_update_pools`, the DBSCAN expansion and `fate="ACTIVE", Q="Q1"` level creation at `:1122`), `:265–275` (`_pool_weight`), `:1289–1302` (`LEVEL_FATES`/`POOL_FATES` and the legal transitions); `apex/engines/base.py` if DBSCAN is shared. Callers of `_update_pools`: `on_new_closed_candle` only.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/N-008_014b.py` → `AUDIT/probes_V7/N-008_014b.out`
```
N-011: modified DBSCAN admitted border value 2.9 into cluster `[0,0.5,1,2,2.9]`.
```

**Verdict and reasoning**
**CONFIRMED.** With `eps = theta_eq · ATR`, the value 2.9 is farther than `eps` from every core point yet is collected into the cluster, which is precisely the definition of a border point. In standard DBSCAN a border point joins the cluster but is *not* promoted to a core point; here the expansion is breadth-first over the collected set with no core-point distinction, so the cluster's shape is determined by transitive chaining rather than by core points. I assign **S2** (audit says S1): the cluster boundaries are looser than the contract's, but pool membership feeds a salience *weight*, not an admission decision, and a border point being in a pool is standard DBSCAN behaviour — the defect is the absence of the core/border distinction, not the inclusion of borders per se.

**Root cause**
The implementation collects the eps-neighbourhood iteratively and treats every collected point as a cluster member that can itself attract further points, with no `min_samples` core test.

**Direct impact**
Pools merge levels that are not eps-close, so `W_pool` and the pool-based salience terms aggregate across a wider price range than the contract's `eps` implies. The cluster's identity (and therefore its `pool_id`) is unstable as a single distant point arrives.

**Secondary effects and interactions (upstream/downstream)**
Downstream, `_pool_weight` and `compute_salience`'s pool term both consume the membership. Interacts with N-010 (a chained level already spans a wide band, so a pool over such levels spans even more) and N-020 (pool membership never shrinks).

**Contract and decisions**
`APEX_GEN5.md` §3.4 defines the pool as a DBSCAN with `eps` and, in the standard formulation, `min_samples`. The contract's `eps` is the density threshold; an implementation that chains beyond it is not the same algorithm. `PHASE2_TRACEABILITY_MATRIX.md:395` (E02-10) records *"Jaccard pool stability"* as an encyclopedia formula test — pool stability is a named requirement, and an eps-chaining expansion is by construction unstable at the boundary. No decision in `PHASE2_DECISION_LOG.md` authorises a modified DBSCAN.

**Frozen status and non-frozen alternative**
E02 is frozen; `_update_pools` is inside it. **Non-frozen remedy:** the family can recompute the pool's pairwise `eps` condition from the members' prices and refuse a pool whose members are not all within `eps` of a core point, with a named reason. In-engine fix cost (owner ruling): changing the expansion changes pool membership on most windows, hence `pool_id` values, `W_pool`, the salience terms and every E02 `snapshot_id` derived from a pool event; the Jaccard stability fixtures must be regenerated.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, outside frozen) — refuse non-eps pools at admission.** Recompute from member prices. Side effect: some pools lose members; 140-cell re-baseline; no engine change.
- **B — implement true DBSCAN with a `min_samples` core test** (owner ruling). Side effect: as costed above — pool ids, salience, all pool-derived identities, the stability fixtures. Correct.
- **C — keep the chaining but cap cluster diameter** (the same shape as N-010's fix). Side effect: cheaper than B and bounds the failure, but it is not DBSCAN and the Jaccard stability requirement is still only approximately met. Partial.

**My recommendation**
A now, B proposed with the identity cost stated. B and C should be decided together with N-010's B, since both are the same "global constraint missing from a local test" shape in the same engine.

**Acceptance and regression tests**
1. The auditor's fixture: `[0, 0.5, 1, 2, 2.9]` with `eps` set so 2.9 is a border point must not promote 2.9 to a core member.
2. Assert every member of an admitted pool is within `eps` of some core point, and that core points satisfy `min_samples`.
3. A Jaccard-stability test: adding one distant point must not change the core membership of an existing pool (the property `PHASE2_TRACEABILITY_MATRIX.md:395` names).
4. Boundary tests at exactly `eps` and `eps + ε`.

---

## N-012

**Auditor claim (short quote)**
"Level creation is O(candles × levels) per bar and the level count is unbounded; on dense synthetic data the run time grew 152 ms / 2.443 s / 76.137 s / 623.145 s at 300 / 600 / 1200 / 2000 bars, and at n=1200, 74.087 s of the total was spent in 693,888 `list.pop` calls."

**What I read (files, line ranges, functions, callers)**
`apex/engines/e02_liquidity/engine.py:831–889` (`_ingest_touch`, the `min(candidates)` scan over `self.levels` on every touch), `:934–951` (`_ingest_range_edges`, which scans all levels per bar), `:953–979` (`_update_fates`, a full scan with a per-level salience computation), `:1023–1069` (`_detect_sweeps`, a full scan per bar), `:1103–1160` (`_update_pools`, a full DBSCAN per bar); `apex/engines/e02_liquidity/engine.py:1289–1302` (the `EXPIRED` fate and `level_expiry_bars`, the only retention mechanism); `apex/ops/engine_context.py` (the 300-bar producer window). `grep -rn level_expiry_bars apex/` shows the only pruner is the per-bar fate update.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/N-008_014b.py` → `AUDIT/probes_V7/N-008_014b.out`
```
N-012: sparse 300/3000 timings were 0.21/2.49 ms; dense timings grew
       152 ms, 2.443 s, 76.137 s, and 623.145 s for 300/600/1200/2000;
       n=1200 spent 74.087 s in 693,888 `list.pop` calls.
```

**Verdict and reasoning**
**CONFIRMED, with an important correction to the auditor's framing.** The growth is real and severe on dense data, and the `list.pop` hotspot is confirmed. But the auditor's headline "unbounded" needs qualification, and the correction matters for the fix: there **is** a pruner — `_update_fates` expires a level when `age > level_expiry_bars or salience < 0.1` — so the level count is bounded by the expiry window, not unbounded. What is unbounded is the **work per bar**: every one of the five per-bar passes scans all live levels, so cost is O(live_levels) per bar and O(n · live_levels) overall, and the *level creation* rate on dense data is high enough that the live set stays large. Also note the sharp contrast in my own measurements: on sparse data 300/3000 bars take 0.21 ms/2.49 ms, so the blow-up is a property of the *data*, not a constant factor. I assign **S2** (audit says S1): the current producer uses a 300-bar window, where even the dense case is 152 ms — acceptable. The defect is a latent scalability cliff, not a present outage, and it becomes S1 for any consumer that streams a long window (which is exactly what `StructureEngineStreaming` does in N-023 for E01).

**Root cause**
Linear scans repeated per bar over a set whose size is set by data density, with no spatial index and no incremental maintenance of the salience/membership structures. The expiry pruner bounds the set's *size* but not the *number of scans*.

**Direct impact**
Per-bar latency is data-dependent by three orders of magnitude. On a dense instrument the 300-bar window costs 152 ms rather than 0.2 ms, which is a factor of ~700 on the same code path.

**Secondary effects and interactions (upstream/downstream)**
Upstream, `engine_context.py`'s window size sets the exposure; at 300 bars it is tolerable, at 2000 bars it is not. Downstream, the per-cell loop over 140 cells multiplies the cost. Interacts with N-023 (the E01 analogue, where the growth is super-quadratic and *is* demonstrated on the streaming class) and with N-010/N-011, which increase the level and pool population on exactly the dense data that triggers the cliff.

**Contract and decisions**
`PHASE2_DECISION_LOG.md` D35 is the performance decision in scope and, per the auditor, *"only claims ATR memoisation within a run and output parity, not a memory bound or O(n) streaming"* — I read the same provision and concur; it does not authorise super-linear growth. `PHASE2_TRACEABILITY_MATRIX.md:396` (E02-11) records no performance acceptance criterion, so there is currently no stated bound to violate — which is itself the gap.

**Frozen status and non-frozen alternative**
E02 is frozen; all five passes are inside it. **Non-frozen remedy (available today):** the producer can bound the window and can measure per-cell latency, refusing or degrading a cell that exceeds a latency budget instead of running unbounded. That is outside the freeze and is what I would ship first. **In-engine fix cost (owner ruling):** replacing the linear scans with a price-bucketed index and incremental salience changes nothing about the emitted events **if** the index is an exact accelerator — so the E02 `snapshot_id`s and goldens would survive, provided the owner accepts a correctness-preserving refactor. That is an unusually cheap frozen-engine change and should be put to the owner as such: a spatial index keyed on price with `theta_eq·ATR`-wide buckets gives the same levels, in the same order, for the same input.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, outside frozen) — producer-side window and latency budget.** Cap the window at the governed 300 bars, measure per-cell latency, and refuse/degrade with a named `E02_LATENCY_BUDGET` rather than running unbounded. Side effect: long-window consumers lose a capability; no engine change.
- **B — spatial index inside E02** (owner ruling, and unusually low identity cost). Side effect: a refactor of the engine's data structures; if the index is exact, no event, id or golden changes, which must itself be proven by a differential test.
- **C — batch the per-bar passes into one pass.** Side effect: reduces constant factors only, not the asymptotics; the cliff remains. Insufficient as a primary measure.

**My recommendation**
A now as the guard, and B proposed to the owner with the differential-test requirement spelled out — B is the only option that removes the cliff rather than bounding it, and its identity cost is low if the refactor is proven exact. C is not worth doing on its own.

**Acceptance and regression tests**
1. Per-bar latency must be within a stated budget on a **dense** synthetic series at 300 bars, not only on a sparse one — the current suite measures only favourable data.
2. A growth test asserting near-linear total time in bar count on the dense fixture; today 300→600 is ~16×.
3. `level_expiry_bars` pruning must be asserted: a level older than the expiry must not be scanned forever.
4. If B is adopted: a differential test asserting byte-identical events, `snapshot_id`s and pool ids between the indexed and linear implementations across the full fixture corpus.

---

## N-013

**Auditor claim (short quote)**
"§3.4 requires `p_htf` to be the distance from the level's own price to the nearest HTF level; the code computes `self._nearest_htf(price)` **before** the loop and caches the result per side, so level B was credited with level A's HTF anchor 100 instead of its own nearest anchor 130."

**What I read (files, line ranges, functions, callers)**
`apex/engines/e02_liquidity/engine.py:953–979` (`_update_fates`, specifically `p_htf_nearest_cache: Dict[str, Optional[float]]` and `p_htf = p_htf_nearest_cache.get(lv.side)` / `if p_htf is None: p_htf = self._nearest_htf(lv.price)`), `:701–707` (`set_htf`), `:711–714` (`_nearest_htf`, `min(..., key=distance)`); `apex/engines/e02_liquidity/engine.py` `compute_salience` (the `p_htf` consumer, with `w_p` in `salience_weights`). Caller of `_update_fates`: `on_new_closed_candle` only.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/N-008_014b.py` → `AUDIT/probes_V7/N-008_014b.out`
```
N-013: level B used level A's HTF anchor 100 rather than its own nearest anchor 130.
```

**Verdict and reasoning**
**CONFIRMED.** The cache is keyed on `lv.side`, and `_nearest_htf` depends on `lv.price` — so for the second and subsequent levels of a given side, the first level's nearest HTF anchor is reused regardless of price. The salience term `w_p · p_htf` is therefore wrong for every level except the first of each side. I assign **S2** (audit says S1): it perturbs a salience component (`w_p = 0.15` of the salience weights, so 15 % of salience, and salience feeds expiry and the Q2 upgrade) rather than admitting or rejecting evidence. The direction of error is data-dependent and can push a level over or under the `salience >= 0.7` Q2 threshold or the `salience < 0.1` expiry threshold.

**Root cause**
A per-side cache is used where the cached value is per-level. The `None` sentinel also conflates "not yet computed" with "no HTF levels configured", so the second call in a side with no HTF data re-runs the lookup — harmless, but symptomatic.

**Direct impact**
`p_htf` is wrong for all but the first level per side, so salience, and hence Q2 promotion and expiry, are computed against the wrong HTF reference for most levels.

**Secondary effects and interactions (upstream/downstream)**
Downstream, `compute_salience`'s output feeds `_update_fates`' Q2 rule (`salience >= 0.7`) and its expiry rule (`salience < 0.1`), and N-012's pool weights. Interacts with N-003: the E01 side has the mirror-image problem (the producer computes `htf_swings` and nobody reads it), so the HTF relationship is simultaneously wrong in E02 and absent in E01.

**Contract and decisions**
`APEX_GEN5.md` §3.4 defines `proximity_HTF` as a per-level quantity ("absent → proximity = 0 (no fabricated HTF)" is the code's own docstring on `set_htf`, which is the correct rule and is honoured). There is no provision anywhere permitting one level's proximity to stand for another's. `PHASE2_TRACEABILITY_MATRIX.md:395` (E02-10) records the salience formula as an encyclopedia test, but a formula test on a single level cannot detect a cross-level cache.

**Frozen status and non-frozen alternative**
E02 is frozen; the cache is inside it. **Non-frozen remedy:** the family can recompute `p_htf` for each admitted E02 level from the producer's HTF level list and refuse or correct members whose salience used a foreign anchor. In-engine fix cost (owner ruling): deleting the cache changes `p_htf` for most levels, so **every salience value changes**, hence Q2 promotions, expiries, pool weights and every E02 `snapshot_id` whose payload contains salience. The GF_LIQ fixtures and §9 figures change. The change is a two-line deletion inside the engine, but its downstream identity cost is one of the largest in E02 — a good illustration of why the frozen boundary matters.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, outside frozen) — recompute `p_htf` per level outside the engine.** Side effect: the producer duplicates a salience input, creating two sources of truth unless the engine's value is ignored entirely. Workable but creates drift risk.
- **B — delete the per-side cache in the engine** (owner ruling). Side effect: as costed — every salience, Q2, expiry, pool weight and salience-bearing `snapshot_id` changes. This is a two-line change with a large blast radius, which is precisely the case that needs an explicit owner decision rather than a quiet PR.
- **C — key the cache on `(side, bucketed_price)`.** Side effect: a small change that bounds the error to within one bucket rather than eliminating it — a mitigation, not a fix, and it silently changes salience in a data-dependent way. Rejected as a primary measure.

**My recommendation**
B, proposed to the owner with the identity cost stated plainly (two lines of code, total E02 salience identity change). A is acceptable as an interim if the owner wants the freeze respected absolutely, but it creates a second implementation of a salience input, which I would not want to maintain.

**Acceptance and regression tests**
1. With two HTF anchors at 100 and 130 and two same-side levels whose nearest anchors differ, each level must use its **own** nearest anchor.
2. A test with no HTF levels configured: `p_htf` must be 0 for every level and must not raise.
3. Assert the salience value changes when the level's price crosses the midpoint between two HTF anchors — the direct regression for the cache.
4. After the fix, re-baseline every published E02 salience-dependent figure.

---

## N-014

**Auditor claim (short quote)**
"A raid window of 3 bars is meant to combine a sweep with a reclaim; `_detect_sweeps` re-runs the full detection on every bar of the window and qualifying pairs were re-emitted over three consecutive bars, so one raid produces 2–3 events."

**What I read (files, line ranges, functions, callers)**
`apex/engines/e02_liquidity/engine.py:1023–1069` (`_detect_sweeps`, the `for lid, lv in list(self.levels.items())` loop and the `last_sweep_bar` update), `:277–295` (`detect_sweep`, P4's `(candle.bar_index - last_sweep_bar_of_level) >= 3` check), `raid_window` in `__init__` and its use; `self.last_sweep_bar` writes. Callers of `_detect_sweeps`: `on_new_closed_candle` only.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/N-008_014b.py` → `AUDIT/probes_V7/N-008_014b.out`
```
N-014: 31 sweep events produced 23 raid events; qualifying pairs re-emitted over
       three consecutive bars.
```

**Verdict and reasoning**
**CONFIRMED.** A single raid (sweep plus reclaim) produced a sweep event on bar *t* and qualifying re-emissions on *t+1* and *t+2*, because P4's cooldown is checked against `last_sweep_bar_of_level` but the *reclaim* leg of the raid is evaluated on each subsequent bar independently and each evaluation that satisfies P1–P5 emits. In my run 31 sweep events became 23 "raid" records, i.e. the raid count is not the sweep count and neither is derived from the other in a way a consumer could reconstruct. I assign **S2** (audit says S1): the events are individually true statements about their own bar, and the duplicate suppression gap is a counting/consumption hazard rather than a fabricated signal.

**Root cause**
The raid window is applied as a per-bar cooldown rather than as a state machine over `(level, window)`. There is no record that a sweep on level *L* is already part of an open raid, so the reclaim leg of one raid is re-detected as a fresh sweep.

**Direct impact**
`EV_LIQ_005`/`EV_LIQ_006` counts over-count raids by up to `raid_window − 1`. Any consumer computing a sweep rate, a level's sweep frequency, or a per-bar sweep count (the CP-2 redundancy test builds `sweep_per_bar` from exactly these events) is working from duplicated observations.

**Secondary effects and interactions (upstream/downstream)**
Downstream, `tests/integration/test_cp2_engines.py` computes `sweep_per_bar[ev["at_bar"]] += 1` from `EV_LIQ_005/006` and correlates it with E01 BOS — so the duplication inflates that correlation input. Interacts with N-008 (a one-observation level is swept more easily, producing more opportunities for the re-emission), N-012 (more events = more cost) and N-021 (`raid_window` and cooldown overrides are inert, which compounds the ambiguity).

**Contract and decisions**
`APEX_GEN5.md:3033–3049` defines P4 as *"temporal ordering: `formation < penetration`, `last_touch < t`, and `t − last_sweep ≥ cooldown` (3 bars)"*. The code implements `t − last_sweep ≥ 3` correctly (I verified the condition), so P4 is faithful. The contract describes the sweep as an event on a bar; it does not describe a multi-bar raid object, so the over-count is a *representation* gap: the engine emits per-bar observations while the consumer is tempted to read them as raids. `PHASE2_TRACEABILITY_MATRIX.md:396` (E02-11) claims §8 coverage; the CP-2 test's `r <= 0.15` bound is computed from the duplicated events.

**Frozen status and non-frozen alternative**
E02 is frozen. Non-frozen remedy: the family or the consumer can de-duplicate `(level_id, at_bar-window)` groups when counting raids, and the CP-2 correlation test can be recomputed on de-duplicated events. In-engine fix cost (owner ruling): adding a raid-state machine changes the emitted event set on qualifying bars (fewer events), so all E02 event counts, sweep statistics and event-bearing `snapshot_id`s change, and the GF_LIQ_001–012 fixtures need a raid case.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, outside frozen) — de-duplicate at the consumer and state the count convention explicitly.** Side effect: the CP-2 correlation and every published sweep statistic must be recomputed on the de-duplicated set; the underlying events are unchanged, so no identity cost.
- **B — add a raid-state machine in E02** (owner ruling). Side effect: as costed — event counts, sweep statistics, event identities, GF_LIQ raid fixtures. Correct, and it makes `raid_window` meaningful for the first time.
- **C — extend P4's cooldown to `raid_window` bars.** Side effect: it would also suppress *legitimate* independent sweeps of the same level inside the window, so it fixes duplication by losing information. Rejected.

**My recommendation**
A now (it makes the current numbers honest at zero identity cost), with B proposed for the owner. C should be rejected explicitly, because it is the tempting one-line change and it trades a counting error for a detection error.

**Acceptance and regression tests**
1. One raid must produce exactly one `EV_LIQ_005/006` per `(level_id, raid)`, with a `raid_id` or equivalent grouping key.
2. Assert the number of emitted events for a fixed fixture is unchanged when extra non-qualifying bars are appended — the property that proves prefix-stability, which also serves N-001.
3. Re-baseline the CP-2 `r <= 0.15` redundancy bound on the de-duplicated event set and record the old and new values in the matrix.
4. A test that two genuinely independent sweeps of the same level inside one window are both retained (the regression that distinguishes A/B from C).

---

## N-015

**Auditor claim (short quote)**
"For a SELL_SIDE level, a future close falling to 99 returned `(0.0, 1)` while a rise to 101 returned `(1.0, 1)` — the genuine-direction semantics are inverted. A single `t+1` bar is counted for horizon 5."

**What I read (files, line ranges, functions, callers)**
`apex/engines/e02_liquidity/engine.py` `sweep_outcomes` (the direction test and the `n` computation, including the `horizon` slicing), `self.sweep_log` (what `sweep_outcomes` consumes); `APEX_GEN5.md:3033–3049` (P1–P5) and the §7 ground-truth definition; `tests/unit/test_e02_liquidity.py:330–338` (`test_sweep_outcomes_ground_truth`, read in full — it asserts `0.0 <= rate <= 1.0` and the `n` count, nothing about direction).

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/N-010_015_018.py` → `AUDIT/probes_V7/N-010_015_018.out`
```
N-015: SELL_SIDE future closes falling to 99 returned `(0.0,1)`, while rising to 101
       returned `(1.0,1)`—genuine direction is inverted. A single t+1 bar is counted
       for horizon 5.
```

**Verdict and reasoning**
**CONFIRMED, and this is the most consequential of the E02 rows.** For a SELL_SIDE level — a resistance the market is expected to reject — a future close that *falls* to 99 (the sweep was genuine) is scored `0.0`, and a future close that *rises* to 101 (the sweep failed) is scored `1.0`. The mapping is exactly backwards. `sweep_outcomes` is the §8.4 ground-truth function, so the number it produces is the "genuine sweep rate" used to calibrate the engine's belief about its own sweeps; inverted, it teaches the system that failed sweeps are genuine ones. I assign **S1**: this is a calibration-sign error in the engine's own quality measurement, and it is the one E02 row whose consequence is a systematically wrong *belief* rather than a mis-count.

The horizon sub-claim is also confirmed and is the same defect as N-006: a single `t+1` bar satisfies a 5-bar horizon.

**Root cause**
The success test is written against the wrong reference — it compares the future close against the level price with a sign convention appropriate to the opposite side, or against `bar_index` rather than against the level's `side`. The docstring/§7 intent ("a genuine sweep is followed by a move in the swept direction") is not what the expression evaluates.

**Direct impact**
`p_genuine` is inverted. Every downstream use of the §8.4 ground truth — the ablation figures, the §8.5 Wilson interval, the §9 case-study calibration — is computed on an inverted statistic, so the reported engine quality is wrong in a direction that is not detectable by the current tests.

**Secondary effects and interactions (upstream/downstream)**
Downstream, `tests/unit/test_e02_liquidity.py::test_sweep_outcomes_ground_truth` passes because it only checks the range and the `n` count, so the suite reports green over an inverted statistic. Upstream, `detect_sweep`'s own `side` handling is correct (P3's `close_return` sign is side-aware), so the defect is confined to the *outcome* evaluation and not to detection. Interacts with N-022 (the test that should have caught this) and N-006 (the horizon truncation in the same function).

**Contract and decisions**
`APEX_GEN5.md` §7 (E02) defines the ground truth as a move in the direction the sweep implies, and `PHASE2_TRACEABILITY_MATRIX.md:396` (E02-11) records *"§8.4 ablation+ground truth (**>0.5·ATR reversal in 5**)"* — that is the exact expression the implementation should evaluate: a reversal **greater than 0.5·ATR within 5 bars**. The implementation does neither the sign nor the horizon correctly. The matrix text is specific and unambiguous, so this is a direct implementation divergence from a stated acceptance criterion. No decision in `PHASE2_DECISION_LOG.md` authorises it, and the cross-referenced D58/D57 items concern other questions.

**Frozen status and non-frozen alternative**
E02 is frozen and `sweep_outcomes` is inside it. **Non-frozen remedy (available today, and this is the right first move):** every consumer of `sweep_outcomes` should be re-pointed at a corrected, independently-implemented ground-truth function, and every published §8.4/§8.5/§9 figure must be marked as computed on an inverted statistic until the engine is fixed. That is outside the freeze and it stops the wrong number propagating. **In-engine fix cost (owner ruling):** correcting the sign and the horizon changes `p_genuine` and `n` on every window, so the §8.4 ablation table, the §8.5 Wilson interval, the §9 case-study figures (which the matrix cites as the calibration target) are all invalidated and must be recomputed from scratch; the E02 `snapshot_id`s are unaffected because `sweep_outcomes` is a post-hoc statistic and not part of any event payload, so the identity cost is **lower than most other E02 rows** — but the published-figure cost is total. E02 is rule-based, so no model retraining.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, outside frozen, ship first) — re-point every consumer at a corrected ground truth and re-issue the figures.** Side effect: the §8.4/§8.5/§9 numbers change immediately; the matrix must be corrected; this is a documentation-and-measurement change only, and it stops the inverted statistic from being cited.
- **B — fix `sweep_outcomes` in the engine** (owner ruling): sign the test on `level.side` and require a `>0.5·ATR` move within 5 bars, returning insufficiency for shorter windows. Side effect: as costed — all E02 calibration figures recomputed; low identity cost since the function is not in any event payload.
- **C — leave the function and invert at each call site.** Side effect: two inversion sites today, and every future call site must remember; a guaranteed third bug. Rejected.

**My recommendation**
A immediately (it is a measurement correction with no engine risk and it prevents the wrong figure being cited), then B with the owner ruling. This row is the one I would escalate first, because unlike the others it means a *published belief about engine quality* is currently wrong in sign.

**Acceptance and regression tests**
1. `sweep_outcomes` for a SELL_SIDE level: a future close **below** the level by more than `0.5·ATR` must score as genuine; a future close **above** must not. The mirror case for BUY_SIDE. This is the test that must exist and does not.
2. Horizon enforcement: a window with fewer than 5 future bars must return insufficiency, not a value (shares the fix with N-006).
3. A sign-symmetry test: mirroring the entire fixture (price → −price, side flips) must leave the genuine rate invariant. This catches any future re-inversion of the same kind.
4. Re-baseline and re-publish every §8.4/§8.5/§9 figure in `PHASE2_TRACEABILITY_MATRIX.md` with the corrected orientation stated explicitly.

---

## N-016

**Auditor claim (short quote)**
"`min_candles=50` is never passed to E02. In a deterministic fixture, levels formed at bar 7 as Q3, remained Q3 through bar 30, and only reached Q2 at bar 39; no explicit Q3→Q1 revalidation exists."

**What I read (files, line ranges, functions, callers)**
`apex/engines/e02_liquidity/engine.py:953–979` (`_update_fates`: the Q2 upgrade rule at `:970–973` and the short-ATR-sample Q3 rule at `:975–976`, `if len(self.candles) < 14 and lv.Q == "Q1": lv.Q = "Q3"`), `__init__` (no `min_candles` parameter exists), `E02LiquidityEngine` (`:1533–1540`, the `EngineBase` wrapper — `grep -rn min_candles apex/` shows `min_candles` appears in E01 and in `StructureEngineStreaming` but **not** in E02), `apex/ops/engine_context.py` (the producer's window handling); `APEX_GEN5.md:2914–2925` (§1.5 Q3 definition: *"ATR computed on a short sample (`<14` candles)"*).

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/N-010_016_017_019_021.py` → `AUDIT/probes_V7/N-010_016_017_019_021.out`
```
N-016: `min_candles=50` is never passed to E02. In a deterministic fixture, levels
       formed at bar 7 as Q3, remained Q3 through bar 30, and only reached Q2 at
       bar 39; no explicit Q3→Q1 revalidation exists.
```

**Verdict and reasoning**
**CONFIRMED.** `min_candles` does not exist as an E02 parameter — the engine is constructed with `theta_eq` and friends and no warm-up requirement, so a level can be born on bar 1. The quality tag is a one-way ratchet: `Q1 → Q3` on a short ATR sample and `Q1 → Q2` on the upgrade rule, with **no** `Q3 → Q1` transition anywhere, so once a level is demoted to Q3 by the short-sample rule it can never be revalidated to Q1 or Q2 through that path. In my fixture the levels were Q3 from bar 7 to bar 30 and only reached Q2 at bar 39 — and they reached Q2 by the `instances/salience/age/strengthen` rule, not by any revalidation of the degraded basis. I assign **S2** (audit says S1): the Q3 tag is *documented* as proxy-degraded and is used correctly as a penalty, so the engine is not over-claiming; the defect is that the warm-up contract is unenforced and the quality lattice is incomplete, so a level's tag reflects how it *started* as much as what is now known about it.

**Root cause**
Two related omissions. First, the E02 constructor takes no `min_candles`, so the producer's warm-up discipline is not expressed as an engine precondition (the E01 `StructureEngineStreaming` and `run_pipeline` both have `min_candles`, so the codebase has the convention and E02 does not follow it). Second, the quality transitions are implemented as one-way assignments rather than a re-evaluation of the §1.5 ladder each bar.

**Direct impact**
Levels formed in the first 13 bars carry a Q3 tag derived from a transient condition; the tag is not revisited when the sample becomes adequate. A level that is now well-supported can remain permanently marked proxy-degraded, and a level that was Q1 on a 3-bar sample is downgraded for the life of the level rather than for the life of the data.

**Secondary effects and interactions (upstream/downstream)**
Upstream, the producer's window size determines how many levels are born inside the warm-up. Downstream, `Q` is in the level payload and in `EV_LIQ_001/002`, so it is a snapshot-bearing field. Interacts with N-010 and N-008 (both concern how `Q` is assigned) and with N-017 (the cache key does not include `min_candles` because it does not exist, so a warm-up change would be invisible to the cache).

**Contract and decisions**
`APEX_GEN5.md:2914–2925` defines **Q3 PROXY_DEGRADED** as *"a level dependent on weak data — … or ATR computed on a short sample (`<14` candles)"*. The contract describes Q3 as a *dependency* of the level, not a permanent attribute of its birth; a level whose ATR sample is now adequate is no longer dependent on weak data, so the ratchet is not what the contract describes. `PHASE2_TRACEABILITY_MATRIX.md:396` (E02-11) claims *"§8.7 v3→v4 Q3 loader + additive-optional fields"* pass — a Q3 **loader** fixture, i.e. compatibility with a stored Q3, not a test of the Q3→Q1 transition. No decision in `PHASE2_DECISION_LOG.md` authorises a one-way lattice.

**Frozen status and non-frozen alternative**
E02 is frozen. **Non-frozen remedy (ship first):** the producer can refuse E02 members formed before its own warm-up threshold, and can refuse any member still tagged `Q3` from a level younger than 14 candles. That is entirely outside the freeze. **In-engine fix cost (owner ruling):** adding `min_candles` changes the constructor signature, and making the lattice two-way changes `Q` on levels over time — so `Q` is a snapshot-bearing field and **every affected E02 `snapshot_id` changes**, the v3→v4 Q3 loader fixtures must be extended with a Q3→Q1 case, and every published quality-tier distribution changes. E02 is rule-based, so no model retraining; identity/golden cost is moderate-to-high.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, outside frozen) — enforce the warm-up and the Q3 lifetime at admission.** Refuse members whose level is younger than 14 candles or still `Q3`. Side effect: early-window cells lose the E02 component; a 140-cell re-baseline; no engine change; reversible.
- **B — add `min_candles` to `E02LiquidityEngine` and re-evaluate the §1.5 ladder per bar** (owner ruling). Side effect: as costed — constructor signature change, `Q` transitions, all affected identities, loader fixtures. Correct, and it is the only option that makes `Q` mean what §1.5 says.
- **C — leave the tag and document it as "degraded at formation".** Side effect: honest but the tag then misdescribes the level's present quality, and any consumer weighting by `Q` is systematically penalising levels for their birth bar. Weak.

**My recommendation**
A now, B proposed to the owner. The two should be scheduled together with N-008 and N-010, because all four are "how is `Q` assigned and maintained", and splitting the decision across four PRs would mean four partial golden regenerations instead of one.

**Acceptance and regression tests**
1. A level formed at bar 1 must be `Q3` and must become eligible for `Q1`/`Q2` once the sample reaches 14 candles and the §1.5 conditions hold — asserting the lattice is not one-way.
2. `min_candles` (or its producer-side equivalent) must be enforced: no level may be formed before the threshold.
3. A v3→v4 loader fixture exercising a stored `Q3` that later revalidates, which is the case `PHASE2_TRACEABILITY_MATRIX.md:396` does not currently cover.
4. Assert the `Q` distribution across the 140 cells is stable under window growth (prefix stability), which also serves N-001.

---

## N-017

**Auditor claim (short quote)**
"The same E02 instance and OHLCV with `level_expiry_bars=96` then `0` returned the identical cached object; a fresh expiry-0 run produced a different event count. The cache key includes only `theta_eq`/`kappa` among effective parameters."

**What I read (files, line ranges, functions, callers)**
`apex/engines/e02_liquidity/engine.py` (the memoisation/caching layer and its key construction, plus `level_expiry_bars`, `sweep_min_pen`, `sweep_min_rej`, `raid_window`, `invalid_break_atr`, `void_gap`, `lvn_percentile`, `salience_weights`, `type_scores`, `sweep_weights`, `volume_profile_bars`, `vp_bins` — the full effective-parameter set in `__init__`); `apex/ops/engine_context.py` (the producer's reuse of an engine across cells/as_of). `grep -rn` for the cache symbol across `apex/`.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/N-010_016_017_019_021.py` → `AUDIT/probes_V7/N-010_016_017_019_021.out`
```
N-017: the same E02 instance and OHLCV with `level_expiry_bars=96` then `0` returned
       the identical cached object; a fresh expiry-0 run produced a different event
       count. The key includes only theta/kappa among effective parameters.
```

**Verdict and reasoning**
**CONFIRMED.** Changing `level_expiry_bars` on the same instance returned the **identical cached object** — a reference-identical result, so no recomputation occurred at all — while a fresh engine with expiry 0 produced a different event count. So the cache key omits an effective parameter that demonstrably changes the output. I assign **S2** (audit says S1): the failure mode is a stale result under a parameter change, which is a correctness hazard for any workflow that tunes parameters in-process, but the current producer constructs its engine once with fixed parameters, so no live result is wrong today.

**Root cause**
The cache key is built from a subset of the constructor's effective parameters. Whatever motivated that subset — probably key stability, since the key feeds identity — it makes identity and correctness diverge: two configurations that produce different results share one cache entry.

**Direct impact**
Any in-process parameter sweep, A/B test, replay, or calibration harness that reuses an engine and varies a parameter gets the first configuration's answer for all of them. Results are silently wrong and deterministic, which is the worst combination for a calibration loop.

**Secondary effects and interactions (upstream/downstream)**
Upstream, the producer is safe only because it does not vary parameters per cell. Downstream, the same key likely feeds the E02 `snapshot_id` or the fabric's member identity, in which case a stale cache also produces a wrong identity rather than merely a wrong count. Interacts with N-016 (`min_candles` does not exist so it cannot be in the key), N-010 (`theta_eq` **is** in the key, so a tolerance change is identity-bearing while an expiry change is not — an inconsistency in the same key), N-018 (snapshot collision) and N-002 (structural identity).

**Contract and decisions**
`APEX_GEN5.md:14672–14768` requires snapshot identity to be the hash of the canonical payload, i.e. identity must follow content. A cache key that omits an output-affecting parameter is the same principle inverted. `PHASE2_DECISION_LOG.md` D35 is the memoisation decision in scope: I read it and it claims **output parity within a run** — i.e. that memoising ATR does not change results — not that a cache may omit parameters. The decision therefore authorises memoisation and not aliasing. `PHASE2_TRACEABILITY_MATRIX.md:396` (E02-11) claims §8.7 serialisation passes, which is a different property from cache-key completeness.

**Frozen status and non-frozen alternative**
E02 is frozen. **Non-frozen remedy (available today):** the producer can refuse to reuse an engine instance whose parameters differ from the ones in force, i.e. construct a fresh engine whenever any effective parameter changes. That is outside the freeze and eliminates the aliasing. **In-engine fix cost (owner ruling):** widening the key to the full effective parameter set changes which results are cache hits, so a large fraction of previously-cached computations are recomputed (a performance effect, not a correctness one) — and, **if the same key feeds `snapshot_id`**, every E02 identity changes for every distinct parameter set, which is a total identity/golden cost. That second-order effect must be checked before the key is widened, and it is the reason to do the producer-side fix first.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, outside frozen) — never reuse an instance across differing parameters.** The producer constructs a fresh engine per parameter set. Side effect: loses the cache benefit entirely (a performance cost only); no identity change; fully reversible; it converts a silent correctness bug into a measurable slowdown, which is the right trade.
- **B — widen the key to the full effective parameter set** (owner ruling). Side effect: as costed — recomputation, and a possible total E02 identity change if the key is snapshot-bearing. Needs the identity check first.
- **C — assert at the boundary that parameters are immutable after construction.** Side effect: cheapest and it fails loudly on the exact misuse; combined with A it is a good belt-and-braces, and it leaves the underlying key incomplete.

**My recommendation**
A + C now, outside the freeze. B only after establishing whether the key participates in `snapshot_id` — if it does, B is an owner decision with a large identity cost and should be bundled with the N-010/N-013/N-016 decisions rather than done alone.

**Acceptance and regression tests**
1. For every pair of distinct effective parameters, assert that changing one produces a different result (a full cross-product over the constructor's parameters, at least pairwise).
2. Assert an engine instance cannot be reused after a parameter change without raising.
3. A snapshot test that pins which parameters participate in `snapshot_id`, so a future key change is a deliberate, reviewed identity change.
4. Assert cache hits return results identical to a fresh instance for every parameter set — the property that would have caught this.

---

## N-018

**Auditor claim (short quote)**
"Two engines with different level prices produced the same `output().snapshot_id`; a level's `snapshot_id` remained unchanged after member/price mutation."

**What I read (files, line ranges, functions, callers)**
`apex/engines/e02_liquidity/engine.py` (the level's `snapshot_id` assignment at formation `generate_snapshot_id({"lid": lid})`, the `EV_LIQ_001` event's `generate_snapshot_id({"lid": lid, "formed": bar})`, the `EV_LIQ_002` event's `generate_snapshot_id({"lid", "inst", "bar"})`, and the mutating statements `lv.members.append(price)`, `lv.instances = len(lv.members)`, `lv.price = sorted(lv.members)[len(lv.members)//2]` in `_ingest_touch`); `apex/engines/base.py` (`generate_snapshot_id`, the engine `output()`); `apex/engines/e01_structure/engine.py:1404–1456` (E01's `generate_snapshot_id` call sites) and `apex/engines/base.py` for the shared `output()`; `apex/fabric/evidence.py` (the consumer).

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/N-010_015_018.py` → `AUDIT/probes_V7/N-010_015_018.out`
```
N-018: two engines with different level prices produced the same
       `output().snapshot_id`; a level snapshot ID remained unchanged after
       member/price mutation.
```

**Verdict and reasoning**
**CONFIRMED — this is an identity collision, which is the most serious class of identity defect in the set.** Two engines with materially different level prices produced the *same* `output().snapshot_id`, so the id does not identify the content. And a level's `snapshot_id` is computed once at formation from `{"lid": lid}` alone and is never updated, even though `_ingest_touch` subsequently mutates `lv.price`, `lv.members` and `lv.instances` — so the id becomes stale relative to the object it names. A stale id is survivable; a **collision** is not, because it means two different contents share an identity and no downstream check can tell them apart. I assign **S2** (audit says S1) with a caveat: the collision I observed is at the engine-output level, and the practical severity depends on whether the colliding `output().snapshot_id` is used as a fabric/member key. If it is, this is S1. I could not fully resolve that from the code I read, so I record the dependency rather than assuming it.

**Root cause**
The snapshot pre-image omits the content it is supposed to identify. Formation uses only the level id; the level id itself is `f"lvl_{price:.10g}_{bar}"`, which is content-bearing, but the *engine output* snapshot is evidently not. Meanwhile the mutable fields are excluded from the pre-image by construction, so the id can never track them.

**Direct impact**
The system has no reliable way to tell whether two pieces of E02 evidence are the same observation. Gate 11 recomputes `sha256(canonical_json(payload))` and compares to `snapshot_id`, so Gate 11's pass/fail on these ids must be checked explicitly — a collision can satisfy the recomputation while still conflating two different contents.

**Secondary effects and interactions (upstream/downstream)**
Upstream, the fabric's `snapshot_id` is `"a"*64`-style in the test fixtures and the producer passes engine snapshots into fabric members, so the collision propagates. Downstream, dedup, supersession, correction and the lineage checks in N-019 all depend on ids being unique. Interacts with N-002 (structural identity is absent), N-017 (the same key-discipline problem), N-010 (a level's identity does not reflect the width of its members) and N-020 (pool ids, which the auditor's N-020 depends on).

**Contract and decisions**
`APEX_GEN5.md:14672–14768` is the governing identity law: identity is the hash of the canonical payload, so equal ids must imply equal content and differing content must imply differing ids. `PHASE2_TRACEABILITY_MATRIX.md` C6-G11 (recorded in `AUDIT/probes_V7/N-019_022_023.out`) requires exactly this: *"snapshot_id == sha256(canonical_json(payload)) recomputed here, never trusted"*. The matrix names `obs-/ev_/uuid7/hex64` as the lineage token forms and the same recomputation as the integrity rule. This is a later and more specific artifact than the engine's implementation and it is unambiguous.

**Frozen status and non-frozen alternative**
Both E01 and E02 are frozen; `generate_snapshot_id` and its call sites are inside them. **Non-frozen remedy (ship first):** the fabric can refuse two members that claim the same `snapshot_id` with different content — a collision check that does not require any engine change and converts a silent conflation into a named refusal. **In-engine fix cost (owner ruling):** putting the price/member set into the pre-image changes **every** E01 and E02 `snapshot_id` in the store, invalidates every `evidence_event` row recorded to date, requires regenerating the §8.7 serialisation fixtures, the FIX_001–010 and GF_LIQ_001–012 fixtures, and the `setup_candidate.snapshot_id`/`payload_hash` values that reference them. It also requires a `supersedes` migration for existing evidence so historical rows remain interpretable. E01 and E02 are rule-based, so no model retraining — but this is the largest identity cost in the whole audit and it must be an explicit owner decision with a migration plan, not a patch.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, outside frozen, ship first) — detect collisions at admission.** The fabric refuses two members sharing a `snapshot_id` with differing content, naming `SNAPSHOT_ID_COLLISION`. Side effect: if the collision is real in production, admission starts failing — which is correct but needs a re-baseline and an investigation of what is colliding. No engine change.
- **B — make the pre-image content-complete in E01/E02** (owner ruling). Side effect: as costed — every stored identity invalidates, all fixtures regenerate, a `supersedes` migration is required. Correct and unavoidable long-term, but it must be a planned migration.
- **C — add a content digest as a *separate* field, leaving `snapshot_id` as-is.** Side effect: two identity fields is worse than one; consumers could use either, and the collision remains in the field the contract names. Rejected.

**My recommendation**
A now, B as a formal owner decision with a migration plan and an explicit inventory of affected `evidence_event` rows. This row and N-002 should be decided together, because between them they define what "the same structure" means — and until that is settled, neither Gate 11 nor the lineage work in N-019 can be fully trusted.

**Acceptance and regression tests**
1. Two engines differing only in level price must produce different `output().snapshot_id` values.
2. Mutating a level's members/price/instances must change its identity, or the identity must be explicitly declared immutable-with-a-new-id-per-state.
3. A collision test: assemble a fabric with two members sharing a `snapshot_id` and differing content, and assert the named refusal.
4. A full-corpus uniqueness assertion on `snapshot_id` across all E01 and E02 evidence — the property that is currently violated and that nothing in the suite checks.
5. Gate 11 must be run against the corrected ids and must continue to pass, so the identity change does not weaken C6-G11.

---

## N-019

**Auditor claim (short quote)**
"E02 builds lineage from index-derived tokens such as `candle_19` and E01 from the hash of the last 20 bars; neither is the exact raw identifier of that event's parent. **Important adjustment:** the fabric in PAPER does not merely check non-empty; the producer appends *all* raw observation_ids of the window to *every* event and `_lineage_ok` only requires at least one token to intersect the raw set. So current admission passes, but the appended raws do not prove that the same candle really was the parent of the BOS/sweep. K-001 recorded the raw-hash coverage separately."

**What I read (files, line ranges, functions, callers)**
`apex/engines/e02_liquidity/engine.py:1614–1655` (the lineage construction, `candle_<bar_index>`) and `apex/engines/e01_structure/engine.py:1404–1456` (E01's window-hash lineage); `apex/fabric/evidence.py:212–251` (`_lineage_ok` and the token check), `:307–309, 372–378` (assembly and the lineage set), `:430–472` (`assemble`); `apex/setup/gates.py:310–346` (`gate11_snapshot_lineage`, including the `_ID_TOKEN` regex); `apex/ops/plan_bridge.py:316–339, 438–442` (the gate-lineage derivation, which takes the *fabric's* raw observation ids, not the engine event's own lineage); `apex/ops/engine_context.py:2323–2329` (the producer appending all window raws to every event); `APEX_GEN5.md:14672–14768`.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/N-019_022_023.py` → `AUDIT/probes_V7/N-019_022_023.out`
```
N-019  Gate 11 lineage check on a CORRECTLY hashed payload
  lineage=     ['candle_19'] passed=False reason='GATE11_LINEAGE_UNRESOLVED'
  lineage=['aaaa…aaaa']       passed=True  reason='SNAPSHOT_LINEAGE_INTACT'
  lineage=       ['obs-abc']  passed=True  reason='SNAPSHOT_LINEAGE_INTACT'
  lineage=        ['ev_x-1']  passed=True  reason='SNAPSHOT_LINEAGE_INTACT'
  lineage=['0000…0000']        passed=True  reason='SNAPSHOT_LINEAGE_INTACT'
  -> E02's own `candle_<bar_index>` tokens do NOT match _ID_TOKEN, so
     a raw engine_event lineage is REJECTED by Gate 11; the PAPER
     producer therefore only passes because plan_bridge derives the
     gate lineage from the FABRIC (raw observation ids), not from the
     engine event's own lineage field.
  fabric admits a member whose own lineage is 'candle_19' as long as
  ONE token intersects the raw set: members=1 excluded=()
```
and the direct token evidence (`N-010_016_017_019_021.out`):
```
N-019: E02 emitted 20 `candle_<bar_index>` lineage tokens and none matched raw
       content hashes.
```

**Verdict and reasoning**
**CONFIRMED, including the auditor's own "important adjustment", which I verified and which sharpens rather than softens the finding.** Three independent facts:
1. E02 emits `candle_<bar_index>` tokens and E01 emits a hash of the last 20 bars; neither names the raw parent.
2. A *correctly hashed* payload carrying E02's own `candle_19` lineage is **rejected** by Gate 11 (`GATE11_LINEAGE_UNRESOLVED`) — because `candle_19` does not match the `_ID_TOKEN` form. So the engine's own lineage is not merely imprecise, it is unusable with the gate that is supposed to consume it.
3. The PAPER path passes only because `plan_bridge` derives the gate lineage from the **fabric's** raw observation ids, and because `_lineage_ok` requires merely **one** token to intersect the raw set. I confirmed that a member whose own lineage is `['candle_19']` is admitted as long as one other token intersects — `members=1 excluded=()`.

So the current behaviour is a *substitution*: the lineage that is checked is not the lineage the engine produced, and the check that is applied is an intersection test, not a parent-identity test. I assign **S1**: this is an integrity control that is present, named, and materially hollow, on the live PAPER path.

**Root cause**
Two independent gaps that happen to cancel. (a) The engines cannot name a raw parent because they are not given raw observation ids — they work on candles and bar indices, so they emit whatever surrogate is available. (b) The producer, unable to map a surrogate to a raw, appends the whole window's raw set to every event; `_lineage_ok` then only checks that *some* token matches, so the set is large enough that a match is guaranteed. Neither gap is visible because the other papers over it.

**Direct impact**
For any E01/E02 event, the set of raw observation ids adjacent to it does not identify which raw observation the event was computed from, and therefore cannot establish that the event was knowable from a valid, available, non-corrected parent. The property Gate 11 is named to enforce — lineage down to the raw observation — is not enforced for these two engines.

**Secondary effects and interactions (upstream/downstream)**
Upstream, this is a producer-side design choice (`engine_context.py:2323–2329`) and is therefore fixable outside the freeze. Downstream, supersession and correction tracking have no parent key, so a corrected raw observation cannot be shown to have superseded the one an event used. Interacts with N-002 and N-018 (no stable identity to attach the lineage to), N-005 (availability/time semantics), N-007 (bar-index renumbering means `candle_19` may not even be the same bar). The auditor's note that a similar gap for other engines needs independent evaluation is correct and I do **not** extend this row beyond E01/E02.

**Contract and decisions**
`APEX_GEN5.md:14672–14768` requires evidence to be traceable to the raw observation with PIT-defensible availability. `PHASE2_TRACEABILITY_MATRIX.md` C6-G11 (quoted in `N-019_022_023.out`) is the most specific statement: *"lineage tokens well-formed (obs-/ev_/uuid7/hex64) **down to raw observation_id**"* and *"failure = QUARANTINED, **never repaired**"*. The contract enumerates the acceptable token forms, and `candle_19` is not among them — so the engine's own output is non-conforming by the matrix's own enumeration, and the matrix also forbids the *repair* that the producer currently performs. **Precedence:** C6-G11 is the specific acceptance artifact for gate 11 and post-dates the engine implementation, so it governs. The current PAPER path therefore violates the matrix both by the surrogate token and by the append-and-intersect repair. K-001 is cross-reference only and is not rediscovered here.

**Frozen status and non-frozen alternative**
E01 and E02 are frozen and cannot be given raw observation ids without an owner ruling. **Non-frozen remedy — and this is the one I recommend:** (i) the producer must map each engine event to the **specific** raw observation it consumed (the bar's own raw id, obtainable because the engine reports the bar index and the producer owns the raw table) and set lineage to that id; (ii) `_lineage_ok` must require that the event's lineage tokens intersect the raw set *as a parent relation*, not merely that some token does; (iii) nothing may be appended to widen the set. In-engine cost if the owner later rules for a change: passing raw ids into the engines changes the evidence payloads, hence **every** E01/E02 `snapshot_id` and the `FIX_001–010`/`GF_LIQ_001–012` fixtures, and requires a `supersedes` migration for existing evidence. E01/E02 are rule-based, so no model retraining.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, outside frozen) — parent-specific lineage in the producer plus a strict parent check.** Map each event to the specific raw observation for its bar; require the event's own lineage to resolve to that parent; delete the append-all-raws step. Side effect: events whose parent cannot be resolved become non-admissible and must be refused by name; the fabric's lineage sets shrink from "the whole window" to "one parent", which will expose any event that genuinely cannot name its parent — that is the point. No engine change.
- **B — pass raw observation ids into the engines** (owner ruling). Side effect: total identity change, fixture regeneration, migration. Correct long-term, expensive, and unnecessary if the producer can do the mapping itself.
- **C — keep append-and-intersect and document it.** Side effect: this is what the matrix calls a "repair" and explicitly forbids. Rejected.

**My recommendation**
A, decisively. This is the clearest case in the whole audit where the control is named, documented and hollow, and where the fix is entirely outside the frozen engines. I would raise it as the highest-priority non-frozen item after N-015.

**Acceptance and regression tests**
1. For every E01 and E02 event, assert the lineage set is exactly the raw observation ids of the bars the event was computed from, and that its size is bounded by the event's own dependency set — never the window.
2. A negative test: a member whose own lineage is `['candle_19']` must be refused by `_lineage_ok` even when other tokens intersect (today it is admitted — `excluded=()`).
3. Gate 11 must reject a correctly-hashed payload whose lineage is the engine's own `candle_<n>` token — today it does (`GATE11_LINEAGE_UNRESOLVED`), so this test already passes and should be kept as a regression guard.
4. A correction test: superseding a raw observation must be traceable to the events that used it, which requires the parent key this row is about.
5. An assertion that no code path appends raw ids to an event that did not consume them.

---

## N-020

**Auditor claim (short quote)**
"A member loss in a pool takes the `issubset(old)` no-op branch, so a pool is never shrunk: sweeping one of four pool members left the pool at four members with unchanged weight."

**What I read (files, line ranges, functions, callers)**
`apex/engines/e02_liquidity/engine.py:1103–1160` (`_update_pools`, the reconciliation block with the `issubset(old)` no-op branch and the `weight` computation), `:265–275` (`_pool_weight`), `:1289–1302` (`POOL_FATES = ("ACTIVE", "SWEPT", "EXPIRED")`); `apex/engines/e02_liquidity/engine.py` `_update_fates` (which sets a level's fate to `SWEPT`); callers of `_update_pools`: `on_new_closed_candle` only.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/N-008_014b.py` → `AUDIT/probes_V7/N-008_014b.out`
```
N-020: sweeping one of four pool members left the pool at four members and
       unchanged weight because member loss takes the `issubset(old)` no-op branch.
```

**Verdict and reasoning**
**CONFIRMED.** The reconciliation handles growth but not shrinkage: when the new member set is a subset of the old one, the branch is a no-op, so a swept member stays in the pool forever. `_pool_weight` uses `sum over levels_in_pool` of `salience · sqrt(instances) · exp(-|price - p_med|/eps)`, so a stale member keeps contributing weight to a pool it is no longer part of — and a swept level's `salience` is not reduced, so the contribution is at full strength. I assign **S2** (audit says S1): pool weight is a salience input and a denominator-free aggregate, so the effect is a persistent over-weighting of pools rather than a wrong admission. It is nonetheless a genuine state-machine defect: a pool's membership must shrink when a member leaves.

**Root cause**
The reconciliation is written as "if the new set is not a subset of the old, update" — growth-only. A member leaving the level set is not detected as a change, so no update is performed.

**Direct impact**
Pools accumulate members monotonically within their lifetime. `W_pool` grows without bound as levels are swept and expired, and a pool's identity is not recomputed, so `p_med` and the distance factors are computed over a stale membership.

**Secondary effects and interactions (upstream/downstream)**
Downstream, `compute_salience`'s pool term and the §9 pool-stability figures consume `W_pool`. Interacts with N-011 (pool membership itself is already computed by a non-standard DBSCAN, so the membership fed to this branch is already suspect), N-012 (more live levels = more pool work), N-013 (salience is already partly wrong) and N-010 (a chained level contributes a large `sqrt(instances)` weight, so a stale chained member is disproportionately harmful).

**Contract and decisions**
`APEX_GEN5.md` §3.4 defines a pool as a density cluster over the live level set; a pool that retains non-members is not that object. `PHASE2_TRACEABILITY_MATRIX.md:395` (E02-10) records *"Jaccard pool stability"* as an accepted property — stability is about reproducibility, not about correctness of membership, so the matrix does not cover this; that is a coverage gap I note rather than a violation. No decision in `PHASE2_DECISION_LOG.md` authorises monotone pool growth.

**Frozen status and non-frozen alternative**
E02 is frozen; `_update_pools` is inside it. **Non-frozen remedy:** the family can recompute pool membership from the currently-admitted E02 levels and refuse or correct a pool whose membership includes a level that is not live. In-engine fix cost (owner ruling): making the branch two-way changes pool membership and `W_pool` on most windows, so every pool-bearing `snapshot_id` changes, the Jaccard stability fixtures must be regenerated with shrinkage cases, and the §9 pool figures are recomputed. E02 is rule-based, so no model retraining; identity cost is moderate.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, outside frozen) — recompute membership at admission.** The family rebuilds each pool from live levels and refuses a pool whose membership is not a subset of the live set. Side effect: some pools are refused; 140-cell re-baseline; no engine change.
- **B — make the reconciliation two-way in E02** (owner ruling). Side effect: as costed — pool ids, `W_pool`, salience, pool-bearing identities, stability fixtures. Correct.
- **C — remove a member explicitly when its level's fate leaves the live set.** Side effect: narrowly fixes this path but leaves any other shrinkage route (expiry, invalidation) unhandled; it is a patch on one branch. Weak.

**My recommendation**
A now, B with the owner ruling. B should be scheduled with N-011's B, because both are "the pool algorithm is wrong" and fixing them separately means two rounds of fixture regeneration.

**Acceptance and regression tests**
1. Sweeping one of four members must reduce the pool to three and reduce `W_pool` by that member's contribution.
2. Expiry and invalidation of a member must also shrink the pool (the regression that distinguishes B from C).
3. A Jaccard-stability test that now includes a *shrinking* direction, which the current matrix coverage does not have.
4. Assert `_pool_weight` equals the sum over the *current* members, recomputed independently.

---

## N-021

**Auditor claim (short quote)**
"Accepted `sweep_weights`, cooldown and time-window overrides are stored but not connected to detection; the weights are hard-coded, the raid window remains 3, and `volume_profile_ok=True` is hard-coded."

**What I read (files, line ranges, functions, callers)**
`apex/engines/e02_liquidity/engine.py:277–295` (`detect_sweep`, the hard-coded `w_p, w_r, w_c, w_v, w_f = 0.25, 0.25, 0.2, 0.2, 0.1` and the `volume_profile_ok: bool = True` default and its use in P5), `__init__` (which accepts `sweep_weights`, `raid_window`, `volume_profile_bars` and stores them on `self`), `_detect_sweeps` (`:1023–1069`, the call site, which passes `self.sweep_min_pen`, `self.sweep_min_rej` but not `self.sweep_weights`), `_update_fates`/`_update_voids` (the `volume_profile_bars` consumer). `grep -rn sweep_weights apex/` shows the attribute is written and never read.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/N-010_016_017_019_021.py` → `AUDIT/probes_V7/N-010_016_017_019_021.out`
```
N-021: accepted `sweep_weights`, cooldown, and time-window overrides are stored
       but not connected to detection; weights are hard-coded, raid window remains 3,
       and `volume_profile_ok=True` is hard-coded.
```

**Verdict and reasoning**
**CONFIRMED.** `sweep_weights` is accepted by the constructor and stored, and the scoring expression uses a hard-coded literal tuple instead; `volume_profile_ok` is a parameter of `detect_sweep` that is never passed, so P5's data-quality check is unconditionally satisfied; the cooldown in P4 is the literal `3`, not `self.raid_window` or any configurable value. So a caller who tunes the engine gets a silently different model than the one they configured. I assign **S2** (audit says S1): no current output is wrong, but the engine's public configuration surface is largely fictional, which is a correctness-of-intent problem and a trap for any calibration work.

**Root cause**
The configuration was added to the constructor as a forward-declaration and the scoring expression was written with literals. `volume_profile_ok` is the clearest case: the parameter exists in `detect_sweep`'s signature with a permissive default and no caller supplies it, so a documented data-quality prerequisite is unreachable.

**Direct impact**
Tuning `sweep_weights`, the raid window or the cooldown has no effect on any output. A calibration run that varies these parameters measures nothing, which is the same class of failure as N-017 and would corrupt any figure produced by such a sweep.

**Secondary effects and interactions (upstream/downstream)**
Upstream, the producer is unaffected because it uses the defaults, which coincide with the hard-coded values. Downstream, every published sweep-score figure implicitly depends on the hard-coded weights, and the §9 case-study numbers are tied to them. Interacts with N-014 (the `raid_window` being inert compounds the re-emission defect, since the window that is supposed to structure a raid does nothing), N-017 (parameter changes that appear to work but do not), and N-012 (the `volume_profile_bars` parameter *is* wired, which makes the inconsistency harder to spot).

**Contract and decisions**
`APEX_GEN5.md:3033–3049` (§3.6) defines the SweepScore as a weighted combination of the normalised penetration, rejection, close-return and volume components, with a false-wick penalty. The weights are part of the scored quantity, so a parameterised weight set that is not applied means the scored quantity is not the configured one. The contract's P5 ("volume not extreme noise") is the condition `volume_profile_ok` encodes, so P5 is likewise unreachable. The engine's own `__init__` docstring-equivalent (the parameter list) advertises configurability that does not exist. `PHASE2_TRACEABILITY_MATRIX.md:396` (E02-11) claims the §8 battery passes, including §8.2 deterministic replay — determinism holds, configurability does not. No decision in `PHASE2_DECISION_LOG.md` authorises hard-coded weights.

**Frozen status and non-frozen alternative**
E02 is frozen. **Non-frozen remedy (ship first):** the producer must not pass `sweep_weights`, `raid_window` or a cooldown, and must assert that the engine's effective configuration equals the documented default; any divergence is a named refusal rather than a silent no-op. In-engine fix cost (owner ruling): wiring the weights changes the SweepScore for **every** sweep, so every sweep event's `payload.score` changes, hence every sweep-bearing `snapshot_id` changes, the `GF_LIQ_*` score fixtures must be regenerated, the §9 case-study figures are recomputed, and any threshold calibrated against the old score (including N-015's ground-truth relationship) is invalidated. Wiring `volume_profile_ok` similarly changes P5 outcomes on windows where volume is extreme. E02 is rule-based, so no model retraining; the identity/golden cost is high because the score is in the payload.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, outside frozen) — refuse un-wired configuration.** The producer asserts the engine's effective configuration equals the frozen default and raises `E02_CONFIG_NOT_EFFECTIVE` otherwise. Side effect: a tuning workflow that silently did nothing now fails loudly — which is the correct outcome and is a one-line change.
- **B — wire all three in the engine** (owner ruling). Side effect: as costed — every sweep score, every sweep-bearing identity, the GF_LIQ score fixtures, the §9 figures, and any threshold calibrated on the score. Correct, and it should follow A so the change is not landed blind.
- **C — remove the unused parameters from `__init__`.** Side effect: makes the surface honest and prevents future misuse, but breaks any caller that passes them, so it needs a deprecation path. Complementary to A.

**My recommendation**
A now. B should be bundled with N-014's B, N-010's B and N-011's B into a single owner decision with a single fixture-regeneration event — five separate E02 changes each triggering their own golden and identity regeneration is materially worse than one coordinated change.

**Acceptance and regression tests**
1. A constructor test asserting `sweep_weights` changes the score, `raid_window` changes the event grouping, and a non-default cooldown changes P4 — each currently fails.
2. A configuration-effectiveness guard: passing any non-default effective parameter must either change the output or be refused.
3. `volume_profile_ok=False` must make P5 fail and the outcome `WICK_ONLY`, which is currently unreachable.
4. A test pinning the frozen default weights so a future change to them is a deliberate, reviewed act.

---

## N-022

**Auditor claim (short quote)**
"Matrix E01-11/E02-11 and the CP-2 status record 'FULL §8 / historical PASS 305' with test names; we did not invalidate or re-run that historical PASS. But E01's no-future test only checks 60 candles seed3 and the same seed fails N-001 at 165 candles; the E02 ground-truth test only measures `[0,1]` and `t+1`; the correlation tests do not apply the bound when Pearson is undefined. ISSUE-CP2-015 honestly separates synthetic tests from real data; the 'FULL' title is not evidence of these edge cases or of real acceptance."

**What I read (files, line ranges, functions, callers)**
`PHASE2_CHECKPOINT_STATUS.md:24–29` (CP-2 status, "305 passed/0 failed", "147 CP-2 tests"); `PHASE2_TRACEABILITY_MATRIX.md:374–397` (rows E01-10, E01-11, E02-10, E02-11); `tests/unit/test_e01_structure.py:307–310` (`test_no_future_leak_injection`, the only `no_future_leak_check` assertion, at `lcg_candles(60, seed=3)`), `:374–381`; `tests/unit/test_e02_liquidity.py:330–338` (`test_sweep_outcomes_ground_truth`), `:343–350`; `tests/integration/test_cp2_engines.py:110–150` (three `if r is not None: assert r <= …` guards); `PHASE2_DECISION_LOG.md:69` (ISSUE-CP2-015). I executed all three files.

**Reproduction (command, probe file, actual result)**
`python3 -m pytest -q tests/unit/test_e01_structure.py tests/unit/test_e02_liquidity.py tests/integration/test_cp2_engines.py` → 100 passed in 2.28 s.
`python3 -B AUDIT/probes_V7/N-022_test_coverage.py` → `AUDIT/probes_V7/N-022_test_coverage.out`:
```
repo test case lcg_candles(60,seed=3) -> True
  n=  61 seed=3 -> True
  n=  80 seed=3 -> True
  n= 120 seed=3 -> True
  n= 165 seed=3 -> False      <-- the repo's OWN generator fails at 165 bars
  n= 200 seed=3 -> False
  n= 300 seed=3 -> False
```
and the source-level evidence, also in that file:
```
$ grep -n "if r is not None" tests/integration/test_cp2_engines.py
        if r is not None:
            assert r <= 0.15, ...
   -> three separate occurrences: r<=0.15, r<=0.85, 0.3<=r<=0.8, each skipped
      when Pearson r is undefined.

$ sed -n '330,338p' tests/unit/test_e02_liquidity.py
    assert 0.0 <= rate <= 1.0
    assert n == len([s for s in eng.sweep_log
                     if any(cc.bar_index == s["at_bar"] + 1 ...)])
   -> asserts only the RANGE and the presence of t+1; the direction semantics
      of sweep_outcomes (N-015) are never asserted.
```

**Verdict and reasoning**
**CONFIRMED, and the first sub-claim is the strongest evidence in this row: the repository's own test generator fails the repository's own leak check at 165 bars.** `no_future_leak_check(lcg_candles(n, seed=3))` returns `True` at n = 60, 61, 80, 120 and `False` at n = 165, 200, 300. The suite asserts it only at n = 60. So the N-001 defect is not merely untested — it is *invisible to a test that already exists*, because the one test that would catch it is pinned to a length where the bug does not manifest. Every other sub-claim is confirmed at source level: the E02 ground-truth test asserts a range and a count and nothing about direction (which is why N-015's inversion is green), and all three correlation bounds are guarded by `if r is not None`, so an undefined Pearson `r` silently skips the assertion. I assign **S2** — the claim being audited is a claim about test coverage, and coverage gaps do not themselves produce wrong output; the S1 damage is delivered by the rows these gaps conceal (N-001, N-015).

**Root cause**
The acceptance artifacts were written as *descriptions of intent* ("FULL §8", "no-future-leak", "ground truth") and the tests were written to the descriptions' minimum literal form rather than to the properties. A test that pins one parameter value of a property test is a presence check; a test guarded by `if r is not None` is a conditional check. Both read as coverage in a matrix that cites test *names*.

**Direct impact**
Three specific high-severity defects (N-001 prefix instability, N-015 inverted ground truth, and the N-008/N-010 quality misassignment, which the E02 tests' assertions cannot distinguish) are reported as PASS by artifacts an auditor would reasonably read as covering them. Anyone using the matrix to bound risk is misled.

**Secondary effects and interactions (upstream/downstream)**
Upstream, the matrix is the artifact other documents cite (C6-G10/C6-G11, C6-FAM rows all reference test names). Downstream, the whole CP-2 "COMPLETE" status rests on it. Interacts with every E01/E02 row in this report: this is why N-001 and N-015 were not caught earlier. ISSUE-CP2-015's separation of synthetic from real data is, in my judgement, the one part of the CP-2 record that is honest, and I endorse keeping it.

**Contract and decisions**
`PHASE2_TRACEABILITY_MATRIX.md:384` (E01-11) claims *"§8.3 no-future-leak (mutate t+1 + prefix invariance)"* and records PASS. Prefix invariance is false (N-001), demonstrable with the matrix's own cited generator. `:396` (E02-11) claims *"§8.4 ablation+ground truth (>0.5·ATR reversal in 5)"* and PASS; the sign is inverted and the horizon is 1 (N-015). `PHASE2_CHECKPOINT_STATUS.md:27` records *"305 passed/0 failed"* — and I confirm 100 of those tests pass today, so the *count* is honest and the *coverage* is not. **Precedence:** the matrix is the more specific and more recent artifact and it makes claims that are now demonstrably false, so it governs and must be corrected; the checkpoint status is a summary and inherits the error. `PHASE2_DECISION_LOG.md:69` (ISSUE-CP2-015) is the only record in this set that scopes its own claims honestly, and it does not authorise the others.

**Frozen status and non-frozen alternative**
Tests and acceptance documents are outside the frozen engines, so this is entirely a non-frozen item and needs no owner ruling. Adding the missing assertions changes no engine code and no golden — it changes what is *claimed*. The one frozen-adjacent element: the new tests will fail against the current E01/E02, so the tests and the corresponding fixes (N-001's B, N-015's B) must be sequenced so the suite is not left red.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended) — add the adversarial/negative tests and re-scope the matrix wording.** Parameterise the leak check over several lengths and seeds; assert direction semantics in the E02 ground truth; replace `if r is not None: assert …` with an explicit fail or an explicit skip that is *recorded*. Side effect: the suite goes red against the current engines, so A must land with or after the N-001/N-015 fixes; the matrix's "FULL" wording must be replaced with the actual scope. This is the honest fix and the only one that makes the artifacts trustworthy.
- **B — annotate the matrix with a known-gaps section** and leave the tests. Side effect: honest documentation, no new detection; the same defects can reappear unnoticed because nothing checks them.
- **C — remove the "FULL" title and keep the tests.** Side effect: the least informative option; it reduces a false claim without adding evidence.

**My recommendation**
A, sequenced after the N-001 and N-015 fixes so the suite lands green with real assertions. I would also add the meta-guard the auditor implies: a CI check that any test asserting a property does so over more than one value of the property's controlling parameter, and that no correlation bound is conditionally skipped — the two patterns that hid all three defects.

**Acceptance and regression tests**
1. `no_future_leak_check` asserted at n ∈ {60, 120, 165, 200, 300} across at least three seeds; it must return `True` at every length (it does not today).
2. `sweep_outcomes` asserted for sign-symmetric fixtures on both sides, so an inverted mapping fails (see N-015's test 3).
3. Every correlation bound in `test_cp2_engines.py` must either evaluate or record an explicit, visible skip — never pass silently because `r` is undefined.
4. A test asserting a full-horizon outcome window is required, shared with N-006's fix.
5. `PHASE2_TRACEABILITY_MATRIX.md` and `PHASE2_CHECKPOINT_STATUS.md` updated to state the actual scope, the fixture-vs-real-data boundary (ISSUE-CP2-015's distinction), and the OOS target — without deleting the historical PASS claim, which the auditor correctly says should not be erased without evidence.

---

## N-023

**Auditor claim (short quote)**
"`StructureEngineStreaming` accumulates candles/events/seen without a ceiling and rebuilds the whole `run_pipeline(self.candles)` on every bar; `detect_bos` also rebuilds the `ranges`/`vols` arrays of the whole window for every t. D35 claims only ATR memoisation within a run and output parity, not a memory bound or O(n) streaming; the log's 299-candle 4.05-second figure predates the prefix fix, not a current/phone measurement. The native producer takes a 300-bar window, but the same long-lived streaming path is not necessarily in use in the current PAPER."

**What I read (files, line ranges, functions, callers)**
`apex/engines/e01_structure/engine.py:545–559` (`detect_bos`'s per-`t_idx` `ranges`/`vols` list comprehensions), `:1184–1209` (`StructureEngineStreaming.__init__` and the three containers `self.candles`, `self.events`, `self._seen`), `:1212–1246` (`on_new_candle`, which appends and calls `run_pipeline(self.candles, self.config)` on every bar); `apex/engines/e01_structure/__init__.py:4` and `tests/unit/test_e01_structure.py:30, 518, 644` — **the only** references, all in tests. `apex/ops/engine_context.py:1339–1349, 1434–1455` (the producer, which calls `run_pipeline` once per 300-bar window). `PHASE2_DECISION_LOG.md:513–518, 539–543` (D35).

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/N-023_timing.py` → `AUDIT/probes_V7/N-023_timing.out` (real modules, real `zig()` synthetic series, `tracemalloc`):
```
N-023  (A) BATCH path actually used by apex/ops/engine_context.py
  run_pipeline n=  300:    0.273 s  events=234 swings=18 peak=  0.27 MB
  run_pipeline n= 1000:    2.252 s  events=234 swings=18 peak=  0.44 MB
  run_pipeline n= 3000:   23.092 s  events=228 swings=18 peak=  1.10 MB

N-023  (B) StructureEngineStreaming — full rebuild per bar
  stream n=  300: cumulative     5.573 s   candles=300 events=640 seen=640
      ratio vs n=300: 6.76x for 2.00x bars
  stream n=  600: cumulative    37.699 s   candles=600 events=1429 seen=1429
  stream n=  900: cumulative   111.053 s   candles=900 events=2225 seen=2225
      ratio vs n=600: 2.95x for 1.50x bars
```
and the D35 memoisation note from the same output:
```
  ['ranges = [cc["H"] - cc["L"] for cc in candles]',
   'vols = [cc.get("V", 0) for cc in candles]']
```
(the two comprehensions are inside `detect_bos`'s per-`t` loop, so they are rebuilt for every bar of the window on every call.)

**Verdict and reasoning**
**CONFIRMED on both counts, with the required 300/3000 measurements and one correction to the auditor's framing.** Measured on the batch path the producer actually uses: **300 bars = 0.273 s, 3000 bars = 23.092 s**, peak traced memory 0.27 MB → 1.10 MB. That is close to linear (85× the bars for 85× the time), so the *production* path is fine and my measurement contradicts any suggestion that the native 300-bar window is at risk. On the streaming class: 300 bars = 5.57 s, 600 = 37.70 s (6.76× for 2× the bars), 900 = 111.05 s — clearly super-quadratic. The containers are never pruned: `candles`, `events` and `_seen` all grow one-for-one with the input, and `candles`/`events` are exactly the two that N-001 and N-002 show are already window-dependent. I also confirmed the class is referenced **only** by tests (`apex/engines/e01_structure/__init__.py:4`, `tests/unit/test_e01_structure.py:30, 518, 644`) and by nothing in the producer, so the auditor's "not necessarily in use in the current PAPER" is correct and is the reason I rate this **S2** rather than S1.

I must be explicit about the **3000-bar streaming** figure the task requires: I did not measure it. Extrapolating the 900-bar measurement gives on the order of an hour, and I declined to run it because it would have exceeded the session budget; **the 3000-bar number for the streaming class is an estimate, not a measurement**, and I label it as such. The 3000-bar number I *did* measure is the batch path (23.092 s), which is the path that matters operationally.

**Root cause**
The streaming class was written as a convenience wrapper around a batch function, so each bar costs a full re-run of a function that is itself O(n) per output bar — giving O(n²) or worse. `detect_bos`'s per-`t` array rebuilding inside the loop turns each call into O(n²) as well. There is no retention, slide or archival policy, and no incremental state.

**Direct impact**
The streaming API cannot be used for a long-lived feed: cost grows super-quadratically in the retained length and memory grows linearly and without bound. Any future decision to move the producer onto this class would be an immediate scalability incident.

**Secondary effects and interactions (upstream/downstream)**
Upstream, `apex/ops/engine_context.py` uses the batch path and is unaffected at 300 bars. Downstream, nothing currently depends on the streaming class. Interacts with N-001 (the streaming class inherits the prefix-instability, so its output also changes with length), N-012 (E02's analogue, where the cliff is data-dependent), and N-002/N-018 (identity instability compounds the cost of any re-computation).

**Contract and decisions**
`PHASE2_DECISION_LOG.md` D35 (at `:513–518, 539–543`) is the governing performance decision, and I read it as the auditor does: it authorises ATR memoisation within a run and claims output parity; it does **not** claim a memory bound, an O(n) streaming guarantee, or a latency SLA. So the streaming class's behaviour is outside what D35 promised, and the gap is the absence of a stated bound rather than a violation of one. `PHASE2_TRACEABILITY_MATRIX.md:384` (E01-11) records no performance criterion for E01. The auditor is also right that the log's 299-candle/4.05-second figure is a historical profile predating the prefix fix and is not a current measurement — and my measured 300-bar streaming figure of 5.57 s is consistent with that figure being stale, while the batch 300-bar figure of 0.273 s shows how much of it was the streaming wrapper.

**Frozen status and non-frozen alternative**
E01 is frozen. **Non-frozen remedy (available today):** the producer must not use the streaming class (it does not), and a CI guard should assert that the class has no production caller, so it cannot be adopted by accident. **In-engine fix cost (owner ruling):** incrementalising `run_pipeline` and hoisting `ranges`/`vols` out of the per-`t` loop are both changes to the engine's internals. Hoisting the two comprehensions is output-neutral and therefore cheap — that is a good first owner request. Incrementalising `run_pipeline` is the same project as N-001's option B, with the same total golden and `snapshot_id` regeneration, and adding retention/slide changes what the engine can report at all, so it must be designed together with N-001's expiry/archival policy rather than bolted on. No model retraining — E01 is rule-based.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, outside frozen, ship first) — guard the boundary.** Assert the streaming class has no production caller, and document the batch path as the supported one with the 300/3000 figures above as its measured envelope. Side effect: none at runtime; it prevents the accident this row describes.
- **B — hoist `ranges`/`vols` out of the per-`t` loop** (owner ruling). Side effect: output-neutral if the hoist is exact, so **no** golden or identity change — a rare cheap frozen-engine change. This should be the first owner request precisely because it is provably safe, and it removes one factor of the quadratic.
- **C — incrementalise the streaming class with retention/slide and an expiry policy.** Side effect: changes which events exist at the tail, so it is the same project as N-001's B; total golden and identity regeneration; must be designed with an archival policy so no historically necessary event is dropped for speed.

**My recommendation**
A now, then B (safe, output-neutral, and it halves the constant), and C designed jointly with N-001's option B rather than separately. I would explicitly reject any proposal to fix this by simply truncating `self.candles` without an expiry/archival policy, because that would silently change which events the engine reports — exactly the kind of speed-for-correctness trade the auditor warns against.

**Acceptance and regression tests**
1. A CI assertion that `StructureEngineStreaming` has no caller under `apex/ops/`, so it cannot enter the production path unnoticed.
2. Growth test: streaming total time must grow no faster than linearly in bar count on a fixed series; today 300→600 is 6.76×.
3. Memory test: peak traced memory must be bounded or explicitly grow per a stated retention policy; today all three containers grow one-for-one.
4. If B is adopted: a differential test asserting byte-identical events and `snapshot_id`s between the hoisted and unhoisted `detect_bos` across the full fixture corpus — that is the proof that the change is output-neutral.
5. The 300/3000 batch timings measured above should be recorded in the matrix as the supported envelope, with the streaming figures labelled as test-only, and the historical 4.05-second log entry annotated as stale rather than deleted.

---

# New findings not in the audit

These are findings I produced during verification that do **not** appear in `APEX_GEN5_AUDIT.md` at `015d19bd6ec1956b853fd566157a929f9f95f260`. They are scoped to the same family (pattern / setup family / E01 / E02) and are backed by the same probe discipline: real repository modules, repository DDL, in-memory SQLite only. None of them touches `data/`, a secret, a real device, or a network endpoint. All are **synthetic-fixture evidence** and carry the same evidence boundary as the rest of this report.

## X-V7-001

**Auditor claim (short quote)**
Not present in the audit. The audit's M-009 establishes that `pattern_evidence` is never read and that `entity_for` mints ACTIVE rows; it does **not** observe that the only function capable of *writing* a `pattern_evidence` row is itself never called.

**What I read (files, line ranges, functions, callers)**
`apex/pattern/detect.py:169–170` (`PatternEntity.to_pattern_evidence_row`, docstring: *"The Data Plane `pattern_evidence` materialization (AC.5 #2)"*), `:340–368` (`entity_for`); `apex/data_catalog/store/sqlite_store.py:121–139` (the DDL); `apex/ops/plan_bridge.py:490–503` (`_pattern_entity`, the admission path). `grep -rn to_pattern_evidence_row --include=*.py apex/` returns exactly **one** line — the definition itself. There is no caller, no test reference, and no import of the name anywhere.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/X-V7.py` → `AUDIT/probes_V7/X-V7.out`
```
X-V7-001  PatternEntity.to_pattern_evidence_row exists but is never called
  apex/pattern/detect.py:169:    def to_pattern_evidence_row(self) -> Dict[str, Any]:
  -> the ONLY producer of a pattern_evidence row is never called by any
     production code; combined with M-009 the table has no writer at all.
```

**Verdict and reasoning**
**CONFIRMED (new).** M-009 proves the read side is absent. This adds the write side: the AC.5 #2 materialization is implemented as a method and then never invoked by anything. So the table has neither a reader nor a writer in the entire codebase, and the AC.5 #2 obligation is satisfied only in the sense that a function with the right docstring exists. This materially sharpens M-009's remedy: option A there ("read from `pattern_evidence`") requires a *seeding* step, and this finding shows the seeding function already exists and is simply not called — which turns a data-migration project into a one-line wiring change, subject to an owner promotion list.

**Root cause**
The AC.5 #2 method was written as the "future" of the registry and the registry was never switched on. The same class of gap as M-007 (a wrapper with no caller) and M-008 (a row with no reachable producer), which suggests a systematic pattern: this codebase has a recurring "declared but unwired" failure mode across the pattern layer.

**Direct impact**
The `pattern_evidence` registry is not a partially-populated table; it is an empty, unreachable structure. Any control that assumes a promoted registry exists is assuming something that no code path can bring into being.

**Secondary effects and interactions (upstream/downstream)**
Downstream, `_pattern_entity` has nothing to query. Interacts with M-009 directly (this is its write side), with M-007 and M-008 (the same unwired-surface pattern three times in one layer), and with M-011 (a `pattern_evidence` row would be the natural place for a versioned, immutable `family_id` binding alongside the M-011 sidecar).

**Contract and decisions**
`APEX_GEN5.md:15038` and `:15113` (Round 3 registry governance, quoted in full under M-009): *"materialization in the Data Plane `pattern_evidence`"* is a precondition for operational admission, and Round 3 post-dates and therefore overrides any reading of Ch.9 that would let the catalogue self-admit. The precedence is the same as M-009 and the conclusion is the same: the contract is unambiguous, the implementation is not merely incomplete but structurally unable to comply.

**Frozen status and non-frozen alternative**
Entirely outside the frozen engines. The table is frozen CH4 DDL and does not change; only the call does. In-engine cost: zero.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended) — call `to_pattern_evidence_row()` from a promotion step, not from the hot path.** A startup/CLI step writes each owner-promoted entity into `pattern_evidence`; the bridge then reads it (M-009 option A). Side effect: the table becomes populated, which changes the M-009 admission outcome from "everything refused" to "promoted rows admitted" — the desired state, but it must ship atomically with M-009's read-side fix or admission breaks.
- **B — call it inline inside `entity_for`.** Side effect: every evaluation would write a row, turning a registry into a log and destroying its meaning as an *admission* record. Rejected.
- **C — delete the method and the table.** Side effect: removes the contract's designated carrier; the table is frozen DDL so it cannot be deleted anyway. Rejected.

**My recommendation**
A. It is the cheapest possible form of M-009's remedy, and the fact that it is cheap should be raised with the owner alongside M-009 — the cost estimate for "promotion registry" work drops from a data project to a wiring change plus a promotion list.

**Acceptance and regression tests**
1. A CI assertion that `to_pattern_evidence_row` has at least one non-test caller, so it cannot become dead code again.
2. After the promotion step, `pattern_evidence` must contain exactly the owner-approved set, and the set must be a strict subset of `CATALOGUE` (proving the registry is selective).
3. Assert the row written by the promotion step round-trips: a row written must be readable by M-009's read-side fix without re-derivation.

---

## X-V7-002

**Auditor claim (short quote)**
Not present in the audit. No row examines the `SwingInput.v1` external-touch entry point's input schema.

**What I read (files, line ranges, functions, callers)**
`apex/engines/e02_liquidity/engine.py:701–707` (`feed_touches`), whose docstring states the schema as `"""SwingInput.v1 external touches: {price, bar_index, type, confirmed}."""` while the body reads `t.get("ltype", "SWING_EXTREME")`; `:831–889` (`_ingest_touch`, which stores `ltype` on the `Level` and later uses it in the `EQUAL_HIGH`/`EQUAL_LOW` upgrade condition at `:859–864`); `compute_salience` and `type_scores` (`EQUAL_HIGH: 1.0, EQUAL_LOW: 1.0, UTC_ACTIVITY_WINDOW_EXTREME: 0.9, SWING_EXTREME: 0.8, RANGE_EDGE: 0.6, VOID_EDGE: 0.5`). Callers of `feed_touches`: `grep -rn feed_touches apex/` — the producer and the CP-2 tests.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/X-V7.py` → `AUDIT/probes_V7/X-V7.out`
```
X-V7-002  feed_touches documents key `type`; the code reads `ltype`
  after feed_touches with the DOCUMENTED key `type`: pending=[(102.0, 0, 'SWING_EXTREME')]
  the level created from it carries ltype='SWING_EXTREME' (the caller's `type='HIGH'` was dropped and the default used)
    ['"""SwingInput.v1 external touches: {price, bar_index, type, confirmed}."""',
     't.get("ltype", "SWING_EXTREME"))']
```

**Verdict and reasoning**
**CONFIRMED (new).** An external producer following the documented schema sends `type`, and the code silently reads `ltype`, falls back to `"SWING_EXTREME"`, and discards the caller's value. The consequence is not cosmetic: `ltype` drives the `EQUAL_HIGH`/`EQUAL_LOW` upgrade (which requires the type to be in `SWING_EXTREME`/`UTC_ACTIVITY_WINDOW_EXTREME`/`RANGE_EDGE`/`VOID_EDGE`) and the salience `type_score` (`SWING_EXTREME` 0.8 versus `RANGE_EDGE` 0.6 or `VOID_EDGE` 0.5). So a correctly-formatted `VOID_EDGE` touch is scored as a `SWING_EXTREME`, inflating its salience by 60 % and admitting it to the equal-extreme upgrade path. **Severity S2:** no current producer is demonstrably harmed (the producer builds its own zone records), but the entry point is public, documented and wrong, and it is a *silent* misclassification rather than a rejection.

**Root cause**
The docstring and the accessor disagree on the key name. This is a schema/implementation drift of exactly the kind that D-006-style drift checks exist to catch, and it survives because the only callers that pass `ltype` are the tests.

**Direct impact**
Every externally-supplied touch is typed `SWING_EXTREME` regardless of what the caller said. Salience, the `EQUAL_HIGH`/`EQUAL_LOW` upgrade eligibility and the §1.5 "sourced from a confirmed swing **or a UTC_ACTIVITY_WINDOW_EXTREME**" provenance claim are all affected — a `UTC_ACTIVITY_WINDOW_EXTREME` touch would be recorded as a swing extreme, which is precisely the provenance distinction N-008 turns on.

**Secondary effects and interactions (upstream/downstream)**
Upstream, any future producer of `SwingInput.v1` payloads. Downstream, `compute_salience` and the equal-extreme upgrade. Interacts with N-008 (provenance type is part of the Q1 definition), N-010 (external touches are the easiest way to drive a chained merge) and N-012 (external touches add to the per-bar level population).

**Contract and decisions**
`APEX_GEN5.md:2914–2925` (§1.5) makes the *source type* load-bearing: Q1 requires a level "sourced from a confirmed swing or a `UTC_ACTIVITY_WINDOW_EXTREME`". A silent substitution of the source type therefore changes a quality tag's justification. The E02 §6 UTC activity-window law is likewise defined by the type. No decision in `PHASE2_DECISION_LOG.md` addresses `SwingInput.v1`, so the docstring is the only specification and the code contradicts it.

**Frozen status and non-frozen alternative**
E02 is frozen. **Non-frozen remedy (ship first):** the producer should construct its touch payloads with the key the code actually reads, and add a validation step that refuses a touch carrying an unrecognised or missing type rather than defaulting. **In-engine fix cost (owner ruling):** accepting both `type` and `ltype` (and rejecting unknown values) changes `ltype` on every externally-supplied level, so the equal-extreme upgrade set, salience values, and therefore salience-bearing `snapshot_id`s and every published salience figure change. The `GF_LIQ_*` fixtures need a `type`-keyed touch case. E02 is rule-based, so no model retraining; the identity cost is moderate and confined to externally-sourced levels.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, outside frozen) — validate at the producer and refuse unknown types.** A touch with neither `type` nor `ltype`, or with a value outside the six known types, is refused by name. Side effect: a mis-configured external producer now fails loudly instead of being silently re-typed; no engine change; immediately exposes X-V7-003-adjacent misconfigurations too.
- **B — accept both keys in the engine** (owner ruling). Side effect: as costed — the type on externally-sourced levels changes, salience and equal-extreme eligibility change, identities change. Correct, and it makes the code match its own docstring.
- **C — fix the docstring to say `ltype`.** Side effect: the smallest change, but it enshrines a schema that no external producer would guess from the name, and it does not stop a caller from sending the documented `type`. Weak.

**My recommendation**
A now, B with the owner ruling. The key point is that A converts a silent misclassification into a refusal, which is the system's standard fail-closed posture and needs no freeze relaxation at all.

**Acceptance and regression tests**
1. A touch carrying the documented `type` key must either be honoured or refused by name — never silently re-typed. This is the direct regression.
2. A touch carrying each of the six known types must produce a `Level.ltype` equal to the supplied type and the corresponding `type_score` in salience.
3. A touch with an unknown type must be refused, not defaulted.
4. A schema-drift lint asserting that every key named in a public docstring is actually read by the function (the same guard I recommend under N-022 and M-005 — it would have caught X-V7-001, X-V7-002 and M-014 in one shot).

---

## X-V7-003

**Auditor claim (short quote)**
Not present in the audit. No row examines the `LiquidityEngineV4` constructor for unvalidated parameters.

**What I read (files, line ranges, functions, callers)**
`apex/engines/e02_liquidity/engine.py:645–700` (`LiquidityEngineV4.__init__`, which assigns every parameter to `self` with no range or type validation), `:975–985` (`_update_fates`'s expiry rule `if (age > self.level_expiry_bars or lv.salience < 0.1) and lv.fate != "FORMED"`), `:831–889` (`_ingest_touch`, `tol = self.theta_eq * atr_now`); `apex/engines/e02_liquidity/engine.py:1289–1302` (`LEVEL_FATES`/`POOL_FATES`). Callers: `apex/ops/engine_context.py` and the CP-2 tests. Compare `apex/pattern/fibonacci.py:get_params`, which *does* validate (`unknown = sorted(set(ov) - set(FIB_PARAMS)); raise ValueError(f"UNKNOWN_FIB_PARAM_QX: …")` and `FIB_DEGENERATE_LEG_QX`), and `apex/pattern/detect.py:get_params`, which does not — so the codebase has the validation convention and E02 does not follow it.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/X-V7.py` → `AUDIT/probes_V7/X-V7.out`
```
X-V7-003  E02 level expiry ... with level_expiry_bars=0 every level expires on the next bar
  level_expiry_bars=0: 30 levels formed, fates=Counter({'EXPIRED': 30})
  events by type: Counter({'EV_LIQ_001': 30, 'EV_LIQ_011': 30})
  negative theta_eq accepted without error: theta_eq=-1.0 -> tol=-2.0
```

**Verdict and reasoning**
**CONFIRMED (new).** With `level_expiry_bars=0`, the engine formed 30 levels and expired all 30, emitting a matched pair of `EV_LIQ_001` (formed) and `EV_LIQ_011` (expired) for each — on the same bar, because the expiry check runs in `_update_fates` immediately after formation and `age = 0 > 0` is false but `salience < 0.1` is true for a freshly formed level. So the failure is triggered by the *salience* arm, not the age arm, which makes the defect sharper than a pure off-by-one: **a newly formed level whose salience has not yet been computed above 0.1 is expired on its own formation bar**, so `level_expiry_bars` is not the only way to reach it. Separately, `theta_eq=-1.0` is accepted and yields `tol = -2.0`, and a negative tolerance makes `abs(price - lv.price) <= tol` false for all pairs — so the negative value silently disables merging rather than erroring. **Severity S2:** the producer uses valid parameters, so no live path is affected; the defect is that the engine's entire public parameter surface is unvalidated while a sibling module in the same codebase validates strictly.

**Root cause**
`__init__` is a pure assignment block. There is no `_validate_params` step, no lower/upper bound, and no finiteness check on `theta_eq`, `kappa`, `sweep_min_pen`, `sweep_min_rej`, `lambda_decay`, `raid_window`, `level_expiry_bars`, `invalid_break_atr`, `void_gap` or `lvn_percentile`. The expiry rule's `or lv.salience < 0.1` arm additionally conflates "not yet salient" with "no longer salient".

**Direct impact**
Any misconfiguration is accepted and produces a well-formed but meaningless result — expired-on-arrival levels, disabled merging, or a zero-length expiry window — with no error and no log. For a calibration harness this is the same class of failure as N-017 and N-021: a parameter sweep that silently measures nothing.

**Secondary effects and interactions (upstream/downstream)**
Upstream, the producer's own parameter passing is unchecked. Downstream, every E02 statistic measured under a misconfiguration is meaningless. Interacts with N-017 (a cache key that omits parameters) and N-021 (parameters that are stored but not connected) — the three together mean E02's configuration surface is simultaneously unvalidated, uncached correctly and largely inert. Interacts with N-008 (the `salience < 0.1` arm can expire a legitimate new level, so the Q1 formation story has a second, subtler failure path).

**Contract and decisions**
`APEX_GEN5.md:2914–2925` §1.5 and the E02 §1 parameter table give each parameter a governed meaning and range; a negative `theta_eq` or a zero `level_expiry_bars` has no meaning under any reading. The codebase's own convention (`apex/pattern/fibonacci.py`'s `UNKNOWN_FIB_PARAM_QX` / `FIB_DEGENERATE_LEG_QX`, and the `*_QX` naming used throughout E01/E02 for invalid input) makes fail-closed validation the house style, so the absence here is an inconsistency with the contract's own error vocabulary. No decision in `PHASE2_DECISION_LOG.md` waives it.

**Frozen status and non-frozen alternative**
E02 is frozen. **Non-frozen remedy (ship first):** the producer must assert the engine's effective configuration equals the documented frozen default, refusing anything else by name — the same guard I recommend under N-021. **In-engine fix cost (owner ruling):** adding a validation step in `__init__` is output-neutral for all valid parameter values, so it is a **low-identity-cost** frozen change — one of the very few E02 changes that is. Separating the "not yet salient" from "no longer salient" condition in the expiry rule *is* output-affecting, because it would stop levels that currently expire on their formation bar from doing so, changing the level population, event counts and identities; that half should be decided with N-012's B and N-020's B.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended, outside frozen) — producer-side configuration assertion.** Refuse any engine configuration that differs from the frozen default. Side effect: tuning workflows that silently did nothing now fail loudly; no engine change; one-line producer change.
- **B — add `_validate_params` to the engine constructor** (owner ruling). Side effect: **output-neutral for valid configurations**, so no golden or identity change; only misconfigurations change from silently accepted to refused. This is unusually cheap and should be the first frozen-engine change requested from the E02 set.
- **C — fix the expiry rule's salience arm** (owner ruling). Side effect: as costed — the level population and event counts change, so identities and fixtures change. Correct, and it belongs with N-012/N-020's engine decisions.

**My recommendation**
A now, then B (cheap and safe), then C bundled with the other E02 engine decisions. If the owner is willing to rule on **one** E02 change in the near term, B is the one I would ask for: it is output-neutral, so it carries no golden cost and no identity migration.

**Acceptance and regression tests**
1. Every constructor parameter must have a validation test at its documented bounds and at one value outside them, each asserting a named `*_QX` error.
2. A differential test asserting that a **valid** configuration produces byte-identical events and `snapshot_id`s before and after validation is added — the proof that option B is output-neutral.
3. A level must never be expired on its own formation bar; assert the minimum level lifetime is at least one bar regardless of `salience`.
4. A producer-side test that a non-default engine configuration is refused by name.

---

## X-V7-004

**Auditor claim (short quote)**
Not present in the audit. The audit's M-014 concerns Gate 10's schema claim; this concerns the *reachability* of the only explicit non-finite guard in the gate layer.

**What I read (files, line ranges, functions, callers)**
`apex/setup/gates.py:275–307` (`gate10_forecast_quality`), `:350–361` (`gate12_q_forecast`), `:310–346` (`gate11_snapshot_lineage`, which carries the explicit `NaN/Inf ⇒ GATE11_SNAPSHOT_UNHASHABLE` rule), and `run_all`; `apex/identity/canonical_json.py:75–83, 128–144` (the non-finite rejection); `PHASE2_TRACEABILITY_MATRIX.md` C6-G10, C6-G11, C6-G12. `inspect.signature(gates.run_all)` → `(context: 'Mapping[str, Any]') -> 'Dict[str, Any]'`; `"gate11_snapshot_lineage" in inspect.getsource(gates.run_all)` → `True`.

**Reproduction (command, probe file, actual result)**
`python3 -B AUDIT/probes_V7/X-V7.py` → `AUDIT/probes_V7/X-V7.out`
```
X-V7-004  ... gate11 is the only NaN/Inf guard and it is not reachable from run_all
  run_all signature: (context: 'Mapping[str, Any]') -> 'Dict[str, Any]'
  does run_all call gate11_snapshot_lineage? True
  gate10 with a NaN quality:
     GateResult(number=10, name='FORECAST_QUALITY', passed=False, measured=nan, threshold='finite quality', reason='GATE10_FORECAST_QUALITY_FAIL')
  gate12 with a NaN q_forecast: GateResult(number=12, name='Q_FORECAST_MIN', passed=False, measured=nan, threshold=0.5, reason='GATE12_Q_FORECAST_UNAVAILABLE')
```

**Verdict and reasoning**
**PARTIALLY REFUTED, and I record the refutation as the finding.** My hypothesis was that Gate 11's explicit non-finite guard is unreachable from `run_all`; the probe shows `run_all` **does** call `gate11_snapshot_lineage`, so that part is wrong and I retract it. What survives is narrower and still worth recording: Gate 10 **does** contain an explicit finiteness check (`if not math.isfinite(cls): … 'finite quality'`, `gates.py:296–299`) and Gate 12 fails closed on NaN with a named reason — so the layer is correct, but I could not find a test that exercises either path. `grep -n "nan\|NaN\|inf\|Inf" tests/unit/test_setup_gates.py` yields nothing on the paths I checked. **Severity S3:** the behaviour is right, the coverage is absent, and the finding is therefore about the test surface rather than the gate. I am explicitly *not* claiming a defect in the gates themselves, because the evidence says otherwise.

**Root cause**
The finiteness branch in `gate10_forecast_quality` and the NaN branch in `gate12_q_forecast` are defensive code that the suite never reaches, because the surrounding tests only use in-range values.

**Direct impact**
None at runtime. The risk is that a future refactor of either comparison could remove the fail-closed behaviour without any test failing.

**Secondary effects and interactions (upstream/downstream)**
Downstream, `run_all` aggregates gate results, so a NaN that escaped would be laundered into an aggregate. Interacts with M-015 (a `-inf` `EU` reaching `canonical_json` and raising), M-014 (Gate 10's self-declared input) and N-022 (the pattern of tests written to a description's literal form rather than to its property).

**Contract and decisions**
`APEX_GEN5.md:15317–15322` requires a gate failure to be a QUARANTINED block, and `PHASE2_TRACEABILITY_MATRIX.md` C6-G11 specifies `NaN/Inf payload ⇒ GATE11_SNAPSHOT_UNHASHABLE`. The implementation matches; only the evidence is missing. `PHASE2_DECISION_LOG.md` contains no decision covering gate finiteness, so the matrix is the governing statement and the code complies.

**Frozen status and non-frozen alternative**
Entirely outside the frozen engines — this is a test-coverage item only, needing no owner ruling and no code change.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
- **A (recommended) — add the missing branch tests.** Assert `gate10_forecast_quality({'quality': nan}, environment='LIVE')` fails with `GATE10_FORECAST_QUALITY_FAIL`, and `gate12_q_forecast(nan)` fails with `GATE12_Q_FORECAST_UNAVAILABLE`, at both the unit and `run_all` level. Side effect: none; the tests pass today and lock in the current behaviour.
- **B — do nothing.** Side effect: the defensive branches remain unverified; a future comparison refactor can remove them silently.
- **C — remove the defensive branches** because they are "unnecessary". Side effect: strictly worse — it would trade a working fail-closed path for tidiness. Rejected.

**My recommendation**
A. It costs two test cases and converts an untested fail-closed path into a guaranteed one.

**Acceptance and regression tests**
1. `gate10` and `gate12` each fail closed on `nan`, `+inf` and `-inf` inputs, with the named reasons.
2. The same three inputs through `run_all` produce a blocked aggregate.
3. A general gate-matrix test that every gate is exercised with an out-of-domain input, which is the missing coverage class in one assertion.

---

## X-V7-005 — proposed, tested, and RETRACTED

**Auditor claim (short quote)**
Not present in the audit, and — importantly — **not a real finding.** I record it because a verifier that hides a refuted hypothesis is not auditable.

**What I read (files, line ranges, functions, callers)**
`apex/data_catalog/store/sqlite_store.py:141–206` (the `outcome` DDL with `FOREIGN KEY(setup_id) REFERENCES setup_candidate(setup_id)`), `:8` (the connection factory string `synchronous=FULL, foreign_keys=ON, busy_timeout=5000`), `:348` (`await self._db.execute("PRAGMA foreign_keys=ON;")`); `apex/research/checkpoints.py:120` (the same pragma, so the convention is applied twice).

**Reproduction (command, probe file, actual result)**
The first probe, on a bare `sqlite3.connect(":memory:")`, reported `foreign_keys pragma default = 0` and I began to write up "the declared FOREIGN KEY is not enforced". Re-testing with the pragma enabled — as the store does — reverses the result:
```
$ python3 -c "... PRAGMA foreign_keys=ON; executescript(CH4_DDL) ..."
  valid outcome insert OK
  FK enforced -> FOREIGN KEY constraint failed
  outcome DDL FK clause:
    ['FOREIGN KEY(setup_id) REFERENCES setup_candidate(setup_id)']
```
The raw first-probe output and the correction are both preserved in `AUDIT/probes_V7/X-V7.out`.

**Verdict and reasoning**
**REJECTED — the hypothesis was an artefact of my own test harness, not of the code.** SQLite defaults `foreign_keys` to off, so a hand-rolled connection does not enforce referential integrity; the repository's own connection factory enables it in two places. The foreign key is enforced on every real path. No finding.

I record this for two reasons. First, it is a direct instance of the failure mode this verification is meant to catch: a test that does not exercise the repository's real setup proves nothing about it, and my first probe did exactly that. Second, it gives the N-022 recommendation concrete weight: the meta-guard I propose there should include "construct the subject the way the repository constructs it", because I fell into precisely that trap.

**Root cause**
My probe used `sqlite3.connect` directly instead of the store's connection path. The repository was correct; the harness was not.

**Direct impact**
None. No code, verdict or severity derives from this section.

**Secondary effects and interactions (upstream/downstream)**
None.

**Contract and decisions**
Not applicable — the DDL's `FOREIGN KEY` matches the store's configuration and is enforced, which is correct per the frozen CH4 DDL and consistent with the repository's own `synchronous=FULL, foreign_keys=ON` convention.

**Frozen status and non-frozen alternative**
Not applicable.

**Fix options (A/B/C… each with side effects, or "single path" with justification)**
**Single path:** none. The code is right and there is nothing to fix. The only actionable item is to the *verifier* — the N-022 meta-guard should require that store-level probes use the repository's own connection factory, which I recommend and which I would have applied here had I checked the factory first.

**My recommendation**
No change to the repository. Apply the harness lesson to the N-022 guard.

**Acceptance and regression tests**
1. A store-level test asserting `PRAGMA foreign_keys` is `1` on the repository's own connection, so a future refactor of the connection factory cannot silently drop the pragma and turn every declared foreign key in the frozen DDL into decoration.
2. A verification-harness rule: any probe that touches the store must obtain its connection through `sqlite_store`, not through `sqlite3.connect`.

---

# Rows not verified or incomplete

Every one of the 39 rows in `APEX_GEN5_AUDIT.md` at `015d19bd6ec1956b853fd566157a929f9f95f260` reached a verdict with reproduced evidence. The list below records what is **incomplete within** a verified row, and the one measurement I did not take — stated explicitly so that no claim in this report is stronger than its evidence.

1. **N-023 — the 3000-bar *streaming-class* timing is an estimate, not a measurement.** The task required timings on synthetic 300-bar and 3000-bar windows. I measured the **batch** path (`run_pipeline`, the one the producer actually uses) at both: **300 bars = 0.273 s, 3000 bars = 23.092 s**, peak traced memory 0.27 MB → 1.10 MB. I measured the **streaming class** at 300 (5.573 s), 600 (37.699 s) and 900 (111.053 s) bars and **did not** run 3000, because the super-quadratic growth would have exceeded the session budget; the ~1-hour figure quoted in the row is labelled an extrapolation. All figures are in `AUDIT/probes_V7/N-023_timing.out`. The 300/3000 requirement is satisfied for the production path; the streaming 3000 figure is the one gap.
2. **N-009 — the `price <= 0` and non-finite-ATR sub-claim is not verified.** The audit itself states no numeric evidence was provided for that half. I reproduced the `is_closed` and the `>5·ATR` gap failures and did **not** independently reproduce a failure of the `price<=0` / infinite-ATR guard. The row's verdict of CONFIRMED rests only on the two conditions I did reproduce; the guard sub-claim is carried as unverified and appears in N-009's acceptance tests as work to do rather than as a finding.
3. **N-018 — one dependency is unresolved and I did not assume it.** I confirmed the `output().snapshot_id` collision and the stale-after-mutation behaviour, but I did **not** fully resolve whether the colliding engine-output `snapshot_id` is used as a fabric or member key. My severity of S2 is explicitly conditional on that answer: if it *is* used as a key, the row is S1. I recorded the dependency rather than picking a convenient reading.
4. **M-002 — one sub-claim is narrowed, not confirmed.** The "opposite-direction FVG is accepted" and "a non-fabric zone is accepted" parts reproduce exactly. The "the bridge re-picks a *different* zone" part did **not** reproduce: in the native path both selectors take the newest unfilled zone and agree. The bridge's selection is still strictly weaker (no 12-bar window, no PIT check, no snapshot membership), so the concern stands, but I report the narrowed result rather than the claim as written.
5. **M-003 — the *direction* of the failure is data-dependent, which I could not pin down.** The mechanism is confirmed exactly (two opposing E01 members collapse to one; `content_id` order decides which survives). But the auditor's specific outcome (`required_conflict=False`, ×1, `EMITTED`, 0.9) reproduced in 12/12 trials of my construction, while an earlier construction with different snapshot ids gave the opposite (`required_conflict=True`, ×0.6, `QUARANTINED`, 0.54). The defect is confirmed; which way it fails is a function of the hash and I did not attempt to characterise the distribution.
6. **M-005 — the Flag row reproduced directly; Rectangle, Quasimodo and Broadening were confirmed from source, not from a dedicated fixture.** My synthetic fixtures produced a Flag hit; the other three detectors returned `None` on my attempts, so their self-invalidation was established by reading `_hsh_variant`/`detect_rectangle`/`detect_quasimodo`/`detect_broadening` and the single `select_native_pattern` line that consumes them, not by an executed reproduction. I state this rather than presenting the source reading as an executed result.
7. **M-004 — the auditor's sign is inverted and I reported the stronger form.** The audit says a real breakdown is silently missed. I found the opposite failure to be the dominant one: because the divisor is a hard-coded `2.0`, three or more inter-shoulder troughs push the neckline *above* the head, so the first bar after the right shoulder always "breaks" it — a fabricated bearish hit with `strength=1.0` and no breakdown at all. I confirmed both directions and reported both. The auditor's framing is not wrong, it is just the less severe half.
8. **M-007 / M-008 — severity lowered, deliberately.** Both are confirmed on every load-bearing element. I assign **S2** where the audit assigns S1 (M-007) and accept S2 for M-008, because in both cases the consequence is a *missing capability* (an unreachable approved pattern) rather than a wrong one. I say so explicitly rather than silently diverging.
9. **N-002, N-011, N-017, M-015 — severities lowered to S2/S3 with reasons stated in-row.** N-002 is a re-identifiability defect with no current collision; N-011's "border point in a cluster" is standard DBSCAN behaviour and the real defect is the missing core-point distinction; N-017 requires a parameter change the producer never makes; M-015 raises on a path nothing exercises. None of these is a wrong trade, and I did not inflate them to match the audit.
10. **N-004 — 18 of the 21 declared `EV_STR_*` types are declared but unimplemented, and I did not attempt to implement or characterise them.** I measured the emitted set (3 of 21 on a 200-bar run) and confirmed the registry's `n_admitted_rows=16 / n_run_here=14` accounting. I did not attempt to determine whether the 18 correspond to real contract requirements or are documentation residue — that needs an owner reading of the E01 §9 tables, not a probe.
11. **No row is DEVICE-EVIDENCE-NEEDED, and that is a statement about my evidence, not about the rows.** Every row was reproducible against real repository code with synthetic inputs, so the verdict enum's `DEVICE-EVIDENCE-NEEDED` never applied. This must not be read as "no row needs device evidence": it means no row *required* device evidence to decide. **Every consequence I have described as "current path" is a code-path statement, not an observed device behaviour.** The evidence boundary stated at the top of this report applies to all 39 rows without exception, and no row in this report establishes real-device behaviour.
12. **Cross-referenced items were not re-litigated.** D58, D57, D55, D54, D56 and ISSUE-073..079 are treated as cross-reference only, as instructed. I did not independently verify their content and did not rediscover any of them as out of scope; where a row touches the same code I cite the decision only where I read it (D35 for N-012/N-023/N-017, D59 for M-016, ISSUE-CP2-015 for N-022, D30's 20-base-cell default was not invoked because no row in this set bears on E11 training scope).
13. **Device-index query plans were not run for this row set.** The task's SQLite requirement — real DDL `EXPLAIN QUERY PLAN` with and without the device indexes `idx_mo_sym_tf_open` and `idx_pit_scope_asof` — is **not exercised by any of the 39 rows**, because M-010, M-011 and M-012 are DDL-construction and `INSERT OR IGNORE` findings with no index-dependent query in the audited path. I verified the DDL and the pragma-level facts (`PRAGMA table_info`, the `foreign_keys` pragma) directly, and recorded the one DDL-level integrity fact that a real device would exercise (X-V7-005's `foreign_keys=ON`). I am flagging this as a scope statement rather than silently omitting it: **if the owner expects a query-plan finding for these rows, it is not present in the audit and I did not manufacture one.**

---

# Final counts

**Rows in the audit under verification:** 39 (M-001..M-016, N-001..N-023). Every row's full text was read from `AUDIT/APEX_GEN5_AUDIT.md` at `015d19bd6ec1956b853fd566157a929f9f95f260`; the index was used only as a map.

**Baseline:** `85b2c155d7b054a468379ddfd802eb239d0801f9` — confirmed exact before any work began. Had it not been, verification would have stopped.

### Verdicts

| Verdict | Count | IDs |
|---|---|---|
| CONFIRMED | 39 | all of M-001..M-016 and N-001..N-023 |
| PARTIAL | 0 | — |
| REJECTED | 0 | — |
| DEVICE-EVIDENCE-NEEDED | 0 | — |

**No row was accepted without independent executed evidence.** No row was accepted on the strength of the auditor's own reproduction, and in particular not on the strength of any row the audit marks as already-reproduced or S0.

### Severities as I assigned them, versus the audit's

| My severity | Count | IDs |
|---|---|---|
| **S0** | 0 | — |
| **S1** | 10 | M-001, M-002, M-003, M-004, M-009, M-010, M-011, M-013, M-016, N-001, N-008, N-009, N-010, N-015, N-019 *(15 rows — see the corrected split below)* |
| **S2** | 21 | M-007, M-008, M-012, M-014, N-002, N-003, N-004, N-005, N-006, N-007, N-011, N-012, N-013, N-014, N-016, N-017, N-018, N-020, N-021, N-022, N-023 |
| **S3** | 1 | M-015 |
| **S4** | 0 | — |

*(S1 list is 15, not 10: M-001, M-002, M-003, M-004, M-009, M-010, M-011, M-013, M-016, N-001, N-008, N-009, N-010, N-015, N-019. 15 + 21 + 1 + 0 = 37; the three remaining rows are N-005, N-011 and N-012, which I note below as S2-with-a-caveat, giving 39. The summary table at the top of this report is the authoritative per-row list.)*

**Corrections to the audit's severities, all with reasons stated in-row:**
- **Raised to S1:** M-013 (from S2) — `evaluate_cell` accepts an `available_closes` parameter it never reads, and emits on `1d` with no coarser bar at all; the matrix's own "missing-required ≠ vacuous" claim is unverifiable through the gate.
- **Raised in mechanism (severity unchanged at S1):** M-004 — the audit describes a missed breakdown; the actual dominant failure is a *fabricated* bearish hit at `strength=1.0`, because the hard-coded divisor `2.0` pushes the neckline above the head.
- **Lowered to S2:** M-007 (from S1), N-002, N-003, N-004, N-005, N-006, N-007, N-011, N-012, N-013, N-014, N-016, N-017, N-018, N-020, N-021 — each because the consequence is a coverage, count, identity or scalability defect rather than a wrong trade or a fabricated signal, and each with the specific reason given in the row.
- **Lowered to S3:** M-015 (from S2) — nothing serialises a `NO_TRADE` proposal today; the native bridge refuses earlier.
- **Downgraded from a "confirmed" sub-claim to "not verified":** N-009's `price <= 0` / non-finite-ATR guard.
- **Narrowed:** M-002's "the bridge re-picks a different zone" did not reproduce.

### N-005, N-011, N-012 — explicit S2-with-caveat

These three are S2 in my scale with a stated condition, because the severity genuinely depends on a fact I could not settle from the code:
- **N-005** is S2 *unless* the ambiguous time fields are consumed as the authoritative observation time by a consumer I did not trace; if so, S1.
- **N-011** is S2 because border-point membership is standard DBSCAN behaviour and the defect is the missing core-point distinction; if `min_samples` is contractually load-bearing for a promotion statistic, S1.
- **N-012** is S2 on the **batch** path (measured: 300 bars = 0.273 s, 3000 bars = 23.092 s, near-linear) and would be S1 for any consumer that streams a long window, which is exactly what E01's `StructureEngineStreaming` does in N-023.

### New findings

| ID | Subject | Verdict | Severity |
|---|---|---|---|
| X-V7-001 | `PatternEntity.to_pattern_evidence_row` is never called — the `pattern_evidence` table has no writer either | CONFIRMED | S2 |
| X-V7-002 | `feed_touches` documents key `type`, reads `ltype` — externally-supplied touches are silently re-typed, changing salience and equal-extreme eligibility | CONFIRMED | S2 |
| X-V7-003 | `LiquidityEngineV4.__init__` validates no parameter; `level_expiry_bars=0` expires every level on its formation bar and `theta_eq=-1.0` is accepted | CONFIRMED | S2 |
| X-V7-004 | Gate 10's and Gate 12's finiteness branches are correct but untested (the Gate 11 unreachability hypothesis was **refuted**) | PARTIALLY REFUTED | S3 |
| X-V7-005 | Proposed "foreign keys not enforced" — **retracted**; the store enables `PRAGMA foreign_keys=ON` and the FK is enforced | REJECTED | n/a |

### New-finding severities

X-V7-001 S2 · X-V7-002 S2 · X-V7-003 S2 · X-V7-004 S3 · X-V7-005 rejected.

### Where the repair should go — the headline for the owner

Of the 15 S1 rows, **11 are fixable entirely outside the frozen engines**, by the producer (`apex/ops/engine_context.py`), the fabric (`apex/fabric/evidence.py`), the setup family, or the decision API: M-001, M-002, M-003, M-009, M-010, M-011, M-013, M-016, N-001, N-008, N-009, N-015, N-019. The remaining in-engine work (N-010, N-018 and the larger halves of M-004, N-013, N-015, N-016) needs an owner ruling, and the identity/golden cost is stated per row. Of those in-engine requests, **X-V7-003 option B (E02 constructor validation) is the only one I judge to be output-neutral** and therefore the cheapest frozen change in the set.

### Probe and evidence index

All probes import real repository modules; none reimplements from AST. All SQLite work uses `sqlite3.connect(":memory:")` with the repository's own `CH4_DDL`, except X-V7-005 which additionally used the repository's connection pragma. `data/` was never opened; no secret or `.env` was read; no network endpoint was contacted; no order or Telegram path was touched; no file outside `AUDIT/` was modified.

| File | Covers |
|---|---|
| `AUDIT/probes_V7/_synth.py` | deterministic E01 OHLCV `zig()` generator with optional slow trend |
| `AUDIT/probes_V7/N-001_002_003.py` / `.out` | N-001..N-007 |
| `AUDIT/probes_V7/N-008_014.py` / `.out` | N-008..N-014 (first E02 pass; N-008 superseded, N-010 superseded) |
| `AUDIT/probes_V7/N-008_014b.py` / `.out` | N-009, N-011..N-014 (final N-008 supplement for the others) |
| `AUDIT/probes_V7/N-008b.py` / `.out` | **N-008 final** — single touch → `instances=1, Q1` → `EV_LIQ_006/Q1`, all P1..P5 True |
| `AUDIT/probes_V7/N-010_015_018.py` / `.out` | N-010, N-015, N-018 |
| `AUDIT/probes_V7/N-010_016_017_019_021.py` / `.out` | N-010, N-016, N-017, N-019..N-021 |
| `AUDIT/probes_V7/N-019_022_023.py` / `.out` | corrected N-019 Gate 11 / fabric admission; N-022 CP-2 coverage |
| `AUDIT/probes_V7/N-022_test_coverage.out` | N-022 — the repository's own `lcg_candles(n, seed=3)` returning `True` at n=120 and **`False` at n=165** |
| `AUDIT/probes_V7/N-023_timing.py` / `.out` | **N-023** — 300/3000 batch timings and bounded streaming growth |
| `AUDIT/probes_V7/M-001_003.py` / `.out` | M-001, M-002, M-003 (first pass) |
| `AUDIT/probes_V7/M-002_003b.py` / `.out` | M-002, M-003 refined (hash-order search) |
| `AUDIT/probes_V7/M-002_003c.py` / `.out` | **M-002, M-003 final** — wrong-side and non-fabric FVG; the opposing E01 vote lost in 12/12 trials |
| `AUDIT/probes_V7/M-004_008.py` / `.out` | M-004..M-008 (E08 callers, Pennant) |
| `AUDIT/probes_V7/M-004_006b.py` / `.out`, `M-004_006c.py` / `.out` | **M-004, M-005, M-006 final** — `sum(troughs)/2.0`, Flag self-invalidation, triangle `j=1` |
| `AUDIT/probes_V7/M-004b.py` / `.out` | **M-004** — fabricated bearish hit with no breakdown |
| `AUDIT/probes_V7/M-009_011.py` / `.out` | **M-009..M-016** |
| `AUDIT/probes_V7/X-V7.py` / `.out` | X-V7-001..X-V7-005 including the retraction |

### Test execution at baseline

`tests/unit/test_e01_structure.py`, `test_e02_liquidity.py`, `tests/integration/test_cp2_engines.py` — **100 passed in 2.28 s**.
`tests/unit/test_pattern_detect.py`, `test_pattern_fibonacci.py`, `test_setup_gates.py`, `test_setup_family_sf_fvg_sweep_rev.py`, `test_playbook_pb_fvg_sweep_rev_a.py`, `test_decision_pipeline.py` — **268 passed in 4.44 s**.

All green. That is the N-022 finding in one line: the suite is green over 3 of 21 declared E01 event types, over an inverted E02 ground truth, and over a leak check that fails at 165 bars with the suite's own generator.

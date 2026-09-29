## C-013 — formal verdict

### Auditor claim (short quote)

“_p1_lane صف بدون maxsize است” — P1 is an unbounded queue. The full row alleges shared-lane eviction does not bound it, the existing NFR probe misses P1/slow consumers and the 500-item feature/evidence queue, and device consumption/latency was not measured. Full row read from `/tmp/AUDIT.md`. Auditor S1.

### What I read (files, line ranges, functions, callers)

Complete apex/bus.py:1–241 (events/identity creation, subscriptions, all priority paths, eviction, dispatch/start/stop, metrics and RawCandleQueue); complete scripts/run_nfr_harness.py:1–277 including queue probe and aggregate/printed verdict; complete tests/unit/test_bus.py:1–150 and test_ai10_nfr_harness.py:1–end. Direct composition/collector Runtime.start/stop (run_apex.py:145–181), full FSM publisher (fsm.py:506–528), boot publication (1055–1063; complete containing boot method previously read for C-002), scheduler publication/call chain already read for C-006, and complete SignalingPlane.send (signaling.py:666–784) to distinguish transport from bus observation. Consumers grep: `C-013-consumers.out`. This is not a claim to have re-audited all Telegram internals or frozen engine formulas.

### Reproduction (command, probe file, actual result)

`PYTHONDONTWRITEBYTECODE=1 python3 AUDIT/probes_V1a/C-013.py`; raw `C-013.out`, exit 0. Native EventBus, event factory, **real dispatcher and asynchronous consumer**, RawCandleQueue and the original imported `_queue_bounds_probe`. No network, transport, orders or AST extraction.

1. With lane_maxsize=10, retained P1 queued events grow **1,000 → 2,000 → 4,000**, after GC traced heap delta **1,506,646 → 3,028,638 → 6,073,006 B**; shared queue stays zero. Actual `_p1_lane.maxsize=0`. Each payload includes about 1 KiB of unique text. No dispatcher in this growth subcase, explicitly; this models backlog, not a post-drain memory leak.
2. With dispatcher running and a 40-ms async P1 consumer, enqueue **75 P1** then one P2; queue snapshot P1=75 despite bound=10. All **75 delivered FIFO**, zero evictions. Last P1 starts **2.981292 s** after publication, completes **3.021564 s**; **25** P1 events wait over two seconds even before their consumer starts. P2 starts after **3.021482 s**. A concurrently published P0 completes inline in **0.000030 s** with its deliberately fast consumer. This is local queue/consumer latency, not Telegram transmission latency or a phone benchmark.
3. Shared control: 15 P2 at capacity 10 yields queue 10, evicted 5. Raw control: 1001 inputs at capacity 1000 yields queue 1000, one drop, oldest remaining item 1. These bounds do work.
4. Publishing 501 P2 messages under a feature/evidence topic to the generic bus returns without backpressure and leaves 501 queued under capacity 1000. This does not invent or prove wiring of an independent feature output queue; it shows this API is not that distinct 500-item blocking queue.
5. Original native NFR queue probe still reports **bounded=true, P0 delivered 2000/2000, shared queue 1000, P2 evicted 100**. Its own workload publishes **no P1**, starts no dispatcher, and measures no P1 latency.

This row's operations issue **no SQLite queries** and have no per-cell/per-row database path. Repository DDL/200k corpus and device-index EXPLAIN are therefore **not applicable**, not omitted measurements of a hidden SQL path. The neighboring rows contain actual 200k-store comparisons where SQL is causal.

Guarded command: `python3 -m pytest -q -p no:cacheprovider tests/unit/test_bus.py tests/unit/test_ai10_nfr_harness.py::TestBounds tests/unit/test_ai10_nfr_harness.py::TestTNFR004QueueBounds::test_p0_delivery_is_synchronous_not_buffered`; **12 passed in 0.08s**, `C-013-pytest.out`. Both guards **[]**. The full NFR harness/order-latency fixture was deliberately not invoked; only its queue probe and no-order tests ran.

### Verdict and reasoning

**CONFIRMED / S1.** The P1 lane has no intrinsic capacity or publisher backpressure. Evicting a different queue does not free a bounded P1 slot; after that queue empties P1 still accumulates. The real dispatcher counterexample establishes local latency >2 seconds under a declared slow-consumer workload, beyond the auditor's enqueue-only reproduction. It does not prove a production Telegram alert missed its SLA: the current Runtime subscriber is an in-memory collector, and signaling publishes its bus receipt **after** transport, rather than using this lane as its outbound message queue.

The published T-NFR-004 test mix really is 2000 P0 + 1000 P2; implementing that narrow mix is not falsification. Treating its PASS as proof of **all** queue/capacity/P1 guarantees is the coverage gap. Device capacity remains unverified.

### Root cause

An asyncio.Queue without maxsize accepts unlimited P1 puts. `_lane_maxsize` only triggers best-effort shared eviction. Dispatch awaits each subscriber serially and drains P1 preferentially; no admission-rate bound, per-consumer deadline or durable overflow path controls backlog. Deque eviction diagnostics already have a 4096 bound and are not an unbounded structure in this row. Successfully drained queues release events; the defect is unbounded backlog under insufficient service, not retention forever after delivery.

### Direct impact

Growing queued-event memory and P1/P2 observation delay under overload or a slow subscriber. P1 is not silently dropped by the measured queue path; making it bounded must not replace that property with silent loss. No actual capital loss, target-device OOM or Telegram transport delay is observed.

### Secondary effects and interactions (upstream/downstream)

FSM noncritical transitions and non-recovery boot events publish P1; their await currently means enqueued, not all subscribers completed. Runtime's collector then keeps delivered events (C-003), so draining the queue does not fix that independent history growth. A blocking P1 publish could stall FSM advancement if consumers rely on work that the publisher still holds, requiring deadlock/lock-order tests. P0 bypasses dispatcher, but inline slow consumers can still delay its caller; the fast P0 control does not prove universal zero delay.

**ISSUE-076:** heavier replay/backfill traffic may increase workload but SQL indexes/commit batching do not bound P1. **ISSUE-077:** an unyielding/stalled analytical driver or DB consumer can reduce service; gather/cursor persistence is a distinct failure mechanism. **ISSUE-079:** synchronous fingerprint/preparation work can starve the same event loop, making backlog/latency worse; fixing that join is necessary for throughput but not a queue admission policy. No separate new X finding is claimed.

### Contract and decisions

APEX_GEN5.md:18891–18901 defines inbound raw 1000/drop-oldest, feature/evidence output **500/blocking producer**, synchronous ledger, dedicated P0/P1, P0 never dropped/delayed and P1 transmitted within **2 s**. T-NFR-004 at 19133 prescribes the narrow P0/P2 mix; release rule at 19146 requires target-device/headroom acceptance. The specific raw and feature policies must not be flattened into one generic drop-oldest queue. Reviewed decision-log/consumer search found no later owner permission to discard P0/P1 or treat shared-lane size as all-queue acceptance. User frozen-path instructions govern edit permissions even though the harness docstring casually calls the bus frozen.

### Frozen status and non-frozen alternative

apex/bus.py and the harness are **not** in the user's frozen set. Fix via non-frozen bus/composition/supervisor boundaries and additive durable outbox/journal if selected; frozen engine producers/catalog/research need not change. Preserve the in-process asyncio bus contract rather than introduce a networked broker as an unapproved workaround.

### Fix options (A/B/C… each with side effects, or "single path" with justification)

**A — governed admission/capacity, bounded P1 work, explicit latency/escalation and durable overflow where appropriate.** Keep P0 inline and no silent P1 loss; separately provision the actual feature/evidence 500-item blocking queue and raw queue. A bounded queue alone cannot guarantee a two-second deadline under an arbitrarily slow consumer: arrival/service capacity, consumer isolation and timeout/escalation must be specified. Durable overflow adds disk/serialization overhead, restart/dedup and possibly an additive schema; it prevents loss but does not by itself make late delivery timely. Maintain one writer/ordered identities, and avoid deadlock when publisher and consumer share locks.

**B — subscriber isolation and realistic admission-rate limits plus truthful NFR reporting first.** Can reduce stalls and expose overload with no required migration, but an unbounded queue remains a resource risk if the limit is not enforced. Unrestricted parallel dispatch breaks per-lane/subscriber order; use explicit ordered partitions if approved. Never drop/coalesce critical events merely by topic without a governed semantic equivalence rule.

Existing `test_p1_never_dropped_evicts_shared` explicitly expects two P1 entries at capacity one and no blocking; a correct capacity/backpressure policy must replace that expectation with deterministic completion/backpressure assertions, while FIFO, no-loss, raw drop-oldest and synchronous P0 controls remain. Transport idempotency/restart identities must survive any spill/retry; UUID event identities are operational, not snapshot hashes. Pure queue plumbing requires no retraining and must not alter model inputs/decisions or canonical historical hashes. Changed delivery ordering can affect upstream/downstream scheduling and must be parity-tested, not assumed harmless.

### My recommendation

A, retaining truthful separation between enqueue, consumer completion and actual transmission. Extend T-NFR-004 instead of claiming the current narrow PASS closes P1/feature-output/device acceptance. Owner-approved overload/escalation policy is necessary where finite resources, lossless preservation and strict timeliness conflict.

### Acceptance and regression tests

Keep actual-dispatch slow-consumer tests, growth samples and P0/P2/raw controls. Test bounded P1 publication, no loss/duplicate IDs, FIFO or explicitly approved ordering, cancellation/shutdown, spill/restart, queue-full escalation, deadlock freedom and downstream latency. Exercise the **real wired** 500-item output queue with blocking producers, not just a topic name, and separately measure send receipts. Run target-device burst/sustained capacity and 30% headroom tests before acceptance; no finite queue test can certify arbitrary unbounded load.

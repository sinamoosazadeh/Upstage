#!/usr/bin/env bash
# Read-only source search requested by the independent verifier.
# It intentionally searches code/tests only; no execution, secrets, .env, or data.
set -u
cd "$(dirname "$0")/../.."

echo "TRACE_VERSION=caller-callee-grep-v1"
echo "ROOT=$(pwd)"

echo "FILES_READ=apex/ops/paper_loop.py apex/ops/engine_context.py scripts/run_apex.py tests/unit/test_ops_backup.py tests/unit/test_fabric_context.py"

echo

trace() {
  local label="$1"; shift
  echo "### ${label}"
  grep -rn --include='*.py' --exclude-dir='AUDIT' --exclude-dir='data' -E "$*" apex scripts tests || true
  echo
}

trace 'paper_loop public/runtime symbols' \
  'PaperRuntime|PlanQueue|normalize_plan|intent_id_for|fill_from_result|last_closed_price|run_cycle|execute_plan|manage_positions|_stage_(ingest|quality|features|engines|setup|gates|risk|decision|execution)|_resolve_plan|_storage_guard'
trace 'engine_context producer/projection symbols' \
  'EngineContextProducer|prepare_engine_bundle|prepare\(|get_bridge_context|_compose_bridge_context|paper_account_inputs|paper_account_state|paper_reservation_proxy|paper_close_marks|load_decision_runtime|validate_classifier|read_context_fact|append_context_fact|persist_public_venue_facts|read_public_venue_facts|adv_input|ladder_input|quality_window|mtf_inputs|feature_timeline|train_classifier_bounded'
trace 'run_apex composition/root symbols' \
  'Runtime|_boot\(|_demo\(|_serve\(|_bootstrap\(|_status\(|_repair_partial\(|_noop_handler|_bootstrap_handler|PaperRuntime|EngineContextProducer|Watchdog|TelegramGateway|StartupReconciliation|ExecutionFSM'
trace 'backup test/direct consumers' \
  'SQLiteBackupManager|restore_drill|verify_restored_ledger|storage_guard|next_drill_due|backup_summary|BACKUP_INTERVAL_MINUTES|RPO_SECONDS|RTO_SECONDS'
trace 'fabric context/conflict test/direct consumers' \
  'build_context|context_confidence|setup_score|resolve\(|assert_permission_monotone|EvidenceFabric|ConflictRecord|redundancy_rho|q_min_tf|data_trust_floor|GATE3_CONFLICT_THRESHOLD|GATE4_REDUNDANCY_THRESHOLD'

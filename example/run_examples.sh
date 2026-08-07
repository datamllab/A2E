#!/bin/bash
# A2E examples — step-by-step walkthrough
#
# Requirements:
#   Terminal 1:  cd task && set -a; . ../.env; set +a && uv run --frozen a2e serve
#   Terminal 2:  cd task && set -a; . ../.env; set +a && bash ../example/run_examples.sh
#
# Each step runs a real experiment and pauses so you can browse results at
# http://localhost:6006 before moving on. Evaluation is always done separately
# via the standalone eval pipeline (Step 4).

set -e

# ── pre-flight ────────────────────────────────────────────────────────────────

echo "=== 0. Pre-flight check ==="

if ! curl -sf http://localhost:6006/healthz > /dev/null 2>&1; then
    echo "✗ A2E server not reachable at http://localhost:6006"
    echo "  Start it first: cd task && set -a; . ../.env; set +a && uv run --frozen a2e serve"
    exit 1
fi
echo "✓ server is up"

EXPERIMENT_IDS=()

# ── helper ─────────────────────────────────────────────────────────────────────

pause_and_view() {
    local label="$1"
    echo ""
    echo "  → Open http://localhost:6006 to browse datasets, experiments, and traces."
    echo "  → Press Enter to continue to the next section."
    read -r
    echo ""
}

# ── 1. Quickstart: mmlu × agno ────────────────────────────────────────────────

echo "=== 1. Quickstart: mmlu × agno, 5 examples ==="
echo "    This is a multiple-choice QA benchmark. The agent picks A/B/C/D answers."
echo ""

uv run python examples/run_experiment.py \
    --dataset mmlu --agent agno --n 5 2>&1 | tee /tmp/a2e_example_1.log

EXP_ID=$(grep -oP 'experiment_id:\s*\K.+' /tmp/a2e_example_1.log | head -1 || true)
if [ -n "$EXP_ID" ]; then
    EXPERIMENT_IDS+=("$EXP_ID")
    echo "experiment_id recorded: $EXP_ID"
fi

pause_and_view "mmlu"

# ── 2. τ-bench: retail scenario ───────────────────────────────────────────────

echo "=== 2. τ-bench: retail domain, 5 examples ==="
echo "    A multi-turn dialogue benchmark. The agent handles customer service"
echo "    tasks like order lookups, returns, and exchanges."
echo ""

uv run python examples/run_experiment.py \
    --dataset tau-bench --domain retail --agent agno --n 5 2>&1 | tee /tmp/a2e_example_2.log

EXP_ID=$(grep -oP 'experiment_id:\s*\K.+' /tmp/a2e_example_2.log | head -1 || true)
if [ -n "$EXP_ID" ]; then
    EXPERIMENT_IDS+=("$EXP_ID")
    echo "experiment_id recorded: $EXP_ID"
fi

pause_and_view "tau-bench"

# ── 3. Sandbox: SWE-bench ─────────────────────────────────────────────────────

echo "=== 3. Sandbox: swe-bench-lite, 1 example ==="
echo "    Runs the agent inside a Docker container. It edits real code and the"
echo "    test suite grades the result. Requires Docker."
echo ""
echo "    Sandbox datasets are scored inside the container via the official test"
echo "    harness. Use --evaluators to surface the result:"
echo "      swe_resolved, swe_fail_to_pass, swe_pass_to_pass  (SWE-bench)"
echo "        resolved:      all target tests now pass"
echo "        fail_to_pass:  fraction of bug tests fixed"
echo "        pass_to_pass:  fraction of existing tests not broken"
echo "      tb_resolved                                       (Terminal-Bench)"
echo "    These are pass-through — they read the pre-computed score from the sandbox"
echo ""
echo "    Skipping — uncomment below to run:"
echo "    # uv run python examples/run_experiment.py \\"
echo "    #     --dataset swe-bench-lite --agent agno --n 1 \\"
echo "    #     --evaluators swe_resolved"

# Tip: pin a pre-cached instance to avoid downloading a random image:
#   A2E_SWE_INSTANCE=<instance_id>        swe-bench-lite / swe-bench-verified
#   A2E_SWE_PRO_INSTANCE=<instance_id>    swe-bench-pro
#   A2E_TB2_TASK=<task_name>              terminal-bench-2
#   A2E_TB21_TASK=<task_name>             terminal-bench-2.1
# The first run downloads a Docker image (1-3 GB) and may take a while.

# Uncomment to enable:
# uv run python examples/run_experiment.py \
#     --dataset swe-bench-lite --agent agno --n 1 --evaluators swe_resolved \
#     2>&1 | tee /tmp/a2e_example_3.log
# EXP_ID=$(grep -oP 'experiment_id:\s*\K.+' /tmp/a2e_example_3.log | head -1 || true)
# if [ -n "$EXP_ID" ]; then
#     EXPERIMENT_IDS+=("$EXP_ID")
# fi

pause_and_view "sandbox"

# ── 4. Standalone evaluation ──────────────────────────────────────────────────

echo "=== 4. Standalone evaluation ==="
echo "    A2E decouples evaluation from experiment execution. Experiments only"
echo "    produce runs and traces. This step independently pulls traces from the"
echo "    server, scores them, and writes results back."
echo ""
echo "    --part all runs diagnostic metrics (plan, tool, correctness, efficiency,"
echo "    safety). It does NOT include sandbox pass/fail scores (tb_resolved,"
echo "    swe_resolved...). Those are only available via --evaluators during"
echo "    experiment execution (see Step 3)."
echo ""

if [ ${#EXPERIMENT_IDS[@]} -eq 0 ]; then
    echo "    No experiment_ids captured. To evaluate a previous experiment:"
    echo "      uv run python ../eval/scripts/run_eval.py --experiment-id <id> --part all"
else
    for EID in "${EXPERIMENT_IDS[@]}"; do
        echo "    Evaluating experiment: $EID"
        uv run python ../eval/scripts/run_eval.py \
            --experiment-id "$EID" --part correct,efficiency 2>&1 | tail -5
        echo ""
    done
fi

# ── done ───────────────────────────────────────────────────────────────────────

echo "=== Done ==="
echo "  Browse everything at http://localhost:6006"
echo ""
echo "  More commands to try:"
echo "    uv run python examples/run_experiment.py --list"
echo "    uv run python examples/run_experiment.py --help"
echo "    uv run python ../eval/scripts/run_eval.py --list-parts"

#!/usr/bin/env bash
# Docker-only batch execution entry point for OpenClaw Safety Bench.

set -euo pipefail

SCRIPT_NAME="$(basename "$0")"

show_help() {
    cat <<'EOF'
Usage: batch_execute.sh [options]

Run OpenClaw benchmark tasks locally with the Docker backend, then normalize
outputs into batch_logs/{batch_name} for analysis.

Required input (choose one):
  --tasks-dir <path>       Flat task directory containing task_* subdirs
  --tasks-jsonl <path>     JSONL task list with {"task_id": "...", "target": "openclaw"}

Required Docker backend config:
  --models-config <path>   Model config YAML; see docker_models_config.example.yaml

Core options:
  --backend <docker>       Execution backend. Only docker is supported in open_source.
  --batch-logs <dir>       Batch logs root (default: ./batch_logs)
  --batch-name <name>      Batch name (default: docker_eval_{timestamp}_{suffix})
  --output-dir <path>      Optional report/analysis output dir
  --with-reference-solution  Append metadata.yaml reference_solution to prompts
  --skip-judge             Run task graders only; skip LLM judge
  --judge-models-config <path>  Multi-judge config YAML/JSON
  --skip-analyze           Skip report.md and analysis.json generation

Docker options:
  --docker-concurrency <n> Max parallel Docker task containers per model (default: 1)
  --docker-image <image>   OpenClaw runtime image (default: benchmark default)
  --docker-timeout <sec>   Per-task timeout (default: 600)
  --docker-init-timeout <sec>  fixture/init.sh timeout (default: 300)

Analysis thresholds:
  --low-threshold <float>  Hard threshold (default: env or 0.3)
  --high-threshold <float> Easy threshold (default: env or 0.8)
  --diff-threshold <float> Discriminative range threshold (default: env or 0.3)

General:
  --verbose                Show detailed benchmark logs
  --help                   Show this help message

Example:
  ./scripts/batch_execute.sh \
      --backend docker \
      --tasks-jsonl batch_inputs/version/v1/test_tasks.jsonl \
      --models-config docker_models_config.yaml \
      --docker-concurrency 2 \
      --batch-logs batch_logs \
      --batch-name docker_eval
EOF
}

log_info() { echo "[INFO] $1"; }
log_error() { echo "[ERROR] $1" >&2; }

BACKEND="docker"
TASKS_DIR=""
TASKS_JSONL=""
BATCH_LOGS_DIR=""
BATCH_NAME=""
OUTPUT_DIR=""
MODELS_CONFIG=""
DOCKER_IMAGE=""
DOCKER_TIMEOUT=600
DOCKER_INIT_TIMEOUT=300
DOCKER_CONCURRENCY=1
WITH_REFERENCE_SOLUTION=false
SKIP_JUDGE=false
JUDGE_MODELS_CONFIG=""
SKIP_ANALYZE=false
LOW_THRESHOLD=""
HIGH_THRESHOLD=""
DIFF_THRESHOLD=""
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --backend)
            [[ $# -ge 2 ]] || { log_error "--backend requires docker"; exit 1; }
            BACKEND="$2"; shift 2 ;;
        --tasks-dir)
            [[ $# -ge 2 ]] || { log_error "--tasks-dir requires a path"; exit 1; }
            TASKS_DIR="$2"; shift 2 ;;
        --tasks-jsonl)
            [[ $# -ge 2 ]] || { log_error "--tasks-jsonl requires a path"; exit 1; }
            TASKS_JSONL="$2"; shift 2 ;;
        --batch-logs)
            [[ $# -ge 2 ]] || { log_error "--batch-logs requires a path"; exit 1; }
            BATCH_LOGS_DIR="$2"; shift 2 ;;
        --batch-name)
            [[ $# -ge 2 ]] || { log_error "--batch-name requires a name"; exit 1; }
            BATCH_NAME="$2"; shift 2 ;;
        --output-dir)
            [[ $# -ge 2 ]] || { log_error "--output-dir requires a path"; exit 1; }
            OUTPUT_DIR="$2"; shift 2 ;;
        --models-config)
            [[ $# -ge 2 ]] || { log_error "--models-config requires a path"; exit 1; }
            MODELS_CONFIG="$2"; shift 2 ;;
        --docker-image)
            [[ $# -ge 2 ]] || { log_error "--docker-image requires an image"; exit 1; }
            DOCKER_IMAGE="$2"; shift 2 ;;
        --docker-timeout)
            [[ $# -ge 2 && "$2" =~ ^[0-9]+$ ]] || { log_error "--docker-timeout requires seconds"; exit 1; }
            DOCKER_TIMEOUT="$2"; shift 2 ;;
        --docker-init-timeout)
            [[ $# -ge 2 && "$2" =~ ^[0-9]+$ ]] || { log_error "--docker-init-timeout requires seconds"; exit 1; }
            DOCKER_INIT_TIMEOUT="$2"; shift 2 ;;
        --docker-concurrency)
            [[ $# -ge 2 && "$2" =~ ^[0-9]+$ && "$2" -ge 1 ]] || { log_error "--docker-concurrency requires a positive integer"; exit 1; }
            DOCKER_CONCURRENCY="$2"; shift 2 ;;
        --with-reference-solution) WITH_REFERENCE_SOLUTION=true; shift ;;
        --skip-judge) SKIP_JUDGE=true; shift ;;
        --judge-models-config)
            [[ $# -ge 2 ]] || { log_error "--judge-models-config requires a path"; exit 1; }
            JUDGE_MODELS_CONFIG="$2"; shift 2 ;;
        --skip-analyze) SKIP_ANALYZE=true; shift ;;
        --low-threshold)
            [[ $# -ge 2 ]] || { log_error "--low-threshold requires a value"; exit 1; }
            LOW_THRESHOLD="$2"; shift 2 ;;
        --high-threshold)
            [[ $# -ge 2 ]] || { log_error "--high-threshold requires a value"; exit 1; }
            HIGH_THRESHOLD="$2"; shift 2 ;;
        --diff-threshold)
            [[ $# -ge 2 ]] || { log_error "--diff-threshold requires a value"; exit 1; }
            DIFF_THRESHOLD="$2"; shift 2 ;;
        --verbose) VERBOSE=true; shift ;;
        --help) show_help; exit 0 ;;
        --skip-submit|--skip-download|--skip-eval|--skip-upload|--resume|--re-eval|--limit|--eval-concurrency|--templates-config|--template-mode|--max-concurrent|--max-retry|--rate|--staging-dir|--traces-dir)
            log_error "$1 is not supported by the open_source Docker-only batch runner"; exit 1 ;;
        -*) log_error "Unknown option: $1"; show_help; exit 1 ;;
        *) log_error "Unexpected argument: $1"; show_help; exit 1 ;;
    esac
done

if [[ "$BACKEND" != "docker" ]]; then
    log_error "open_source supports only --backend docker"
    exit 1
fi
if [[ -n "$TASKS_DIR" && -n "$TASKS_JSONL" ]]; then
    log_error "--tasks-dir and --tasks-jsonl are mutually exclusive"
    exit 1
fi
if [[ -z "$TASKS_DIR" && -z "$TASKS_JSONL" ]]; then
    log_error "Either --tasks-dir or --tasks-jsonl is required"
    show_help
    exit 1
fi
if [[ -z "$MODELS_CONFIG" ]]; then
    log_error "--models-config is required"
    exit 1
fi
if [[ -n "$TASKS_DIR" && ! -d "$TASKS_DIR" ]]; then
    log_error "tasks-dir does not exist: $TASKS_DIR"
    exit 1
fi
if [[ -n "$TASKS_JSONL" && ! -f "$TASKS_JSONL" ]]; then
    log_error "tasks-jsonl does not exist: $TASKS_JSONL"
    exit 1
fi
if [[ ! -f "$MODELS_CONFIG" ]]; then
    log_error "models-config does not exist: $MODELS_CONFIG"
    exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPTS_DIR="$PROJECT_ROOT/scripts"
ENV_FILE="$PROJECT_ROOT/.env"

if [[ -z "${PYTHON_CMD:-}" ]]; then
    if command -v uv >/dev/null 2>&1 && [[ -f "$PROJECT_ROOT/pyproject.toml" ]]; then
        if [[ -f "$PROJECT_ROOT/uv.lock" ]]; then
            PYTHON_CMD="env UV_CACHE_DIR=.uv-cache uv run --frozen python"
        else
            PYTHON_CMD="env UV_CACHE_DIR=.uv-cache uv run python"
        fi
    else
        PYTHON_CMD="python3"
    fi
fi

if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
    log_info "Loaded environment from $ENV_FILE"
fi

if [[ -z "$JUDGE_MODELS_CONFIG" ]]; then
    for cfg in judge_models_config.yaml judge_models_config.yml judge_models_config.json; do
        if [[ -f "$PROJECT_ROOT/$cfg" ]]; then
            JUDGE_MODELS_CONFIG="$PROJECT_ROOT/$cfg"
            break
        fi
    done
fi
if [[ -n "$JUDGE_MODELS_CONFIG" && ! -f "$JUDGE_MODELS_CONFIG" ]]; then
    log_error "judge-models-config does not exist: $JUDGE_MODELS_CONFIG"
    exit 1
fi

if [[ -z "$BATCH_NAME" ]]; then
    TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
    RANDOM_SUFFIX="$(head -c 4 /dev/urandom | xxd -p | head -c 4)"
    BATCH_NAME="docker_eval_${TIMESTAMP}_${RANDOM_SUFFIX}"
    log_info "Auto-generated batch name: $BATCH_NAME"
fi
if [[ -z "$BATCH_LOGS_DIR" ]]; then
    BATCH_LOGS_DIR="$PROJECT_ROOT/batch_logs"
fi
BATCH_DIR="$BATCH_LOGS_DIR/$BATCH_NAME"
TRACES_DIR="$BATCH_DIR/traces"
mkdir -p "$BATCH_DIR" "$TRACES_DIR"

DOCKER_DATASET="$TASKS_DIR"
DOCKER_TASK_LIST=""
if [[ -n "$TASKS_JSONL" ]]; then
    DOCKER_DATASET="$PROJECT_ROOT/tasks"
    DOCKER_TASK_LIST="$TASKS_JSONL"
fi

log_info "Docker dataset:      $DOCKER_DATASET"
if [[ -n "$DOCKER_TASK_LIST" ]]; then
    log_info "Docker task list:    $DOCKER_TASK_LIST"
fi
log_info "Models config:       $MODELS_CONFIG"
log_info "Docker concurrency:  $DOCKER_CONCURRENCY"
log_info "Batch logs:          $BATCH_DIR"

DOCKER_CMD="$PYTHON_CMD \"$SCRIPTS_DIR/docker_execute_backend.py\""
DOCKER_CMD+=" --dataset \"$DOCKER_DATASET\""
if [[ -n "$DOCKER_TASK_LIST" ]]; then
    DOCKER_CMD+=" --task-list \"$DOCKER_TASK_LIST\""
fi
DOCKER_CMD+=" --round-dir \"$BATCH_DIR\""
DOCKER_CMD+=" --traces-dir \"$TRACES_DIR\""
DOCKER_CMD+=" --round-name \"$BATCH_NAME\""
DOCKER_CMD+=" --models-config \"$MODELS_CONFIG\""
DOCKER_CMD+=" --concurrency \"$DOCKER_CONCURRENCY\""
DOCKER_CMD+=" --timeout \"$DOCKER_TIMEOUT\""
DOCKER_CMD+=" --init-timeout \"$DOCKER_INIT_TIMEOUT\""
if [[ "$WITH_REFERENCE_SOLUTION" == true ]]; then
    DOCKER_CMD+=" --with-reference-solution"
fi
if [[ "$SKIP_JUDGE" == true ]]; then
    DOCKER_CMD+=" --skip-judge"
elif [[ -n "$JUDGE_MODELS_CONFIG" ]]; then
    DOCKER_CMD+=" --judge-models-config \"$JUDGE_MODELS_CONFIG\""
fi
if [[ -n "$DOCKER_IMAGE" ]]; then
    DOCKER_CMD+=" --image \"$DOCKER_IMAGE\""
fi
if [[ -f "$ENV_FILE" ]]; then
    DOCKER_CMD+=" --env-file \"$ENV_FILE\""
fi
if [[ "$VERBOSE" == true ]]; then
    DOCKER_CMD+=" --verbose"
fi

eval "$DOCKER_CMD"
log_info "Docker backend execution completed"

if [[ "$SKIP_ANALYZE" != true ]]; then
    ANALYZE_CMD="$PYTHON_CMD \"$SCRIPTS_DIR/batch_analyze.py\" --batch-logs \"$BATCH_LOGS_DIR\" --batch-name \"$BATCH_NAME\""
    if [[ -n "$OUTPUT_DIR" ]]; then
        ANALYZE_CMD+=" --output-dir \"$OUTPUT_DIR\""
    fi
    if [[ -n "$LOW_THRESHOLD" ]]; then
        ANALYZE_CMD+=" --low-threshold \"$LOW_THRESHOLD\""
    fi
    if [[ -n "$HIGH_THRESHOLD" ]]; then
        ANALYZE_CMD+=" --high-threshold \"$HIGH_THRESHOLD\""
    fi
    if [[ -n "$DIFF_THRESHOLD" ]]; then
        ANALYZE_CMD+=" --diff-threshold \"$DIFF_THRESHOLD\""
    fi
    eval "$ANALYZE_CMD"
    log_info "Analysis completed"
fi

echo ""
echo "Batch Execute Complete"
echo "Backend:    docker"
echo "Batch name: $BATCH_NAME"
echo "Batch logs: $BATCH_DIR"
echo "Traces:     $TRACES_DIR"
if [[ "$SKIP_ANALYZE" != true ]]; then
    if [[ -n "$OUTPUT_DIR" ]]; then
        echo "Report:     $OUTPUT_DIR/report.md"
        echo "Analysis:   $OUTPUT_DIR/analysis.json"
    else
        echo "Report:     $BATCH_DIR/report.md"
        echo "Analysis:   $BATCH_DIR/analysis.json"
    fi
fi

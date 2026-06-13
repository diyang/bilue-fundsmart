#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
cd "${repo_root}"

input_notebook="${INPUT_NOTEBOOK:-${repo_root}/evaluation/triage_service_evaluation.ipynb}"
triage_service_url="${TRIAGE_SERVICE_URL:-http://localhost:8001}"
triage_test_data_format="${TRIAGE_TEST_DATA_FORMAT:-split}"
triage_test_data="${TRIAGE_TEST_DATA:-${repo_root}/sythetic_tests/synthetic_generated.jsonl}"
triage_complaints_data="${TRIAGE_COMPLAINTS_DATA:-${repo_root}/sythetic_tests/synthetic_complaints.jsonl}"
triage_gold_labels="${TRIAGE_GOLD_LABELS:-${repo_root}/sythetic_tests/gold_labels.jsonl}"
triage_eval_timeout_seconds="${TRIAGE_EVAL_TIMEOUT_SECONDS:-120}"
run_ragas_eval="${RUN_RAGAS_EVAL:-false}"

papermill_bin="${PAPERMILL_BIN:-${repo_root}/.venv/bin/papermill}"
if [ ! -x "${papermill_bin}" ]; then
  papermill_bin="$(command -v papermill || true)"
fi

if [ -z "${papermill_bin}" ] || [ ! -x "${papermill_bin}" ]; then
  echo "papermill is not installed. Install it with: pip install papermill" >&2
  exit 1
fi

run_timestamp="$(date +%Y%m%d_%H%M%S)"
output_dir="${OUTPUT_DIR:-${repo_root}/evaluation/results/triage_service/papermill_runs/${run_timestamp}}"
attempts_dir="${output_dir}/attempts"
output_notebook="${OUTPUT_NOTEBOOK:-${output_dir}/triage_service_evaluation_executed.ipynb}"
mkdir -p "${attempts_dir}"

export JUPYTER_CONFIG_DIR="${output_dir}/jupyter_config"
mkdir -p "${JUPYTER_CONFIG_DIR}"

max_attempts="${PAPERMILL_MAX_ATTEMPTS:-${PAPERMILL_ATTEMPTS:-3}}"
retry_delay_seconds="${PAPERMILL_RETRY_DELAY_SECONDS:-30}"

if [ ! -f "${input_notebook}" ]; then
  echo "Input notebook not found: ${input_notebook}" >&2
  exit 1
fi

if ! [[ "${max_attempts}" =~ ^[1-9][0-9]*$ ]]; then
  echo "PAPERMILL_MAX_ATTEMPTS must be a positive integer" >&2
  exit 1
fi

if ! [[ "${retry_delay_seconds}" =~ ^[0-9]+$ ]]; then
  echo "PAPERMILL_RETRY_DELAY_SECONDS must be a non-negative integer" >&2
  exit 1
fi

case "${triage_test_data_format}" in
  split)
    if [ ! -f "${triage_complaints_data}" ]; then
      echo "Triage complaints data not found: ${triage_complaints_data}" >&2
      exit 1
    fi
    if [ ! -f "${triage_gold_labels}" ]; then
      echo "Triage gold labels not found: ${triage_gold_labels}" >&2
      exit 1
    fi
    ;;
  combined)
    if [ ! -f "${triage_test_data}" ]; then
      echo "Triage test data not found: ${triage_test_data}" >&2
      exit 1
    fi
    ;;
  auto)
    ;;
  *)
    echo "TRIAGE_TEST_DATA_FORMAT must be split, combined, or auto" >&2
    exit 1
    ;;
esac

if ! curl -fsS "${triage_service_url}/health" >/dev/null; then
  echo "Triage service is not reachable at ${triage_service_url}" >&2
  echo "Start it with: docker compose --env-file .env -f infra/docker-compose.yml up -d --build" >&2
  exit 1
fi

echo "Papermill output dir=${output_dir}"
echo "Papermill binary=${papermill_bin}"
echo "Max attempts per notebook=${max_attempts}"
echo "Retry delay seconds=${retry_delay_seconds}"
echo "Input notebook=${input_notebook}"
echo "Output notebook=${output_notebook}"
echo "Service URL=${triage_service_url}"
echo "Data format=${triage_test_data_format}"
echo "Combined data=${triage_test_data}"
echo "Complaints data=${triage_complaints_data}"
echo "Gold labels=${triage_gold_labels}"
echo "Ragas enabled=${run_ragas_eval}"

run_notebook() {
  notebook_path="$1"
  final_output="$2"
  shift 2

  notebook_label="$(basename "${final_output}" .ipynb)"
  attempt=1

  while [ "${attempt}" -le "${max_attempts}" ]; do
    attempt_output="${attempts_dir}/${notebook_label}.attempt-${attempt}.ipynb"
    log_path="${attempts_dir}/${notebook_label}.attempt-${attempt}.log"
    status_path="${attempts_dir}/${notebook_label}.attempt-${attempt}.status"

    echo "Running ${notebook_path} attempt ${attempt}/${max_attempts}"
    rm -f "${status_path}"
    set +e
    (
      "${papermill_bin}" "${notebook_path}" "${attempt_output}" "$@"
      printf '%s\n' "$?" >"${status_path}"
    ) 2>&1 | tee "${log_path}"
    status="$(cat "${status_path}")"
    set -e
    rm -f "${status_path}"

    if [ "${status}" -eq 0 ]; then
      cp "${attempt_output}" "${final_output}"
      echo "Completed ${notebook_path}; output=${final_output}"
      return 0
    fi

    echo "Failed ${notebook_path} attempt ${attempt}/${max_attempts}; log=${log_path}" >&2
    attempt=$((attempt + 1))
    if [ "${attempt}" -le "${max_attempts}" ]; then
      echo "Waiting ${retry_delay_seconds}s before retry." >&2
      sleep "${retry_delay_seconds}"
    fi
  done

  echo "Notebook failed after ${max_attempts} attempts: ${notebook_path}" >&2
  return 1
}

run_notebook \
  "${input_notebook}" \
  "${output_notebook}" \
  -p TRIAGE_SERVICE_URL "${triage_service_url}" \
  -p TRIAGE_TEST_DATA_FORMAT "${triage_test_data_format}" \
  -p TRIAGE_TEST_DATA "${triage_test_data}" \
  -p TRIAGE_COMPLAINTS_DATA "${triage_complaints_data}" \
  -p TRIAGE_GOLD_LABELS "${triage_gold_labels}" \
  -p TRIAGE_EVAL_TIMEOUT_SECONDS "${triage_eval_timeout_seconds}" \
  -p RUN_RAGAS_EVAL true \
  -p EVALUATION_OUTPUT_DIR "${output_dir}"

find "${attempts_dir}" -type f \( -name "*.attempt-*.ipynb" -o -name "*.attempt-*.log" \) -delete
rmdir "${attempts_dir}" 2>/dev/null || true
echo "Deleted papermill attempt notebooks and logs from ${attempts_dir}"

echo "Evaluation notebook written to ${output_notebook}"

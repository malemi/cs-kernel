#!/usr/bin/env bash
set -u
umask 077

if [ "$#" -ne 4 ]; then
    echo "Usage: collect_logs.sh CLONE_ROOT CONFIG ENV_FILE LAST_RUN_LOG" >&2
    exit 64
fi

clone_root=$1
collector_config=$2
collector_env=$3
last_run_log=$4

exec >"$last_run_log" 2>&1
cd "$clone_root" || exit 72
set -a
source "$collector_env" || exit 78
set +a
exec timeout --kill-after=5s 150s "$clone_root/.venv/bin/python" -m cs.monitor_cli once --config "$collector_config"

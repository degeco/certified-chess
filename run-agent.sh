#!/usr/bin/env bash
# Usage: ./run-agent.sh <folder> [model] [task file in that folder, default TASK.md]
# Account: AGY=agy or AGY=agy-dege (default). Check quota: agy -p "/usage"
# Runs one headless agy agent on <folder>/TASK.md; output goes to <folder>/agent.log.
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
dir="$root/${1:?folder}"
model="${2:-gemini-4-neon-high}"
task="${3:-TASK.md}"
log="agent-${task%.md}.log"
cd "$dir"
exec "${AGY:-agy-dege}" -p "You are the agent for the folder $(basename "$dir") of the project in $root. \
Read $root/AGENTS.md, $root/design/SPEC.md and ./$task, then carry out $task completely: \
write the code, run the tests, fix what fails, and finish by writing REPORT.md. \
Work only inside $dir. Do not stop to ask questions; record open questions in REPORT.md." \
  --add-dir "$root" --model "$model" --print-timeout 3000s >"$log" 2>&1

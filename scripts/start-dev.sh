#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for command in docker bun; do
    if ! command -v "$command" >/dev/null 2>&1; then
        printf "Required command '%s' was not found on PATH.\n" "$command" >&2
        exit 1
    fi
done

cd "$repo_root"
docker compose stop frontend

docker compose up --watch backend &
backend_pid=$!

cleanup() {
    kill "$backend_pid" 2>/dev/null || true
    wait "$backend_pid" 2>/dev/null || true
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

printf "Backend watch and frontend dev server started.\n"
printf "Frontend: http://localhost:5173 | Backend: http://localhost:8000\n"

bun run dev

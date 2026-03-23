#!/usr/bin/env bash
# Runs the common Docker Compose flows for the market analysis scaffold.
# This keeps the launch commands short and consistent on macOS and Linux.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
ENV_PATH="$PROJECT_ROOT/.env"
ENV_EXAMPLE_PATH="$PROJECT_ROOT/.env.example"
COMMAND=${1:-help}
BUILD_FLAG=${2:-}

print_usage() {
  cat <<'EOF'
Usage:
  bash scripts/adk.sh init-env
  bash scripts/adk.sh config
  bash scripts/adk.sh web [--build]
  bash scripts/adk.sh api [--build]
  bash scripts/adk.sh test

Commands:
  init-env  Create .env from .env.example if it does not exist.
  config    Render the Docker Compose configuration.
  web       Start the ADK web UI on http://localhost:8001.
  api       Start the ADK API server on http://localhost:8000.
  test      Run the containerized pytest suite.
EOF
}

ensure_env_file() {
  if [[ ! -f "$ENV_PATH" ]]; then
    cp "$ENV_EXAMPLE_PATH" "$ENV_PATH"
    echo "Created .env from .env.example. Replace GOOGLE_API_KEY before live analysis."
    return
  fi

  echo ".env already exists."
}

warn_if_missing_env() {
  local mode="$1"
  if [[ ! -f "$ENV_PATH" && ( "$mode" == "web" || "$mode" == "api" ) ]]; then
    echo "Warning: no .env file found. Compose defaults will let the service start, but live model calls need a real GOOGLE_API_KEY." >&2
  fi
}

run_compose() {
  (
    cd "$PROJECT_ROOT"
    docker compose "$@"
  )
}

case "$COMMAND" in
  help)
    print_usage
    ;;
  init-env)
    ensure_env_file
    ;;
  config)
    run_compose config
    ;;
  web)
    warn_if_missing_env web
    if [[ "$BUILD_FLAG" == "--build" ]]; then
      run_compose --profile web up --build market-analysis-web
    else
      run_compose --profile web up market-analysis-web
    fi
    ;;
  api)
    warn_if_missing_env api
    if [[ "$BUILD_FLAG" == "--build" ]]; then
      run_compose up --build market-analysis-agent
    else
      run_compose up market-analysis-agent
    fi
    ;;
  test)
    run_compose --profile test run --rm market-analysis-test
    ;;
  *)
    print_usage
    exit 1
    ;;
esac
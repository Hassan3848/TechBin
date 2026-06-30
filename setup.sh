#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

REQUIRED_NODE_MAJOR=20
LOCAL_BIN="$PROJECT_ROOT/node_modules/.bin"
TOOLS_BIN="$PROJECT_ROOT/.tools/node_modules/.bin"
export PATH="$LOCAL_BIN:$TOOLS_BIN:$PATH"

log() {
  printf '[setup] %s\n' "$1"
}

warn() {
  printf '[setup][warn] %s\n' "$1"
}

fail() {
  printf '[setup][error] %s\n' "$1" >&2
  exit 1
}

have() {
  command -v "$1" >/dev/null 2>&1
}

need_file() {
  [[ -f "$1" ]] || fail "Required file missing: $1"
}

node_major() {
  node -p "Number(process.versions.node.split('.')[0])"
}

ensure_node() {
  have node || fail "Node.js ${REQUIRED_NODE_MAJOR}+ is required."

  local major
  major="$(node_major)"
  if [[ "$major" -lt "$REQUIRED_NODE_MAJOR" ]]; then
    fail "Node.js ${REQUIRED_NODE_MAJOR}+ is required. Current: $(node -v)"
  fi

  have npm || fail "npm is required but was not found."
  log "Node.js ready: $(node -v)"
  log "npm ready: $(npm -v)"
}

ensure_pnpm() {
  if have pnpm; then
    log "pnpm ready: $(pnpm -v)"
    return
  fi

  if have corepack; then
    log "pnpm not found. Enabling pnpm with corepack..."
    corepack enable || true
    corepack prepare pnpm@latest --activate || true
  fi

  if ! have pnpm; then
    warn "corepack did not provide pnpm. Installing pnpm locally in .tools."
    mkdir -p .tools
    npm install --prefix .tools pnpm@10
  fi

  have pnpm || fail "pnpm installation failed. Install pnpm manually, then rerun setup.sh."
  log "pnpm ready: $(pnpm -v)"
}

check_project_files() {
  need_file package.json
  need_file pnpm-lock.yaml
  need_file src/main.tsx
  need_file src/app/App.tsx
  need_file src/shared/supabase.ts
  need_file supabase/schema.sql
}

install_frontend_deps() {
  log "Installing frontend dependencies..."
  if [[ -f pnpm-lock.yaml ]]; then
    if ! pnpm install --frozen-lockfile; then
      warn "Frozen lockfile install failed. Retrying with regular pnpm install."
      pnpm install
    fi
  else
    pnpm install
  fi
}

build_frontend() {
  log "Building Vite frontend..."
  pnpm build
}

print_success() {
  cat <<'EOF'

[setup] Setup completed successfully.

Before running the app:
  1. Create .env.local from .env.example
  2. Apply supabase/schema.sql in Supabase SQL editor
  3. Deploy the Edge Functions in supabase/functions

Run:
  ./setup.sh dev

Open:
  Frontend: http://localhost:5173

First admin:
  Create admin@techbin.com manually in Supabase Auth, then log in once.
EOF
}

run_dev() {
  check_project_files
  ensure_node
  ensure_pnpm
  exec pnpm dev
}

main() {
  case "${1:-setup}" in
    setup)
      log "Bootstrapping TechBin Dashboard from: $PROJECT_ROOT"
      check_project_files
      ensure_node
      ensure_pnpm
      install_frontend_deps
      build_frontend
      print_success
      ;;
    dev)
      run_dev
      ;;
    help|-h|--help)
      cat <<'EOF'
Usage:
  ./setup.sh        Install dependencies and build the project
  ./setup.sh setup  Same as above
  ./setup.sh dev    Start Vite frontend
EOF
      ;;
    *)
      fail "Unknown command: $1. Run ./setup.sh help"
      ;;
  esac
}

main "$@"

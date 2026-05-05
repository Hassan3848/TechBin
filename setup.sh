#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

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

if ! command -v node >/dev/null 2>&1; then
  fail "Node.js is required. Install Node.js first (recommended: 24.x LTS)."
fi

NODE_MAJOR="$(node -p "Number(process.versions.node.split('.')[0])")"
if [[ "$NODE_MAJOR" -lt 18 ]]; then
  fail "Node.js 18+ is required. Current: $(node -v)"
fi
if [[ "$NODE_MAJOR" -lt 24 ]]; then
  warn "Detected $(node -v). functions-backend declares Node 24 in engines; Node 24 is recommended."
fi

if ! command -v npm >/dev/null 2>&1; then
  fail "npm is required but was not found."
fi

if ! command -v pnpm >/dev/null 2>&1; then
  if command -v corepack >/dev/null 2>&1; then
    log "pnpm not found. Enabling pnpm via corepack..."
    corepack enable
    corepack prepare pnpm@latest --activate
  else
    fail "pnpm not found and corepack is unavailable. Install pnpm first."
  fi
fi

log "Installing root dependencies..."
if ! pnpm install --frozen-lockfile; then
  warn "Frozen lockfile install failed. Retrying with regular install..."
  pnpm install
fi

log "Installing functions-backend dependencies..."
pushd functions-backend >/dev/null
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi

log "Building functions-backend..."
npm run build
popd >/dev/null

if ! command -v firebase >/dev/null 2>&1; then
  warn "Firebase CLI not found. Install it before running emulators: npm i -g firebase-tools"
fi

if ! command -v java >/dev/null 2>&1; then
  warn "Java runtime not found. Firestore emulator may fail without Java."
fi

log "Setup completed successfully."
printf '\n'
printf 'Next steps:\n'
printf '1) Terminal A: pnpm emulators\n'
printf '2) Terminal B: pnpm dev\n'
printf '3) Open: http://localhost:5173\n'

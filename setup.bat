@echo off
setlocal

cd /d "%~dp0"

if not exist package.json (
  echo [setup][error] package.json missing.
  exit /b 1
)

if not exist src\shared\supabase.ts (
  echo [setup][error] src\shared\supabase.ts missing.
  exit /b 1
)

where node >nul 2>nul
if errorlevel 1 (
  echo [setup][error] Node.js 20+ is required.
  exit /b 1
)

where pnpm >nul 2>nul
if errorlevel 1 (
  echo [setup][warn] pnpm not found. Trying corepack.
  corepack enable
  corepack prepare pnpm@latest --activate
)

where pnpm >nul 2>nul
if errorlevel 1 (
  echo [setup][error] pnpm is required. Install pnpm and rerun setup.bat.
  exit /b 1
)

echo [setup] Installing dependencies...
pnpm install
if errorlevel 1 exit /b 1

echo [setup] Building frontend...
pnpm build
if errorlevel 1 exit /b 1

echo.
echo [setup] Setup completed successfully.
echo Create .env.local from .env.example, apply supabase\schema.sql, deploy Edge Functions, then run:
echo pnpm dev

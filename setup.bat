@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo [setup] Starting project bootstrap...

where node >nul 2>nul
if errorlevel 1 (
  echo [setup][error] Node.js is required. Install Node.js first (recommended: 24.x LTS).
  exit /b 1
)

for /f "tokens=1 delims=." %%i in ('node -v') do set NODE_TOKEN=%%i
set NODE_MAJOR=%NODE_TOKEN:v=%

if %NODE_MAJOR% LSS 18 (
  echo [setup][error] Node.js 18+ is required. Current:
  node -v
  exit /b 1
)

if %NODE_MAJOR% LSS 24 (
  echo [setup][warn] Node version is below 24.
  echo [setup][warn] functions-backend declares Node 24 in engines; Node 24 is recommended.
)

where npm >nul 2>nul
if errorlevel 1 (
  echo [setup][error] npm is required but was not found.
  exit /b 1
)

where pnpm >nul 2>nul
if errorlevel 1 (
  where corepack >nul 2>nul
  if errorlevel 1 (
    echo [setup][error] pnpm not found and corepack is unavailable. Install pnpm first.
    exit /b 1
  )
  echo [setup] pnpm not found. Enabling pnpm via corepack...
  call corepack enable
  if errorlevel 1 exit /b 1
  call corepack prepare pnpm@latest --activate
  if errorlevel 1 exit /b 1
)

echo [setup] Installing root dependencies...
call pnpm install --frozen-lockfile
if errorlevel 1 (
  echo [setup][warn] Frozen lockfile install failed. Retrying with regular install...
  call pnpm install
  if errorlevel 1 exit /b 1
)

echo [setup] Installing functions-backend dependencies...
cd /d "%~dp0functions-backend"
if exist package-lock.json (
  call npm ci
) else (
  call npm install
)
if errorlevel 1 exit /b 1

echo [setup] Building functions-backend...
call npm run build
if errorlevel 1 exit /b 1

cd /d "%~dp0"

where firebase >nul 2>nul
if errorlevel 1 (
  echo [setup][warn] Firebase CLI not found. Install it before running emulators: npm i -g firebase-tools
)

where java >nul 2>nul
if errorlevel 1 (
  echo [setup][warn] Java runtime not found. Firestore emulator may fail without Java.
)

echo [setup] Setup completed successfully.
echo.
echo Next steps:
echo 1) Terminal A: pnpm emulators
echo 2) Terminal B: pnpm dev
echo 3) Open: http://localhost:5173

exit /b 0

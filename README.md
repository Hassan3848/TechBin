# TechBin Dashboard (Development Setup)

TechBin Dashboard is an internal organizational dashboard built for a Smart AI-based waste bin system.
It provides role-based access (Admin / Viewer), secure authentication, and management features using Firebase Emulators.

This project is designed for academic / Capstone use and does not require a paid Firebase plan.

---

## Tech Stack

Frontend:
- React + TypeScript
- Vite
- Tailwind CSS

Backend:
- Firebase Authentication
- Firebase Cloud Functions
- Firestore
- Firebase Emulator Suite

---

## Project Structure

src/
 ├── app/
 │   ├── components/
 │   ├── contexts/AuthContext.tsx
 │   ├── App.tsx
 ├── firebase.ts

functions-backend/
 ├── src/index.ts
 ├── lib/ (auto-generated, do not edit)

firebase.json
firestore.rules

---

## Authentication & Roles

Roles:
- Admin: Can manage users and access all dashboard features
- Viewer: Read-only access

Permanent Root Admin:
admin@techbin.com

When this user logs in, the system automatically assigns Admin role using Firebase custom claims.

---

## How to Run the Project

1. Install dependencies

pnpm install
cd functions-backend
npm install

2. Build Cloud Functions (mandatory)

cd functions-backend
npm run build

3. Start Firebase Emulators

firebase emulators:start

Emulator UI:
http://127.0.0.1:4000

4. Start Frontend

pnpm dev

Frontend URL:
http://localhost:5173

---

## One-Command Setup (Recommended for Sharing)

You can now bootstrap dependencies + functions build with one file:

- macOS / Linux:
  - Run:
    - `bash setup.sh`
  - Optional:
    - `chmod +x setup.sh && ./setup.sh`

- Windows (CMD):
  - Run:
    - `setup.bat`

What the setup scripts do:
- Check Node.js and package managers
- Install root dependencies (`pnpm`)
- Install `functions-backend` dependencies (`npm`)
- Build Cloud Functions (`npm run build`)
- Warn if Firebase CLI or Java is missing

After setup, run:
- Terminal 1: `pnpm emulators`
- Terminal 2: `pnpm dev`

---

## Best Way to Share This Project

Preferred:
- Share via GitHub/GitLab (small size, version history, easy updates)

If sharing a ZIP:
- Include:
  - project source files
  - `pnpm-lock.yaml`
  - `setup.sh` and `setup.bat`
- Exclude:
  - `node_modules`
  - `dist`

Then tell the receiver:
1. Extract ZIP
2. Run setup script (`setup.sh` or `setup.bat`)
3. Run emulators + frontend

---

## Create First Admin User

Open Emulator UI:
http://127.0.0.1:4000/auth

Create user:
Email: admin@techbin.com
Password: 123123

Login using the same credentials in the app.

---

## Creating More Users

Only Admin users can create new users using the User Management page.
Roles are enforced using Firebase custom claims.

---

## Notes

- Firebase Auth Emulator resets users on restart unless persistence is enabled
- To persist emulator data:

firebase emulators:start --export-on-exit=./emulator-data --import=./emulator-data

- Analytics and telemetry data are mock-based for academic use

---

If you follow these steps exactly, the project will run successfully.

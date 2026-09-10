# NetWatch Desktop

This is a practical Windows Electron shell for the existing local NetWatch services. It starts the Windows host sensor and FastAPI backend on `127.0.0.1`, starts the Next standalone server when `frontend/.next/standalone/server.js` exists, health-checks them, opens the dashboard, and stops child processes when the window closes.

## Development

From the repository root in PowerShell:

```powershell
Copy-Item desktop\.env.template desktop\.env
.\desktop\scripts\dev.ps1
```

`dev.ps1` resolves Python in this order: `backend\.venv\Scripts\python.exe`, then root `.venv\Scripts\python.exe`, then `python.exe` on `PATH`. This fixes the root-vs-backend environment ambiguity without changing the existing root scripts. Install frontend dependencies and run `npm run build` in `frontend` before expecting the standalone frontend to open.

Safe lifecycle commands:

```powershell
.\desktop\scripts\start.ps1
.\desktop\scripts\stop.ps1
```

`start.ps1` launches Electron with a repository-root working directory. `stop.ps1` only stops the Electron process recorded by the desktop shell and refuses to act on a mismatched PID.

## Packaging

Run `npm install` in `desktop`, then `npm run dist`. The packaging step builds the frontend runtime, copies the backend and migrations, bundles a standalone Python interpreter plus the required dependencies, and produces a Windows NSIS installer in `desktop/release`.

The generated installer keeps the SQLite database, application data, and encrypted integration credentials in the per-user NetWatch data folder. It does not bundle `.env` secrets or router credentials. On first run, configure Technitium and a supported router provider in Settings.

The installer can operate without Docker. Docker/Technitium remains optional for discovery and monitoring, but DNS activity and DNS-based blocking require a reachable Technitium server. Full router blocking requires an OpenWrt or OPNsense API; a NOS/Hitron device without a supported API remains manual.

Technitium/Docker is intentionally not managed by this shell. Technitium and router APIs remain separate integrations configured by the backend; the local dashboard and core monitoring can still run without them.

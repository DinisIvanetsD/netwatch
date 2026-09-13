# NetWatch Desktop

This is a practical Windows Electron shell for the existing local NetWatch services. It starts the Windows host sensor and FastAPI backend on `127.0.0.1`, starts the Next standalone server when `frontend/.next/standalone/server.js` exists, health-checks them, opens the dashboard, and stops child processes when the window closes.

## Development

From the repository root in PowerShell:

```powershell
Copy-Item desktop\.env.template desktop\.env
.\desktop\scripts\dev.ps1
```

`dev.ps1` resolves Python in this order: `backend\.venv\Scripts\python.exe`, then root `.venv\Scripts\python.exe`, then `python.exe` on `PATH`. The default command assumes frontend dependencies are already installed and uses the existing frontend build if present. Pass `-BuildFrontend` to run `npm run build` first; it does not install frontend dependencies.

Safe lifecycle commands:

```powershell
.\desktop\scripts\start.ps1
.\desktop\scripts\stop.ps1
```

`start.ps1` launches Electron with a repository-root working directory. `stop.ps1` only stops the Electron process recorded by the desktop shell and refuses to act on a mismatched PID.

## Packaging

Install dependencies once with `npm install` in both `frontend` and `desktop`, then run `npm run dist` from `desktop`. `dist` builds the frontend standalone output, clears and stages the exact `desktop/runtime` directory, validates its required files and Python runtime, and produces a Windows NSIS installer in `desktop/release`. Python dependencies are copied from the existing `backend\.venv` when available, then the root `.venv`; the packaging scripts do not install Python packages.

The generated installer keeps the SQLite database, application data, and encrypted integration credentials in the per-user NetWatch data folder. It does not bundle `.env` secrets or router credentials. On first run, configure Technitium and a supported router provider in Settings.

The installer can operate without Docker. Docker/Technitium remains optional for discovery and monitoring, but DNS activity and DNS-based blocking require a reachable Technitium server. Full router blocking requires an OpenWrt or OPNsense API; a NOS/Hitron device without a supported API remains manual.

Technitium/Docker is intentionally not managed by this shell. For a Windows-local Technitium
installation, use `http://127.0.0.1:5380` in **Settings → Technitium DNS Server**, enter the
current administrator credentials, select DNS port `53`, save, test the connection, and run a
scan. The router must advertise the Windows PC's LAN address as DNS for other devices to appear
in DNS activity. Mobile hotspots and ISP routers that do not expose DHCP/DNS settings cannot be
controlled by the desktop app.

The desktop shell overrides Docker-only Technitium environment values with the local console
address by default. This prevents a development `.env` value such as `http://technitium:5380` or
its bootstrap password from being imported into the Windows desktop process. The password is never
stored in `desktop/.env`; enter the current Technitium password once in Settings, where NetWatch
stores it encrypted in the per-user application data directory. If the connection test reports
that Technitium has temporarily blocked login attempts, stop retrying and wait for its cooldown
before testing again.

The shell creates a valid Fernet key in the per-user `config.env`. It also repairs the invalid
unpadded key created by early development builds before saving encrypted provider credentials.

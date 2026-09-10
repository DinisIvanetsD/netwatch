const { app, BrowserWindow, ipcMain, shell } = require("electron");
const { spawn } = require("node:child_process");
const { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } = require("node:fs");
const crypto = require("node:crypto");
const path = require("node:path");
const http = require("node:http");

const repoRoot = path.resolve(__dirname, "..");
const runtimeRoot = app.isPackaged
  ? path.join(process.resourcesPath, "netwatch")
  : repoRoot;
const defaults = { backendPort: 8000, frontendPort: 3000, sensorPort: 8765 };
const services = new Map();
let mainWindow;
const hasSingleInstanceLock = app.requestSingleInstanceLock();

if (!hasSingleInstanceLock) {
  app.quit();
}

function loadEnv(file) {
  if (!existsSync(file)) return {};
  return Object.fromEntries(readFileSync(file, "utf8").split(/\r?\n/).filter((line) => line && !line.startsWith("#") && line.includes("=")).map((line) => {
    const index = line.indexOf("=");
    return [line.slice(0, index).trim(), line.slice(index + 1).trim().replace(/^['"]|['"]$/g, "")];
  }));
}

function prepareConfig() {
  if (!app.isPackaged) {
    return { ...defaults, ...loadEnv(path.join(__dirname, ".env")) };
  }
  const userData = app.getPath("userData");
  mkdirSync(userData, { recursive: true });
  const dataDirectory = path.join(userData, "data");
  mkdirSync(dataDirectory, { recursive: true });
  const databasePath = path.join(dataDirectory, "netwatch.db").replaceAll("\\", "/");
  const file = path.join(userData, "config.env");
  if (!existsSync(file)) {
    const secret = crypto.randomBytes(32).toString("base64url");
    writeFileSync(
      file,
      [
        "NETWATCH_ENV=development",
        "NETWATCH_SUBNET=192.168.1.0/24",
        "AUTO_DETECT_NETWORK=true",
        "NETWATCH_HOST_SENSOR_URL=http://127.0.0.1:8765",
        `DATABASE_URL=sqlite+aiosqlite:///${databasePath}`,
        `NETWATCH_SECRET_KEY=${secret}`,
        "CORS_ORIGINS=http://127.0.0.1:3000,http://localhost:3000",
        "ALLOWED_HOSTS=localhost,127.0.0.1",
      ].join("\n"),
      { encoding: "utf8", mode: 0o600 },
    );
  }
  const loaded = loadEnv(file);
  return {
    ...defaults,
    ...loaded,
    DATABASE_URL: loaded.DATABASE_URL?.includes("///./")
      ? `sqlite+aiosqlite:///${databasePath}`
      : loaded.DATABASE_URL,
    userData,
  };
}

let config = defaults;
let logPath;
const url = (port, endpoint) => `http://127.0.0.1:${port}${endpoint}`;

function writeLog(message) {
  const line = `[${new Date().toISOString()}] ${message}`;
  console.log(line);
  if (!logPath) return;
  try {
    appendFileSync(logPath, `${line}\n`, { encoding: "utf8" });
  } catch {
    // Logging must never stop the local services from starting.
  }
}

function pythonPath() {
  const candidates = [
    path.join(runtimeRoot, "python", "python.exe"),
    path.join(runtimeRoot, "python", "Scripts", "python.exe"),
    path.join(runtimeRoot, "backend", ".venv", "Scripts", "python.exe"),
    path.join(runtimeRoot, ".venv", "Scripts", "python.exe"),
    path.join(repoRoot, "backend", ".venv", "Scripts", "python.exe"),
    path.join(repoRoot, ".venv", "Scripts", "python.exe"),
  ];
  return candidates.find(existsSync) || "python.exe";
}

function childEnv(extra = {}) {
  const configured = Object.fromEntries(
    Object.entries(config).filter(
      ([key, value]) => /^[A-Z][A-Z0-9_]*$/.test(key) && typeof value === "string",
    ),
  );
  return { ...configured, ...extra };
}

function publicConfig() {
  return Object.fromEntries(
    Object.entries(config).filter(
      ([key]) => !/(SECRET|PASSWORD|TOKEN|API_KEY|API_SECRET)/i.test(key),
    ),
  );
}

function healthCheck(port, endpoint) {
  return new Promise((resolve) => {
    const request = http.get(url(port, endpoint), { timeout: 1200 }, (response) => {
      response.resume();
      resolve(response.statusCode >= 200 && response.statusCode < 500);
    });
    request.on("error", () => resolve(false));
    request.on("timeout", () => { request.destroy(); resolve(false); });
  });
}

async function waitForHealth(port, endpoint, attempts = 24) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (await healthCheck(port, endpoint)) return true;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  return false;
}

function startService(name, command, args, cwd, env) {
  if (services.has(name)) return;
  const child = spawn(command, args, {
    cwd, env: { ...process.env, ...env }, windowsHide: true, stdio: ["ignore", "pipe", "pipe"],
  });
  child.stdout.on("data", (data) => writeLog(`[${name}] ${data.toString().trimEnd()}`));
  child.stderr.on("data", (data) => writeLog(`[${name}:error] ${data.toString().trimEnd()}`));
  child.on("error", (error) => writeLog(`[${name}:spawn-error] ${error.message}`));
  child.on("exit", (code, signal) => {
    writeLog(`[${name}:exit] code=${code ?? "unknown"} signal=${signal ?? "none"}`);
    services.delete(name);
  });
  services.set(name, child);
}

function runCommand(command, args, cwd, env) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd,
      env: { ...process.env, ...env },
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
    child.stdout.on("data", (data) => writeLog(`[command] ${data.toString().trimEnd()}`));
    child.stderr.on("data", (data) => writeLog(`[command:error] ${data.toString().trimEnd()}`));
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`Command exited with code ${code ?? "unknown"}.`));
    });
  });
}

function startBackend() {
  startService("backend", pythonPath(), ["-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", String(config.backendPort)], path.join(runtimeRoot, "backend"), childEnv({
    CORS_ORIGINS: `http://127.0.0.1:${config.frontendPort},http://localhost:${config.frontendPort}`,
    ALLOWED_HOSTS: "localhost,127.0.0.1",
  }));
}

function startSensor() {
  startService("sensor", pythonPath(), ["-m", "uvicorn", "sensor_main:app", "--host", "127.0.0.1", "--port", String(config.sensorPort)], path.join(runtimeRoot, "backend"), childEnv());
}

function startFrontend() {
  const server = path.join(runtimeRoot, "frontend", ".next", "standalone", "server.js");
  if (!existsSync(server)) return false;
  const command = app.isPackaged
    ? process.execPath
    : process.platform === "win32"
      ? "npm.cmd"
      : "npm";
  const args = app.isPackaged ? [server] : ["start"];
  const cwd = app.isPackaged
    ? path.join(runtimeRoot, "frontend", ".next", "standalone")
    : path.join(runtimeRoot, "frontend");
  startService("frontend", command, args, cwd, childEnv({
    HOSTNAME: "127.0.0.1", PORT: String(config.frontendPort),
    NEXT_PUBLIC_API_URL: `http://127.0.0.1:${config.backendPort}`,
    NEXT_PUBLIC_WS_URL: `ws://127.0.0.1:${config.backendPort}/ws`,
    ...(app.isPackaged ? { ELECTRON_RUN_AS_NODE: "1" } : {}),
  }));
  return true;
}

async function startAll() {
  if (app.isPackaged) {
    await runCommand(
      pythonPath(),
      ["-m", "alembic", "upgrade", "head"],
      path.join(runtimeRoot, "backend"),
      childEnv(),
    );
  }
  startSensor();
  startBackend();
  const backendReady = await waitForHealth(config.backendPort, "/api/health");
  const frontendStarted = startFrontend();
  return {
    backendReady,
    frontendStarted,
    python: pythonPath(),
    services: [...services.keys()],
  };
}

async function status() {
  return {
    sensor: await healthCheck(config.sensorPort, "/health"),
    backend: await healthCheck(config.backendPort, "/api/health"),
    frontend: await healthCheck(config.frontendPort, "/api/health"),
    frontendBuilt: existsSync(path.join(runtimeRoot, "frontend", ".next", "standalone", "server.js")),
    python: pythonPath(),
  };
}

async function stopAll() {
  for (const [name, child] of services) {
    if (!child.killed) child.kill();
    services.delete(name);
  }
}

async function createWindow() {
  config = prepareConfig();
  logPath = path.join(config.userData || repoRoot, "desktop.log");
  writeLog(`Starting NetWatch desktop (packaged=${app.isPackaged})`);
  mkdirSync(path.join(runtimeRoot, "backend", "data"), { recursive: true });
  mainWindow = new BrowserWindow({ width: 1180, height: 760, minWidth: 900, minHeight: 600, webPreferences: { preload: path.join(__dirname, "preload.cjs"), contextIsolation: true, sandbox: true } });
  let started;
  try {
    started = await startAll();
  } catch (error) {
    writeLog(`NetWatch services could not be started: ${error instanceof Error ? error.stack || error.message : String(error)}`);
    started = {
      frontendStarted: false,
      services: [...services.keys()],
      error: error instanceof Error ? error.message : String(error),
    };
  }
  await mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"));
  mainWindow.webContents.send("desktop-state", { started, config: publicConfig() });
  if (started.frontendStarted && await waitForHealth(config.frontendPort, "/api/health")) {
    await mainWindow.loadURL(`http://127.0.0.1:${config.frontendPort}`);
  }
}

ipcMain.handle("netwatch:status", status);
ipcMain.handle("netwatch:open-dashboard", () => shell.openExternal(`http://127.0.0.1:${config.frontendPort}`));
ipcMain.handle("netwatch:restart", async () => { await stopAll(); return startAll(); });

if (hasSingleInstanceLock) {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
  app.whenReady().then(createWindow);
}
app.on("before-quit", (event) => { event.preventDefault(); stopAll().finally(() => app.exit(0)); });
app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });

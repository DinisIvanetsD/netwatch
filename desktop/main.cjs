const { app, BrowserWindow, ipcMain, shell } = require("electron");
const { spawn } = require("node:child_process");
const { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } = require("node:fs");
const crypto = require("node:crypto");
const path = require("node:path");
const http = require("node:http");
const { createReadinessMonitor } = require("./startup-readiness.cjs");

const repoRoot = path.resolve(__dirname, "..");
const runtimeRoot = app.isPackaged
  ? path.join(process.resourcesPath, "netwatch")
  : repoRoot;
const defaults = { backendPort: 8000, frontendPort: 3000, sensorPort: 8765 };
const services = new Map();
let mainWindow;
let configError;
let restartInFlight;
let stopInFlight;
let quitting = false;
let readinessGeneration = 0;
let readinessMonitor;
let dashboardNavigationGeneration;
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

function parsePort(value, name) {
  const port = Number.parseInt(String(value), 10);
  if (!/^\d+$/.test(String(value)) || !Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error(`${name} must be an integer between 1 and 65535 (received ${JSON.stringify(value)}).`);
  }
  return port;
}

function configuredPorts(values) {
  const ports = {
    backendPort: parsePort(values.BACKEND_PORT ?? defaults.backendPort, "BACKEND_PORT"),
    frontendPort: parsePort(values.FRONTEND_PORT ?? defaults.frontendPort, "FRONTEND_PORT"),
    sensorPort: parsePort(values.SENSOR_PORT ?? defaults.sensorPort, "SENSOR_PORT"),
  };
  if (new Set(Object.values(ports)).size !== Object.values(ports).length) {
    throw new Error("BACKEND_PORT, FRONTEND_PORT, and SENSOR_PORT must be different ports.");
  }
  return ports;
}

function generateFernetKey() {
  // Python's Fernet implementation expects a URL-safe base64 encoding of 32 bytes.
  return `${crypto.randomBytes(32).toString("base64url")}=`;
}

function isValidFernetKey(value) {
  return typeof value === "string"
    && /^[A-Za-z0-9_-]{43}=$/.test(value)
    && Buffer.from(value, "base64").length === 32;
}

function writeEnv(file, values) {
  writeFileSync(
    file,
    Object.entries(values).map(([key, value]) => `${key}=${value}`).join("\n"),
    { encoding: "utf8", mode: 0o600 },
  );
}

function prepareConfig() {
  if (!app.isPackaged) {
    const loaded = loadEnv(path.join(__dirname, ".env"));
    return { ...loaded, ...configuredPorts(loaded) };
  }
  const userData = app.getPath("userData");
  mkdirSync(userData, { recursive: true });
  const dataDirectory = path.join(userData, "data");
  mkdirSync(dataDirectory, { recursive: true });
  const databasePath = path.join(dataDirectory, "netwatch.db").replaceAll("\\", "/");
  const file = path.join(userData, "config.env");
  if (!existsSync(file)) {
    writeEnv(file, {
      NETWATCH_ENV: "development",
      NETWATCH_SUBNET: "192.168.1.0/24",
      AUTO_DETECT_NETWORK: "true",
      NETWATCH_HOST_SENSOR_URL: "http://127.0.0.1:8765",
      DATABASE_URL: `sqlite+aiosqlite:///${databasePath}`,
      NETWATCH_SECRET_KEY: generateFernetKey(),
      CORS_ORIGINS: "http://127.0.0.1:3000,http://localhost:3000",
      ALLOWED_HOSTS: "localhost,127.0.0.1",
    });
  }
  const loaded = loadEnv(file);
  if (!isValidFernetKey(loaded.NETWATCH_SECRET_KEY)) {
    // Older builds generated an unpadded key. It cannot decrypt credentials, so
    // rotate it before any integration attempts and keep the file private.
    loaded.NETWATCH_SECRET_KEY = generateFernetKey();
    writeEnv(file, loaded);
  }
  return {
    ...defaults,
    ...loaded,
    ...configuredPorts(loaded),
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
      resolve(response.statusCode >= 200 && response.statusCode < 300);
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
    NETWATCH_HOST_SENSOR_URL: `http://127.0.0.1:${config.sensorPort}`,
    // The repository .env is Docker-oriented and may contain the service name
    // `technitium`. A desktop backend runs on the Windows host, so it must not
    // inherit that hostname or its bootstrap password accidentally. Users can
    // configure a different private URL and credential in Settings; the
    // persisted integration remains the source of truth after setup.
    TECHNITIUM_SERVER_URL: config.TECHNITIUM_SERVER_URL || "http://127.0.0.1:5380",
    TECHNITIUM_USERNAME: config.TECHNITIUM_USERNAME || "admin",
    TECHNITIUM_PASSWORD: config.TECHNITIUM_PASSWORD || "",
    TECHNITIUM_DNS_PORT: config.TECHNITIUM_DNS_PORT || "53",
  }));
}

function startSensor() {
  startService("sensor", pythonPath(), ["-m", "uvicorn", "sensor_main:app", "--host", "127.0.0.1", "--port", String(config.sensorPort)], path.join(runtimeRoot, "backend"), childEnv());
}

function startFrontend() {
  const server = path.join(runtimeRoot, "frontend", ".next", "standalone", "server.js");
  if (!existsSync(server)) return false;
  const command = process.execPath;
  const args = app.isPackaged
    ? [server]
    : [path.join(repoRoot, "frontend", "scripts", "start-standalone.mjs")];
  const cwd = app.isPackaged
    ? path.join(runtimeRoot, "frontend", ".next", "standalone")
    : path.join(runtimeRoot, "frontend");
  startService("frontend", command, args, cwd, childEnv({
    HOSTNAME: "127.0.0.1", PORT: String(config.frontendPort),
    NEXT_PUBLIC_API_URL: `http://127.0.0.1:${config.backendPort}`,
    NEXT_PUBLIC_WS_URL: `ws://127.0.0.1:${config.backendPort}/ws`,
    NETWATCH_INTERNAL_API_URL: `http://127.0.0.1:${config.backendPort}`,
    NETWATCH_INTERNAL_WS_URL: `ws://127.0.0.1:${config.backendPort}/ws`,
    ELECTRON_RUN_AS_NODE: "1",
  }));
  return true;
}

async function startAll() {
  if (quitting) throw new Error("NetWatch is shutting down.");
  if (app.isPackaged) {
    await runCommand(
      pythonPath(),
      ["-m", "alembic", "upgrade", "head"],
      path.join(runtimeRoot, "backend"),
      childEnv(),
    );
  }
  if (quitting) throw new Error("NetWatch is shutting down.");
  startSensor();
  startBackend();
  const sensorReady = await waitForHealth(config.sensorPort, "/health");
  const backendReady = await waitForHealth(config.backendPort, "/api/health");
  const frontendStarted = startFrontend();
  const frontendReady = frontendStarted
    ? await waitForHealth(config.frontendPort, "/api/health")
    : false;
  const failures = [];
  if (!sensorReady) failures.push("sensor");
  if (!backendReady) failures.push("backend");
  if (!frontendStarted || !frontendReady) failures.push("frontend");
  return {
    sensorReady,
    backendReady,
    frontendStarted,
    frontendReady,
    failures,
    python: pythonPath(),
    services: [...services.keys()],
  };
}

async function status() {
  const current = {
    sensor: await healthCheck(config.sensorPort, "/health"),
    backend: await healthCheck(config.backendPort, "/api/health"),
    frontend: await healthCheck(config.frontendPort, "/api/health"),
    frontendBuilt: existsSync(path.join(runtimeRoot, "frontend", ".next", "standalone", "server.js")),
    python: pythonPath(),
  };
  return configError
    ? { ...current, error: `Invalid desktop configuration: ${configError}`, failures: ["sensor", "backend", "frontend"] }
    : current;
}

async function stopAll() {
  if (stopInFlight) return stopInFlight;
  stopInFlight = Promise.all([...services.entries()].map(([name, child]) => new Promise((resolve) => {
    if (child.exitCode !== null || child.signalCode !== null) {
      services.delete(name);
      resolve();
      return;
    }
    let settled = false;
    let forceTimer;
    const isRunning = () => child.exitCode === null && child.signalCode === null;
    const finish = () => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (forceTimer) clearTimeout(forceTimer);
      services.delete(name);
      resolve();
    };
    const timer = setTimeout(() => {
      if (isRunning()) {
        writeLog(`[${name}] graceful stop timed out; forcing exit`);
        child.kill("SIGKILL");
      }
      forceTimer = setTimeout(() => {
        if (isRunning()) writeLog(`[${name}] force stop did not report an exit before timeout`);
        finish();
      }, 1000);
    }, 3000);
    child.once("exit", finish);
    child.kill();
  }))).finally(() => { stopInFlight = undefined; });
  return stopInFlight;
}

function cancelFrontendReadiness() {
  readinessGeneration += 1;
  readinessMonitor?.cancel();
  readinessMonitor = undefined;
}

function beginFrontendReadiness(started) {
  cancelFrontendReadiness();
  if (!started.frontendStarted || started.frontendReady) return;
  const generation = readinessGeneration;
  readinessMonitor = createReadinessMonitor({
    probe: () => healthCheck(config.frontendPort, "/api/health"),
    isCurrent: () => !quitting && generation === readinessGeneration && mainWindow && !mainWindow.isDestroyed(),
    onReady: async () => {
      if (generation !== readinessGeneration || !mainWindow || mainWindow.isDestroyed()) return;
      const recovered = { ...started, frontendReady: true, failures: started.failures.filter((failure) => failure !== "frontend") };
      mainWindow.webContents.send("desktop-state", { started: recovered, config: publicConfig() });
      if (dashboardNavigationGeneration === generation) return;
      dashboardNavigationGeneration = generation;
      try {
        await mainWindow.loadURL(`http://127.0.0.1:${config.frontendPort}`);
      } catch (error) {
        writeLog(`Frontend recovery navigation failed: ${error instanceof Error ? error.stack || error.message : String(error)}`);
      }
    },
    onTimeout: () => writeLog(`Frontend did not become healthy during the startup grace period (generation=${generation}).`),
  });
  readinessMonitor.start();
}

async function createWindow() {
  configError = undefined;
  try {
    config = prepareConfig();
  } catch (error) {
    config = defaults;
    configError = error instanceof Error ? error.message : String(error);
  }
  logPath = path.join(config.userData || repoRoot, "desktop.log");
  writeLog(`Starting NetWatch desktop (packaged=${app.isPackaged})`);
  mkdirSync(path.join(runtimeRoot, "backend", "data"), { recursive: true });
  mainWindow = new BrowserWindow({ width: 1180, height: 760, minWidth: 900, minHeight: 600, webPreferences: { preload: path.join(__dirname, "preload.cjs"), contextIsolation: true, sandbox: true } });
  let started;
  try {
    if (configError) throw new Error(`Invalid desktop configuration: ${configError}`);
    started = await startAll();
  } catch (error) {
    writeLog(`NetWatch services could not be started: ${error instanceof Error ? error.stack || error.message : String(error)}`);
    started = {
      sensorReady: false,
      backendReady: false,
      frontendStarted: false,
      frontendReady: false,
      failures: ["sensor", "backend", "frontend"],
      services: [...services.keys()],
      error: error instanceof Error ? error.message : String(error),
    };
  }
  await mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"));
  mainWindow.webContents.send("desktop-state", { started, config: publicConfig() });
  if (started.frontendReady) {
    cancelFrontendReadiness();
    dashboardNavigationGeneration = readinessGeneration;
    await mainWindow.loadURL(`http://127.0.0.1:${config.frontendPort}`);
  } else {
    beginFrontendReadiness(started);
  }
  mainWindow.on("closed", () => { cancelFrontendReadiness(); mainWindow = undefined; });
}

ipcMain.handle("netwatch:status", status);
ipcMain.handle("netwatch:open-dashboard", () => shell.openExternal(`http://127.0.0.1:${config.frontendPort}`));
ipcMain.handle("netwatch:restart", async () => {
  if (quitting) throw new Error("NetWatch is shutting down.");
  if (restartInFlight) throw new Error("A restart is already in progress.");
  cancelFrontendReadiness();
  restartInFlight = stopAll().then(async () => {
    if (quitting) throw new Error("NetWatch is shutting down.");
    config = prepareConfig();
    configError = undefined;
    const started = await startAll();
    beginFrontendReadiness(started);
    if (started.frontendReady && mainWindow && !mainWindow.isDestroyed()) {
      dashboardNavigationGeneration = readinessGeneration;
      await mainWindow.loadURL(`http://127.0.0.1:${config.frontendPort}`);
    }
    return started;
  }).catch((error) => {
    configError = error instanceof Error ? error.message : String(error);
    throw error;
  }).finally(() => { restartInFlight = undefined; });
  return restartInFlight;
});

if (hasSingleInstanceLock) {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
  app.whenReady().then(createWindow);
}
app.on("before-quit", (event) => {
  event.preventDefault();
  if (quitting) return;
  quitting = true;
  cancelFrontendReadiness();
  stopAll().finally(() => app.exit(0));
});
app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });

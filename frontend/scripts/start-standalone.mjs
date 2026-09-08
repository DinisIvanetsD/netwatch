import { spawn } from "node:child_process";
import { cpSync, existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const buildRoot = join(process.cwd(), ".next");
const standaloneRoot = join(buildRoot, "standalone");
const serverPath = join(standaloneRoot, "server.js");

if (!existsSync(serverPath)) {
  throw new Error(
    "Standalone build not found. Run npm run build before npm start.",
  );
}

mkdirSync(join(standaloneRoot, ".next"), { recursive: true });
cpSync(join(buildRoot, "static"), join(standaloneRoot, ".next", "static"), {
  recursive: true,
});

const publicDirectory = join(process.cwd(), "public");
if (existsSync(publicDirectory)) {
  cpSync(publicDirectory, join(standaloneRoot, "public"), { recursive: true });
}

const server = spawn(process.execPath, [serverPath], {
  env: { ...process.env, HOSTNAME: process.env.HOSTNAME ?? "0.0.0.0" },
  stdio: "inherit",
});

server.on("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  process.exit(code ?? 1);
});

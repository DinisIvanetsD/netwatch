const DEFAULT_INTERVAL_MS = 500;
const DEFAULT_GRACE_MS = 60_000;

function createReadinessMonitor({
  probe,
  onReady,
  onTimeout,
  intervalMs = DEFAULT_INTERVAL_MS,
  graceMs = DEFAULT_GRACE_MS,
  isCurrent = () => true,
  setTimer = setTimeout,
  clearTimer = clearTimeout,
  now = () => Date.now(),
}) {
  let timer;
  let cancelled = false;
  let settled = false;
  const cancel = () => {
    cancelled = true;
    if (timer) clearTimer(timer);
    timer = undefined;
  };
  const isActive = () => !cancelled && !settled && isCurrent();
  const check = async (deadline) => {
    if (!isActive()) return;
    let ready = false;
    try { ready = await probe(); } catch { ready = false; }
    if (!isActive()) return;
    if (ready) { settled = true; await onReady(); return; }
    if (now() >= deadline) { settled = true; await onTimeout?.(); return; }
    timer = setTimer(() => { void check(deadline); }, intervalMs);
  };
  return {
    start() { if (!cancelled && !settled) void check(now() + graceMs); },
    cancel,
    get settled() { return settled; },
  };
}

module.exports = { createReadinessMonitor };

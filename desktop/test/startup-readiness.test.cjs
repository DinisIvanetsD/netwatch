const test = require("node:test");
const assert = require("node:assert/strict");
const { createReadinessMonitor } = require("../startup-readiness.cjs");

function fakeTimers() {
  let current = 0;
  const timers = [];
  return {
    now: () => current,
    setTimer(callback, delay) { const timer = { callback, at: current + delay, cancelled: false }; timers.push(timer); return timer; },
    clearTimer(timer) { timer.cancelled = true; },
    async advance(ms) {
      current += ms;
      const due = timers.filter((timer) => timer.at <= current);
      timers.splice(0, timers.length, ...timers.filter((timer) => timer.at > current));
      for (const timer of due) if (!timer.cancelled) await timer.callback();
    },
  };
}

const flush = () => new Promise((resolve) => setImmediate(resolve));

test("recovers once when frontend becomes healthy after the initial failure", async () => {
  const clock = fakeTimers();
  let attempts = 0;
  let navigations = 0;
  const monitor = createReadinessMonitor({ probe: async () => ++attempts >= 3, onReady: async () => { navigations += 1; }, intervalMs: 10, graceMs: 100, ...clock });
  monitor.start();
  await flush();
  await clock.advance(0);
  await clock.advance(10);
  await clock.advance(10);
  assert.equal(attempts, 3);
  assert.equal(navigations, 1);
  await clock.advance(100);
  assert.equal(navigations, 1);
});

test("stops probing at the bounded grace timeout", async () => {
  const clock = fakeTimers();
  let attempts = 0;
  let timedOut = 0;
  const monitor = createReadinessMonitor({ probe: async () => { attempts += 1; return false; }, onReady: () => assert.fail("must not become ready"), onTimeout: async () => { timedOut += 1; }, intervalMs: 10, graceMs: 25, ...clock });
  monitor.start();
  await flush();
  await clock.advance(0);
  await clock.advance(10);
  await clock.advance(10);
  await clock.advance(10);
  assert.equal(timedOut, 1);
  assert.equal(attempts, 4);
});

test("cancellation and stale generations prevent readiness callbacks", async () => {
  const clock = fakeTimers();
  let ready = 0;
  let current = true;
  const monitor = createReadinessMonitor({ probe: async () => true, onReady: async () => { ready += 1; }, isCurrent: () => current, intervalMs: 10, graceMs: 100, ...clock });
  monitor.start();
  current = false;
  await flush();
  monitor.cancel();
  await clock.advance(1000);
  assert.equal(ready, 0);
});

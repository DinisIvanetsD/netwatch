# Contributing to NetWatch

Thank you for helping improve NetWatch. Keep all network operations scoped to explicitly configured private networks and avoid features involving stealth, exploitation, credential attacks, or control bypasses.

## Development checks

From `backend`, run:

```bash
ruff format --check .
ruff check .
pytest -q
```

From `frontend`, run:

```bash
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
```

Add an Alembic migration for schema changes and tests for behavior changes. Keep discovery, monitoring, service checks, and alert rules outside API route modules.


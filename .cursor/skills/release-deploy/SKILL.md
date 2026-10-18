# Skill: Release / deploy

1. Ensure CI green (`lint`, unit/integration tests).
2. Confirm `.env` secrets are injected via host/GitHub Actions — never baked into images.
3. `docker compose up --build` with `TRADING_MODE=paper`.
4. Smoke: `/api/health`, setup wizard, one dry `POST /api/run`.
5. Bump version in `pyproject.toml` + `docs/CHANGELOG.md`.
6. Live deploy only with double gate env vars and human confirmation checklist in runbook.

# Repository Guidelines

## Project Structure & Module Organization

This repository is a full-stack template with separate backend and frontend workspaces. The Python API lives in `backend/`, with application code under `backend/src/sighttalk_api/` and tests under `backend/tests/`. The React client lives in `frontend/`, with source code under `frontend/src/`, static assets in `frontend/public/`, and Vite configuration in `frontend/vite.config.ts`. Shared project-level files include `compose.yaml`, `.github/workflows/ci.yml`, `.editorconfig`, and the root `README.md`.

## Build, Test, and Development Commands

Backend commands:

```bash
cd backend
uv sync --dev
uv run uvicorn sighttalk_api.main:app --reload
uv run ruff check .
uv run mypy
uv run pytest
```

Frontend commands:

```bash
cd frontend
npm install
npm run dev
npm run lint
npm run test:run
npm run build
```

Use `docker compose up --build` from the repository root to run both services together.

## Coding Style & Naming Conventions

Use spaces for indentation: 4 spaces for Python and 2 spaces for frontend files, as defined in `.editorconfig`. Python uses Ruff and MyPy with strict typing; prefer explicit types at module boundaries and keep FastAPI routes under `api/v1/`. React uses TypeScript, ESLint, and Prettier. Name React components in PascalCase, hooks with `use` prefixes, tests as `*.test.tsx`, and shared client utilities under `frontend/src/shared/`.

## Testing Guidelines

Backend tests use Pytest and should live in `backend/tests/` with names like `test_health.py`. Frontend tests use Vitest and Testing Library; colocate them near the feature or app code, such as `src/app/App.test.tsx`. Add tests for new API routes, non-trivial UI behavior, and bug fixes. Run both backend and frontend test commands before opening a PR.

## Commit & Pull Request Guidelines

The current history uses Conventional Commits, for example `chore: add gitignore`. Follow `<type>: <description>` with types such as `feat`, `fix`, `test`, `docs`, `chore`, or `ci`. Keep commits focused on one logical change.

Pull requests should include a concise summary, test results, linked issues when applicable, and screenshots for visible frontend changes. Mention any configuration, migration, or deployment impact explicitly.

## Security & Configuration Tips

Do not commit `.env` files or secrets. Use `.env.example` files as documented templates. Keep dependency lockfiles (`backend/uv.lock`, `frontend/package-lock.json`) updated when changing dependencies.

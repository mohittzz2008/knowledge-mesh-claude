# Knowledge Mesh

Connect the coding platforms you use; Knowledge Mesh turns your public activity into a skill map, a learning path and practice recommendations.

**Platforms:** GitHub, LeetCode, HackerRank, Codeforces, AtCoder, CodeChef, Codewars, GeeksforGeeks, Exercism.

> GeeksforGeeks has no public API. Its connector reads the public profile page (`__NEXT_DATA__`) and raises a clear "layout changed" error if the site changes. Treat it as best-effort.

## Run it

```bash
# backend (Python 3.11+)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # set DATABASE_URL (+ auth settings, see below)
alembic upgrade head
uvicorn app.main:app --reload   # http://localhost:8000

# frontend
cd frontend
npm install
# create frontend/.env.local with NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY, CLERK_SECRET_KEY, NEXT_PUBLIC_BACKEND_URL
npm run dev                     # http://localhost:3000
```

## Auth

With `CLERK_JWKS_URL` set, the backend verifies the Clerk session JWT (`Authorization: Bearer ...`). Without it, it falls back to trusting `X-Clerk-User-Id` for local development only; set `ALLOW_INSECURE_DEV_AUTH=false` for anything public.

## Tests

```bash
cd backend && pytest        # uses DATABASE_URL if configured, otherwise a temporary SQLite file
RUN_LIVE_TESTS=1 pytest     # also runs tests that call the real third-party APIs
cd frontend && npx tsc --noEmit && npm run lint && npm run build
```

## Adding a platform

1. Write a connector in `backend/app/services/platform/` that extends `BasePlatformConnector` (use `http_util.py` for requests and typed errors).
2. Register it in `platform/__init__.py` with `PlatformRegistry.register(...)`.
3. Add a skill-tag mapping in `mesh/concept_extractor.py` if its tags are new.

The platforms page, dashboard, skill mesh and coach read the registry, so no frontend change is needed (optionally add a two-letter mark in `frontend/lib/platforms.ts`).

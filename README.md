# CMHoC-Polsim

A Django site for a Canadian "Model House of Commons" simulation: forums, parties,
elections, bills/voting, moderation, press, scoring, an internal Twitter-style app
("chirps"), and AI-driven NPC characters.

- **Backend**: Django 5.1, PostgreSQL (SQLite for local dev)
- **Static/media**: Whitenoise for static files; media (avatars, bill/constitution
  PDFs) on Google Cloud Storage in production, local disk in dev
- **NPCs**: `google-genai`, backed by Ollama (dev) or Vertex AI/Gemini (prod)
- **Server**: gunicorn behind a Cloudflare Tunnel, run via Docker Compose

## Prerequisites

- Python 3.11+
- Git
- Docker + Docker Compose (only needed for the production-style stack, not for local dev)

## Developing locally

No Docker, Postgres, or GCP account needed.

1. Create and activate a venv, then install deps:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate      # Windows
   pip install -r requirements.txt
   ```
2. Copy the dev env template and fill in a secret key:
   ```bash
   copy .env.dev.example .env
   python -c "import secrets; print(secrets.token_urlsafe(50))"
   ```
   Paste the generated value in as `SECRET_KEY` in `.env`.
3. Run migrations and create an admin user:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```
4. Start the server:
   ```bash
   python manage.py runserver
   ```
5. Visit http://localhost:8000/ and http://localhost:8000/admin/.

With `.env.dev.example`'s defaults, the app uses SQLite and writes uploaded
media to a local `media/` folder, and NPCs are disabled (`NPCS_ENABLED=False`)
so you don't need Ollama running. To try NPCs locally, set `NPCS_ENABLED=True`,
run `ollama serve`, and `ollama pull llama3.1` (or whichever model you set
`OLLAMA_MODEL` to).

## Deploying

Production runs via Docker Compose on a VM, fronted by a Cloudflare Tunnel
(`cloudflared` service) with no open inbound ports.

**Normal flow**: push to `main`. A GitHub Actions workflow
(`.github/workflows/docker-publish.yml`) builds the image and pushes it to
`ghcr.io/adrianmk98/cmhoc-polsim`. The `watchtower` service already running on
the VM polls every 5 minutes and restarts `web` automatically when a new image
is available — no SSH needed for a normal code change.

**To force it immediately** (or for the first deploy after this change),
on the VM:
```bash
docker compose pull web
docker compose up -d
```

**One-time setup on the VM**, before the first deploy with this image-based
flow:

- Either make the `cmhoc-polsim` GHCR package public (repo → Packages →
  package settings → Change visibility) so nothing needs to authenticate, or
  log the VM's Docker daemon in to the registry once — `watchtower` reuses
  this same login to pull automatically, so this one command covers both
  manual and automatic pulls:
  ```bash
  docker login ghcr.io -u <your-github-username>
  # password: a GitHub Personal Access Token with the read:packages scope
  ```
- Make sure `.env` on the VM is populated from `.env.example` (DB password,
  GCP settings, Cloudflare tunnel token, etc.) — this is separate from the dev
  `.env.dev.example` and is never committed to the repo.
- Push to `main` at least once (or trigger the workflow manually from the
  Actions tab) so an image actually exists in GHCR before the first
  `docker compose up -d`.

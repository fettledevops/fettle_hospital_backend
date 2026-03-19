# Fettle Production Infrastructure and CI/CD Setup

Updated for the current repository layout on 2026-03-19.

## Purpose

This document is the current deployment runbook for the backend infrastructure.

It reflects the infrastructure that exists in this repository today:

- Docker Compose based dev and prod profiles
- Django + Celery + Redis runtime
- PostgreSQL in Docker for dev and external PostgreSQL/RDS for prod
- LiveKit server and LiveKit SIP bridge as separate services
- GitHub Actions based continuous testing

It also documents the target direction for full CI/CD.

## What Changed Since the Older Setup

The repository is no longer purely a manual EC2 + systemd deployment story.

Current state in the repo:

- `docker-compose.yml` defines `dev` and `prod` profiles
- `Dockerfile` builds dedicated `dev` and `prod` targets
- `entrypoint.sh` runs migrations automatically and collects static files when `DEBUG=False`
- `.github/workflows/continuous-testing.yml` already runs tests on every push and pull request

Legacy artifacts still exist:

- `fettle_backend.service`
- `fettle_celery.service`
- `livekit-server.service`
- `livekit-sip.service`

Treat those systemd units as fallback or migration-era references, not the primary deployment path.

## Current Runtime Topology

### Development

Development is containerized with the `dev` profile:

- `db`: local Postgres 16 container
- `redis`: local Redis 7 container
- `web`: Django app using the `dev` target
- `celery`: Celery worker using the `dev` target

Environment source:

- `.env.dev`

Run command:

```bash
docker compose --profile dev up --build
```

### Production

Production is containerized with the `prod` profile:

- `redis`
- `web-prod`
- `celery-prod`
- `livekit-server`
- `livekit-sip`

Environment source:

- `.env.prod`

Run command:

```bash
docker compose --profile prod up --build -d
```

Important production details from the current repo:

- `web-prod` uses the `prod` image target but `docker-compose.yml` overrides the container command to `manage.py runsslserver`
- the base `prod` image in `Dockerfile` defaults to `gunicorn`, but that is not the active command path in compose today
- `celery-prod` uses `celery -A project worker -l info -P gevent`
- `livekit-server` and `livekit-sip` both run with `network_mode: host`
- production database is expected to be external, configured through `.env.prod`

## Source of Truth Files

Use these files as the current infrastructure source of truth:

- [docker-compose.yml](/workspaces/fettle_hospital_backend/docker-compose.yml)
- [Dockerfile](/workspaces/fettle_hospital_backend/Dockerfile)
- [entrypoint.sh](/workspaces/fettle_hospital_backend/entrypoint.sh)
- [.env.dev](/workspaces/fettle_hospital_backend/.env.dev)
- [.env.prod](/workspaces/fettle_hospital_backend/.env.prod)
- [docs/ASTERISK_CONFIG.md](/workspaces/fettle_hospital_backend/docs/ASTERISK_CONFIG.md)
- [.github/workflows/continuous-testing.yml](/workspaces/fettle_hospital_backend/.github/workflows/continuous-testing.yml)

## Required Secrets and Environment Variables

Production depends on these groups being populated in `.env.prod` or, preferably, an external secret store:

### Django

- `DEBUG=False`
- `SECRET_KEY`
- `ALLOWED_HOSTS`

### Database

- `DB_HOST`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_PORT`
- `DB_SSL_MODE=require`

### Redis / Celery

- `CELERY_BROKER_URL`

### AWS

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_STORAGE_BUCKET_NAME`
- `AWS_S3_REGION_NAME`
- `LIVEKIT_BUCKET_NAME`

### OpenAI / LiveKit

- `OPENAI_API_KEY`
- `LIVEKIT_URL`
- `LIVEKIT_WS_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `LIVEKIT_KEYS`
- `LIVEKIT_SIP_TRUNK_ID`

### Internal loopback auth for Celery callbacks

- `INTERNAL_API_BASE_URL`
- `INTERNAL_API_EMAIL`
- `INTERNAL_API_PASSWORD`

## Missing Repo-Managed Runtime Assets

The repository currently expects some runtime configuration that is not checked into this workspace:

- `/app/config/tls/fullchain.pem`
- `/app/config/tls/privkey.pem`
- `config/livekit/livekit.yaml`
- `config/livekit/sip.yaml`

Why this matters:

- `docker-compose.yml` mounts TLS files into the `runsslserver` command path
- `docker/livekit-server.Dockerfile` copies `config/livekit/livekit.yaml`
- `docker/livekit-sip.Dockerfile` copies `config/livekit/sip.yaml`

Before a production deployment or CI/CD cutover, these files must either:

1. be added through a secure deployment artifact flow, or
2. be mounted at deploy time from the host or secret storage

Do not commit private certificates or provider secrets into the repository.

## Production Deployment Steps

### Recommended path: Compose-based deployment

1. Provision the host with Docker Engine and the Compose plugin.
2. Place production secrets on the host without committing them to git.
3. Ensure the missing runtime assets listed above are present.
4. Pull the release commit or prebuilt images.
5. Run:

```bash
docker compose --profile prod pull
docker compose --profile prod up -d --build
```

6. Verify:

- web container is healthy and reachable
- Celery worker is connected to Redis
- database migrations completed through `entrypoint.sh`
- LiveKit server is reachable on configured ports
- LiveKit SIP bridge is connected to LiveKit

### Recommended host/network prerequisites

- expose `8000` only if SSL termination stays inside Django
- if using a reverse proxy or load balancer, prefer terminating TLS there and moving the app to Gunicorn
- open LiveKit ports from `.env.prod` and provider-required SIP/RTP ports
- allow the production host to reach RDS, S3, OpenAI, and LiveKit dependencies

## LiveKit and SIP Notes

The repo currently supports LiveKit server and SIP as production services, but there is a documentation gap to be aware of:

- the code defines `LiveKitWebhook` in [phone_calling/views.py](/workspaces/fettle_hospital_backend/phone_calling/views.py)
- there is currently no matching route in [project/urls.py](/workspaces/fettle_hospital_backend/project/urls.py)

Because of that, do not configure a production LiveKit webhook to `/api/livekit_webhook/` yet. That URL is mentioned in the older doc set but is not currently active in the codebase.

Current working assumption:

- outbound call processing is triggered through existing API flows and Celery tasks
- automatic webhook-based post-call processing needs a routed endpoint before it can be treated as production-ready

## Asterisk and SIP Bridging

If you are running Asterisk alongside LiveKit SIP and CloudConnect, use:

- [docs/ASTERISK_CONFIG.md](/workspaces/fettle_hospital_backend/docs/ASTERISK_CONFIG.md)

That document has been updated to be template-safe. Replace all placeholder values with actual production values through secure secret management.

## Current CI Status

The repository already has a basic CI workflow:

- workflow: [continuous-testing.yml](/workspaces/fettle_hospital_backend/.github/workflows/continuous-testing.yml)
- triggers on every push and pull request
- sets up Python 3.12
- installs dependencies from `requirements.txt`
- runs `python run_tests.py`

This is continuous testing, not full CI/CD yet.

## Target Full CI/CD Model

Recommended target state:

### CI

On every pull request and push to protected branches:

1. install dependencies
2. run tests
3. optionally run lint/format checks
4. build Docker images
5. publish versioned images for release branches or tags

### CD

For `main` or release tags:

1. build and push app images to a registry such as GHCR or ECR
2. deploy to the production host using a non-interactive workflow
3. run `docker compose --profile prod pull`
4. run `docker compose --profile prod up -d`
5. verify service readiness
6. notify on success or rollback on failure

### Secret handling

Move away from long-lived secrets in checked-in env files.

Preferred options:

- GitHub Actions secrets for CI/CD orchestration
- AWS Systems Manager Parameter Store
- AWS Secrets Manager
- host-level `.env.prod` injected outside git

## Recommended CI/CD Migration Plan

### Phase 1: Harden CI

- keep the existing test workflow
- add branch protection for the main branch
- add dependency caching and optional linting
- fail PRs if tests do not pass

### Phase 2: Container registry

- build the backend image in GitHub Actions
- push versioned images to GHCR or ECR
- stop relying on in-place host builds for every release

### Phase 3: Production deploy automation

- add a deployment workflow triggered by `main` merges or version tags
- have the deployment workflow connect to the host and run compose updates, or trigger a pull-based deployment agent
- use immutable image tags per release

### Phase 4: Runtime cleanup

- decide whether production will keep `runsslserver` or move fully to `gunicorn`
- if moving to a reverse proxy, remove app-managed TLS from the Django container path
- retire legacy systemd units once Compose deployment is stable

## Legacy Systemd Units

These files still exist in the repository:

- [fettle_backend.service](/workspaces/fettle_hospital_backend/fettle_backend.service)
- [fettle_celery.service](/workspaces/fettle_hospital_backend/fettle_celery.service)
- [livekit-server.service](/workspaces/fettle_hospital_backend/livekit-server.service)
- [livekit-sip.service](/workspaces/fettle_hospital_backend/livekit-sip.service)

They are useful as references during migration, but they are not aligned with the container-first direction of the repo.

If you keep them temporarily:

- ensure they match the current env var contract
- avoid mixing systemd-managed services with compose-managed equivalents on the same host

## Operational Checklist

Before declaring production ready:

- `.env.prod` is fully populated with real secrets
- TLS assets exist and are mounted correctly
- LiveKit config files exist and are mounted correctly
- RDS connectivity is confirmed
- Redis connectivity is confirmed
- S3 read/write works
- OpenAI calls work from the Celery worker
- outbound and inbound call paths are tested end to end
- CI passes on the release commit
- deployment is repeatable without `git reset --hard`

## Summary

Primary recommendation:

- use Docker Compose as the production deployment mechanism
- keep GitHub Actions as CI
- evolve to image-based CD next
- treat the old systemd instructions as legacy fallback only

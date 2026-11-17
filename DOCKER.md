# Docker hardening lab (Ubuntu)

The Compose setup works with Docker Engine and the Docker Compose v2 plugin on
an Ubuntu host. The image uses the official Python 3.12 slim Linux image; it
does not require a Windows host. The API binds only to localhost, and SQLite
persists in the `ticketing-data` Docker volume.

## Prerequisites

- Ubuntu with Docker Engine and Docker Compose v2 installed
- `curl` and `openssl`
- Permission to run `docker` without `sudo` (for example, membership in the
  `docker` group; note that Docker group membership grants root-equivalent
  privileges)

From the project directory, create local settings and a private secret:

```bash
cp -n .env.example .env
sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$(openssl rand -hex 32)/" .env
chmod +x scripts/ticketing-script.sh
```

Do not commit `.env`. The script also creates it and generates a secret if it
is missing.

## Automated commands

```bash
./scripts/ticketing-script.sh harden
./scripts/ticketing-script.sh weak
./scripts/ticketing-script.sh test harden
./scripts/ticketing-script.sh test weak
./scripts/ticketing-script.sh status
./scripts/ticketing-script.sh stop
```

`harden` and `weak` each build and start that mode, wait for the Docker health
check, call `GET /health`, and verify the effective settings with `docker
inspect`. Only one mode runs at a time; both use `127.0.0.1:8000`. `stop`
preserves both SQLite volumes.

## Before/after security demonstration

```bash
./scripts/ticketing-script.sh demo
```

The script starts the intentionally insecure `compose.weak.yaml` mode and
verifies that HTTP works while the process runs as root with a writable
filesystem. It then stops that mode, starts the hardened Compose service, and
verifies compliance.

The hardened container:

- Runs as the unprivileged `app` user.
- Uses a read-only root filesystem; `/app/data` and `/tmp` are the only
  writable locations.
- Drops all Linux capabilities and enables `no-new-privileges`.
- Publishes HTTP only on `127.0.0.1` and uses a private bridge network.
- Provides an automatic `/health` Docker health check.

Capture the script output as test evidence. Inspect the effective Compose
configuration with:

```bash
docker compose -p ticketing-harden -f compose.yaml config
docker compose -p ticketing-weak -f compose.weak.yaml config
```

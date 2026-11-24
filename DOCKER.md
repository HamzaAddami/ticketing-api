# Docker hardening lab (Ubuntu)

The Compose setup works with Docker Engine and the Docker Compose v2 plugin on
an Ubuntu host. The image uses the official Python 3.12 slim Linux image; it
does not require a Windows host. The API is published on all host IPv4
interfaces at port 8000 so it can be reached through the host's LAN IP.
Restrict access with the host firewall and use only on a trusted network; the
API uses HTTP without TLS. SQLite persists in the `ticketing-data` Docker
volume.

## Prerequisites

- Ubuntu with Docker Engine and Docker Compose v2 installed
- `curl` and `openssl`
- Permission to run `docker` without `sudo` (for example, membership in the
  `docker` group; note that Docker group membership grants root-equivalent
  privileges)

From the project directory, create local settings and a private secret:

```bash
cd ticketing-api
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
inspect`. The script retrieves the running API container ID with Compose and
passes that ID to `docker inspect` to display its user, health, published
ports, filesystem, capabilities, security options, and mounts. Only one mode
runs at a time; both publish port 8000 on all host IPv4 interfaces. From
another device on the same network, open
`http://<host-lan-ip>:8000/health`. `stop` preserves both SQLite volumes.

To inspect the configuration manually during a test:

```bash
./scripts/ticketing-script.sh test harden
CONTAINER_ID="$(docker compose -p ticketing-harden -f compose.yaml ps --quiet api)"
docker inspect --format 'ID: {{.Id}}
Name: {{.Name}}
User: {{.Config.User}}
Health: {{if .State.Health}}{{.State.Health.Status}}{{else}}not configured{{end}}
Published ports: {{json .NetworkSettings.Ports}}
Read-only root filesystem: {{.HostConfig.ReadonlyRootfs}}
Capabilities dropped: {{json .HostConfig.CapDrop}}
Security options: {{json .HostConfig.SecurityOpt}}
Mounts: {{range .Mounts}}{{.Type}} {{.Source}} -> {{.Destination}} (rw={{.RW}}); {{end}}' "$CONTAINER_ID"
```

For the weak-mode test, use `test weak` and replace the Compose project and file
in the `CONTAINER_ID` command with `-p ticketing-weak -f compose.weak.yaml`.

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
- Publishes HTTP on all host IPv4 interfaces and uses a private bridge network.
- Provides an automatic `/health` Docker health check.

Capture the script output as test evidence. Inspect the effective Compose
configuration with:

```bash
docker compose -p ticketing-harden -f compose.yaml config
docker compose -p ticketing-weak -f compose.weak.yaml config
```

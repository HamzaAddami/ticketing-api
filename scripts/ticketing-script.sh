#!/usr/bin/env bash
set -Eeuo pipefail

action="${1:-test}"
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

secure_compose=(-p ticketing-harden -f compose.yaml)
weak_compose=(-p ticketing-weak -f compose.weak.yaml)

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

check_docker() {
    command -v docker >/dev/null 2>&1 || die "Docker CLI is not installed."
    docker compose version >/dev/null 2>&1 || die "Install the Docker Compose v2 plugin."
    docker info >/dev/null 2>&1 || die "Docker is unavailable or your user lacks permission to access it."
}

ensure_env() {
    if [[ ! -f .env ]]; then
        command -v openssl >/dev/null 2>&1 || die "Install openssl to generate a SECRET_KEY."
        cp .env.example .env
        secret="$(openssl rand -hex 32)"
        sed -i "s/^SECRET_KEY=.*/SECRET_KEY=${secret}/" .env
        printf 'Created .env with a generated local SECRET_KEY.\n'
    elif grep -q '^SECRET_KEY=replace-this-with-' .env; then
        command -v openssl >/dev/null 2>&1 || die "Install openssl to generate a SECRET_KEY."
        secret="$(openssl rand -hex 32)"
        sed -i "s/^SECRET_KEY=.*/SECRET_KEY=${secret}/" .env
        printf 'Replaced the example SECRET_KEY in .env.\n'
    fi
}

compose() {
    docker compose "$@"
}

compose_mode() {
    local compose_name="$1"
    shift
    local -n compose_files=$compose_name
    compose "${compose_files[@]}" "$@"
}

container_id() {
    local -n compose_files=$1
    local id
    id="$(compose "${compose_files[@]}" ps --quiet api)"
    [[ -n "$id" ]] || die "API container was not found. Start the service first."
    printf '%s' "$id"
}

show_container_config() {
    local id="$1"
    printf '\n=== Docker configuration for container %s ===\n' "$id"
    docker inspect --format 'Name: {{.Name}}
ID: {{.Id}}
Image: {{.Config.Image}}
State: {{.State.Status}}
Health: {{if .State.Health}}{{.State.Health.Status}}{{else}}not configured{{end}}
User: {{if .Config.User}}{{.Config.User}}{{else}}root (default){{end}}
Network mode: {{.HostConfig.NetworkMode}}
Published ports: {{json .NetworkSettings.Ports}}
Read-only root filesystem: {{.HostConfig.ReadonlyRootfs}}
Capabilities dropped: {{json .HostConfig.CapDrop}}
Security options: {{json .HostConfig.SecurityOpt}}
Mounts: {{range .Mounts}}{{.Type}} {{.Source}} -> {{.Destination}} (rw={{.RW}}); {{end}}' "$id"
}

wait_for_api() {
    local compose_name="$1"
    local -n compose_files=$compose_name
    local id health attempt

    for attempt in $(seq 1 45); do
        id="$(compose "${compose_files[@]}" ps --quiet api 2>/dev/null || true)"
        if [[ -n "$id" ]]; then
            health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$id" 2>/dev/null || true)"
            if [[ "$health" == "unhealthy" ]]; then
                compose "${compose_files[@]}" logs api || true
                printf 'ERROR: Docker health check failed.\n' >&2
                return 1
            fi
            if [[ "$health" == "healthy" ]] &&
                curl --fail --silent --max-time 3 http://127.0.0.1:8000/health >/dev/null 2>&1; then
                return 0
            fi
        fi
        sleep 2
    done

    compose "${compose_files[@]}" logs api || true
    printf 'ERROR: API did not become healthy within 90 seconds.\n' >&2
    return 1
}

assert_non_root() {
    local id="$1"
    local user
    user="$(docker inspect --format '{{.Config.User}}' "$id")"
    if [[ -z "$user" || "$user" == "0" || "$user" == "root" || "$user" == "0:0" ]]; then
        printf 'ERROR: Security check failed: container is running as root.\n' >&2
        return 1
    fi
}

assert_hardened() {
    local id="$1"
    local read_only cap_drop security_opt
    assert_non_root "$id"
    read_only="$(docker inspect --format '{{.HostConfig.ReadonlyRootfs}}' "$id")"
    cap_drop="$(docker inspect --format '{{json .HostConfig.CapDrop}}' "$id")"
    security_opt="$(docker inspect --format '{{json .HostConfig.SecurityOpt}}' "$id")"
    if [[ "$read_only" != "true" ]]; then
        printf 'ERROR: Security check failed: root filesystem is writable.\n' >&2
        return 1
    fi
    if [[ "$cap_drop" != *'"ALL"'* ]]; then
        printf 'ERROR: Security check failed: not all Linux capabilities are dropped.\n' >&2
        return 1
    fi
    if [[ "$security_opt" != *'no-new-privileges:true'* ]]; then
        printf 'ERROR: Security check failed: no-new-privileges is not enabled.\n' >&2
        return 1
    fi
    printf 'PASS: non-root user, read-only root filesystem, all capabilities dropped, no-new-privileges enabled.\n'
}

assert_weak() {
    local id="$1"
    local user read_only cap_drop security_opt
    user="$(docker inspect --format '{{.Config.User}}' "$id")"
    read_only="$(docker inspect --format '{{.HostConfig.ReadonlyRootfs}}' "$id")"
    cap_drop="$(docker inspect --format '{{json .HostConfig.CapDrop}}' "$id")"
    security_opt="$(docker inspect --format '{{json .HostConfig.SecurityOpt}}' "$id")"

    if [[ "$user" != "0" && "$user" != "0:0" && "$user" != "root" ]]; then
        printf 'ERROR: Weak-mode check failed: container is not running as root.\n' >&2
        return 1
    fi
    if [[ "$read_only" != "false" ]]; then
        printf 'ERROR: Weak-mode check failed: root filesystem is not writable.\n' >&2
        return 1
    fi
    if [[ "$cap_drop" != "null" && "$cap_drop" != "[]" ]]; then
        printf 'ERROR: Weak-mode check failed: capabilities are still being dropped.\n' >&2
        return 1
    fi
    if [[ "$security_opt" == *'no-new-privileges:true'* ]]; then
        printf 'ERROR: Weak-mode check failed: no-new-privileges is enabled.\n' >&2
        return 1
    fi
    printf 'EXPECTED WEAK MODE: root user, writable root filesystem, default capabilities.\n'
}

stop_modes() {
    compose "${weak_compose[@]}" down
    compose "${secure_compose[@]}" down
}

start_mode() {
    local mode="$1"
    local compose_name
    local id

    if [[ "$mode" == "harden" ]]; then
        compose_name="secure_compose"
    else
        compose_name="weak_compose"
    fi

    stop_modes
    compose_mode "$compose_name" up --detach --build --force-recreate
    wait_for_api "$compose_name"
    id="$(container_id "$compose_name")"
    show_container_config "$id"

    if [[ "$mode" == "harden" ]]; then
        assert_hardened "$id"
    else
        assert_weak "$id"
    fi
    curl --fail --silent --show-error http://127.0.0.1:8000/health
    printf '\nPASS: %s mode passed HTTP and security checks.\n' "$mode"
}

run_demo() {
    start_mode weak
    start_mode harden
    printf 'PASS: weak mode was identified and hardened mode is now running.\n'
}

case "$action" in
    start|harden|weak|test|demo|status|stop) ;;
    *) die "Usage: $0 {harden|weak|test [harden|weak]|status|stop|demo}" ;;
esac

check_docker
ensure_env

case "$action" in
    start)
        start_mode harden
        ;;
    harden)
        start_mode harden
        ;;
    weak)
        start_mode weak
        ;;
    test)
        mode="${2:-harden}"
        [[ "$mode" == "harden" || "$mode" == "weak" ]] ||
            die "Usage: $0 test {harden|weak}"
        start_mode "$mode"
        ;;
    status)
        compose "${secure_compose[@]}" ps
        compose "${weak_compose[@]}" ps
        ;;
    stop)
        stop_modes
        ;;
    demo)
        run_demo
        ;;
esac

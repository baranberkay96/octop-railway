#!/bin/sh
# shellcheck shell=sh
# Octop on Railway. Railway's init (podman-init) is PID 1; this script is its
# child and ends by exec'ing `octop run`, so the container lives and dies with
# Octop and Railway's restart policy covers crashes and exits.
#
#  1. Checks PORT, the volume and the environment; caps CPU thread pools.
#  2. Waits for Postgres (when OCTOP_DATABASE_URL is set).
#  3. railway_setup.py: migrations, admin account from variables (fails
#     closed, no setup wizard), first-boot security policy, TLS guard.
#  4. Removes the admin variables from the environment the app (and every
#     agent's shell) inherits.
#  5. Forwards Octop's file log to stdout, then exec's `octop run`.
set -eu

THREAD_CAP=8
DB_WAIT_SECONDS_DEFAULT=540

log() {
    printf '[railway] %s\n' "$*" >&2
}

die() {
    printf '[railway] FATAL: %s\n' "$*" >&2
    exit 1
}

is_true() {
    case "$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')" in
        true|1|yes|on) return 0 ;;
    esac
    return 1
}

# CPU quota of this container (cgroup v2, then v1), else nproc; capped.
# Railway hosts expose all host cores to nproc while the service only gets a
# share of them (STANDARD Rule 8.15).
cpu_threads() {
    n=""
    if [ -r /sys/fs/cgroup/cpu.max ]; then
        read -r quota period < /sys/fs/cgroup/cpu.max || true
        case "${quota:-}:${period:-}" in
            *[!0-9:]*|:*|*:) ;;
            *) if [ "$period" -gt 0 ]; then n=$(( (quota + period - 1) / period )); fi ;;
        esac
    elif [ -r /sys/fs/cgroup/cpu/cpu.cfs_quota_us ] && [ -r /sys/fs/cgroup/cpu/cpu.cfs_period_us ]; then
        quota=$(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us)
        period=$(cat /sys/fs/cgroup/cpu/cpu.cfs_period_us)
        case "${quota}:${period}" in
            *[!0-9:]*|:*|*:) ;;
            *) if [ "$period" -gt 0 ]; then n=$(( (quota + period - 1) / period )); fi ;;
        esac
    fi
    if [ -z "$n" ]; then
        n=$(nproc 2>/dev/null || echo 1)
    fi
    case "$n" in
        ''|*[!0-9]*) n=1 ;;
    esac
    if [ "$n" -lt 1 ]; then n=1; fi
    if [ "$n" -gt "$THREAD_CAP" ]; then n=$THREAD_CAP; fi
    printf '%s' "$n"
}

# pg_isready exit codes: 0 accepting, 1 starting up, 2 no response,
# 3 bad parameters (never retried).
wait_for_postgres() {
    wait_max="${OCTOP_DB_WAIT_SECONDS:-$DB_WAIT_SECONDS_DEFAULT}"
    case "$wait_max" in
        ''|*[!0-9]*) wait_max=$DB_WAIT_SECONDS_DEFAULT ;;
    esac
    started=$(date +%s)
    announced=""
    while :; do
        rc=0
        pg_isready -q -t 5 -d "$OCTOP_DATABASE_URL" || rc=$?
        case "$rc" in
            0) log "Postgres is accepting connections"; return 0 ;;
            3) die "OCTOP_DATABASE_URL is not a valid PostgreSQL connection URL" ;;
        esac
        waited=$(( $(date +%s) - started ))
        if [ "$waited" -ge "$wait_max" ]; then
            die "Postgres did not accept connections within ${wait_max}s (pg_isready exit ${rc}); the restart policy will retry"
        fi
        if [ -z "$announced" ]; then
            log "waiting for Postgres (up to ${wait_max}s)"
            announced=1
        fi
        sleep 5
    done
}

# Octop's application logs (agents, channels, cron) go to a rotating file on
# the volume only. Forward new lines to stdout so they show up in Railway's
# log view; uvicorn's own lines are already on stdout and are skipped here.
# -F follows the name across Octop's daily and size-based rotation.
start_log_forwarder() {
    log_file="$OCTOP_HOME/logs/octop.log"
    tail -n 0 -F "$log_file" 2>/dev/null | awk '
        /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] / && $5 == "\342\200\224" {
            skip = ($4 ~ /^uvicorn/)
        }
        !skip { print; fflush() }
    ' &
}

# --- 1. Port, paths, environment ---------------------------------------------

PORT="${PORT:-8088}"
case "$PORT" in
    ''|*[!0-9]*) die "PORT must be a port number, got '${PORT}'" ;;
esac
if [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
    die "PORT must be between 1 and 65535, got '${PORT}'"
fi
export PORT
export OCTOP_PORT="$PORT"

export HOME="${HOME:-/data}"
export OCTOP_HOME="${OCTOP_HOME:-$HOME/.octop}"
case "$OCTOP_HOME" in
    /*) ;;
    *) die "OCTOP_HOME must be an absolute path, got '${OCTOP_HOME}'" ;;
esac
mkdir -p "$OCTOP_HOME"
chmod 700 "$OCTOP_HOME"

if ! awk '$5 == "/data" { found = 1 } END { exit !found }' /proc/self/mountinfo 2>/dev/null; then
    log "WARNING: /data is not a mounted volume; workspaces, knowledge bases and uploads are lost on redeploy"
fi

# uvicorn would take the client address from X-Forwarded-For for the peers
# listed here. Octop keys its LDAP-bind and invite throttles on that address,
# so forged headers would bypass them. Keep uvicorn's default (loopback
# only); nothing proxies inside this container.
if [ -n "${FORWARDED_ALLOW_IPS:-}" ]; then
    log "FORWARDED_ALLOW_IPS ignored: forged proxy headers would bypass Octop's per-address throttling"
fi
unset FORWARDED_ALLOW_IPS

# Octop passes this to uvicorn, which refuses unknown level names.
OCTOP_LOG_LEVEL=$(printf '%s' "${OCTOP_LOG_LEVEL:-info}" | tr '[:upper:]' '[:lower:]')
case "$OCTOP_LOG_LEVEL" in
    critical|error|warning|info|debug|trace) ;;
    *) log "OCTOP_LOG_LEVEL '${OCTOP_LOG_LEVEL}' is not valid; using info"; OCTOP_LOG_LEVEL=info ;;
esac
export OCTOP_LOG_LEVEL

threads=$(cpu_threads)
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-$threads}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-$OMP_NUM_THREADS}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-$OMP_NUM_THREADS}"

# --- 2. Database -------------------------------------------------------------

if [ -n "${OCTOP_DATABASE_URL:-}" ]; then
    wait_for_postgres
else
    log "OCTOP_DATABASE_URL is empty: using SQLite on the volume ($OCTOP_HOME/octop.db)"
fi

# --- 3. Setup ------------------------------------------------------------------

cd /app
/app/.venv/bin/python /app/railway/railway_setup.py || die "setup failed (see the lines above); Octop was not started"

# --- 4. Keep the bootstrap credentials out of the app's environment ----------
# Every agent's shell inherits Octop's environment. The admin password is in
# the database now; drop it (and upstream's bootstrap variable, if someone
# set it) so `env` in an agent shell does not print it. A root shell can still
# read the container's initial environment from /proc/1/environ, and the
# database URL must stay (Octop needs it); see TEMPLATE.md, Security model.
unset OCTOP_ADMIN_PASSWORD OCTOP_DEFAULT_PASSWORD OCTOP_ADMIN_USERNAME \
    OCTOP_ADMIN_DISPLAY_NAME OCTOP_ADMIN_LOCALE OCTOP_SECURITY_DEFAULTS \
    OCTOP_DB_WAIT_SECONDS

# --- 5. Start ------------------------------------------------------------------

if is_true "${OCTOP_LOG_TO_STDOUT:-true}"; then
    start_log_forwarder
fi
unset OCTOP_LOG_TO_STDOUT

log "starting Octop on 0.0.0.0:${PORT} (${OMP_NUM_THREADS} CPU threads for numeric libraries)"
# 0.0.0.0, not "::": uvicorn's single-worker asyncio socket on "::" is
# IPv6-only and Railway's healthcheck and edge connect over IPv4 (Rule 8.2).
# `octop run` persists host and port to config.json, as upstream's entrypoint
# does.
exec octop run --host 0.0.0.0 --port "$PORT"

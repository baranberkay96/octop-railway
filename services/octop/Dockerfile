# Octop 1.0.3b1 for Railway: the official image plus a small wrapper.
#
# Nothing of Octop is rebuilt. This layer adds:
#   - railway/: an entrypoint and a setup script that create the admin from
#     Railway variables before the port opens (no setup wizard, no credential
#     file), switch on tool approval and the shell guard on the first boot,
#     wait for Postgres, and send Octop's file log to Railway's log view;
#   - postgresql-client-18 (pg_dump / pg_restore / pg_isready): Octop's
#     dashboard backup calls pg_dump when the control plane is PostgreSQL,
#     and the official image has no client tools;
#   - bubblewrap: Octop installs it with apt at every start otherwise;
#   - Playwright's Chromium with its system libraries, so the browser tool
#     works on the first use and after every redeploy (a browser installed
#     from the dashboard lives in the container layer and is lost).
#
# Pinned by tag and by the multi-arch index digest of
# ghcr.io/tencentcloud/octop:1.0.3b1 (published 2026-10-25, git tag v1.0.3b1,
# commit 890111b7879665840414ca28ab168b05b0db0921). Upgrade: change both and
# the version check below, read the release notes, and rebuild; the build
# fails early if the upstream helpers railway_setup.py imports have moved.
FROM ghcr.io/tencentcloud/octop:1.0.3b1@sha256:2ac082ea72efa8497d67dcf5c2421b90ddbc0e8735fc91e49fdc77f2dd89af47

# HOME=/data is upstream's layout (~/.octop is the state directory). The
# Railway volume is mounted at /data, so Octop's state and HOME caches
# (embedding models, browser profiles) survive redeploys.
ENV HOME=/data \
    OCTOP_HOME=/data/.octop \
    OCTOP_IN_CONTAINER=1 \
    PORT=8088 \
    PYTHONUNBUFFERED=1

# Debian trixie (the python:3.12-slim base of the official image) ships
# PostgreSQL 17 client tools; pg_dump must be at least the server's major
# version (Railway's Postgres template runs 18), so the client comes from the
# PostgreSQL project's own apt repository (PGDG). apt verifies the repository
# signature with the key downloaded over HTTPS.
RUN set -eu; \
    . /etc/os-release; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl bubblewrap; \
    install -d /usr/share/postgresql-common/pgdg; \
    curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
        https://www.postgresql.org/media/keys/ACCC4CF8.asc; \
    echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends postgresql-client-18; \
    python -m playwright install --with-deps chromium; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/* /tmp/*

COPY railway/ /app/railway/
RUN chmod 0755 /app/railway/railway-entrypoint.sh \
    && chmod 0644 /app/railway/railway_setup.py

# Fail the build (not the first boot) when the wrapper, the tools, or the
# upstream helpers it relies on are missing. Imports run with a throwaway
# HOME so nothing is written under /data (the volume is mounted there).
RUN set -eu; \
    sh -n /app/railway/railway-entrypoint.sh; \
    python -m py_compile /app/railway/railway_setup.py; \
    export HOME=/tmp/octop-build OCTOP_HOME=/tmp/octop-build/.octop; \
    python -c "import importlib.metadata as m; v = m.version('octop'); assert v == '1.0.3b1', v"; \
    python -c "from octop.cli.support.db import open_cli_services; from octop.infra.users.password import hash_password, validate_password_policy; from octop.infra.errors import OctopError; from octop.infra.agents.security import policy_store; from octop_harness.security.models import SecurityPolicy; assert policy_store._SETTINGS_KEY == 'security_policy'; assert SecurityPolicy.from_dict(SecurityPolicy.defaults().to_dict()).tool_guard.enabled"; \
    python -c "from octop_browser.install import verify_chromium; ok, msg = verify_chromium(); print(msg); raise SystemExit(0 if ok else 1)"; \
    pg_dump --version | grep -q 'PostgreSQL) 18\.'; \
    pg_isready --version >/dev/null; \
    for tool in octop bwrap tail awk; do \
        command -v "$tool" >/dev/null || { echo "missing in image: $tool" >&2; exit 1; }; \
    done; \
    rm -rf /tmp/octop-build

EXPOSE 8088

# Replaces upstream's docker-entrypoint.sh (first-run wizard fallback,
# plaintext credential.txt on the volume, logs only in a file).
ENTRYPOINT ["/app/railway/railway-entrypoint.sh"]
CMD []

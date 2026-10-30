# NOTICE: Octop template

## Software deployed

| Component | Source | License | How it is used |
|---|---|---|---|
| Octop | https://github.com/TencentCloud/Octop, tag `v1.0.3b1` (commit `890111b7879665840414ca28ab168b05b0db0921`); image `ghcr.io/tencentcloud/octop:1.0.3b1@sha256:2ac082ea72efa8497d67dcf5c2421b90ddbc0e8735fc91e49fdc77f2dd89af47` | MIT License, Copyright (c) 2026 Octop (repository `LICENSE`) | Used unmodified as the base image. Its Python dependencies keep their own licenses; among them octop-harness 1.0.5, octop-gateway 1.0.3 and octop-browser 1.0.0 (MIT, Tencent Cloud's Octop packages on PyPI). |
| PostgreSQL client 18 (`pg_dump`, `pg_restore`, `pg_isready`) | apt.postgresql.org (`trixie-pgdg`) | PostgreSQL License | Installed in the Octop image so dashboard backups work with a PostgreSQL control plane and the entrypoint can wait for the database. |
| Chromium (Playwright build) and its Debian libraries | `python -m playwright install --with-deps chromium` with the Playwright 1.61.0 package already in the image | Chromium: BSD-style and others; Playwright: Apache-2.0; Debian packages: their own licenses | Pre-installed so Octop's browser tool works without a runtime download. |
| bubblewrap | Debian trixie | LGPL-2.0-or-later | Pre-installed; Octop otherwise installs it with apt at every start. |
| PostgreSQL server | `ghcr.io/railwayapp-templates/postgres-ssl:18` (Railway's Postgres template image) | PostgreSQL License (server); Railway's image wrapper: its own license | Control-plane database and agent memory; service definition copied from `templates/_railway-base/postgres.json`. |

Octop, Tencent Cloud, Feishu, DingTalk, WeCom, QQ, WeChat, Telegram and Discord are names of their respective owners. This is a community template and is not affiliated with or endorsed by Tencent Cloud or the Octop maintainers.

MIT License text: https://github.com/TencentCloud/Octop/blob/v1.0.3b1/LICENSE

## Adapted upstream material

No upstream file or text is copied into this package.

- `services/octop/railway/railway-entrypoint.sh` replaces upstream's `docker/docker-entrypoint.sh`. It keeps upstream's run command (`octop run --host 0.0.0.0 --port $PORT`), `HOME=/data`, and the `.initialized` marker name, and was otherwise written for this template.
- `services/octop/railway/railway_setup.py` was written for this template. It calls Octop's own helpers at runtime (`octop.cli.support.db.open_cli_services`, `octop.infra.users.password`, `octop.infra.agents.security.policy_store.SecuritySettingsStore`, `octop_harness.security.models.SecurityPolicy`) the way Octop's CLI commands `octop init`, `octop user passwd` and `octop admin rotate-jwt-secret` do. No upstream code is copied into it.

## Upstream files checked (tag `v1.0.3b1`, released 2026-10-25, checked 2026-10-30)

The local copy in `_upstream/TencentCloud__Octop` matches the tag (blob hashes of `docker/Dockerfile`, `docker/docker-entrypoint.sh`, `pyproject.toml`, `.env.example` and `docs/configuration.md` compared with `gh api repos/TencentCloud/Octop/contents/<path>?ref=v1.0.3b1`; `compare v1.0.3b1...main` shows no commits ahead).

- `docker/Dockerfile`, `docker/docker-entrypoint.sh`, `docker/docker-compose.yml`, `docker/docker-compose.postgres.yml`, `docker/postgres/init-vector.sql`, `docker/README.md`, `.env.example`, `pyproject.toml`, `uv.lock`, `CHANGELOG.md`, `README.md`, `LICENSE`
- `docs/configuration.md`, `docs/adr/001-single-process-model.md`, `docs/adr/002-database-backends.md`, `docs/agent-backend-file-io.md`
- `src/octop/config.py`, `launch.py`, `cli/commands/{init,run,user,admin,channel}.py`, `cli/support/{db,offline_ops}.py`, `infra/server.py`, `infra/db/{factory,pool,services}.py`, `infra/db/repos/{users,settings,secrets}.py`, `infra/crypto/fernet.py`, `infra/users/{password,resource_policy}.py`, `infra/utils/{paths,bwrap,host_dirs}.py`, `infra/backend/{resolver,adapter}.py`, `infra/agents/memory/backend.py`, `infra/agents/security/policy_store.py`, `infra/backup/pg_dump.py`, `infra/knowledge/{index,ocr}.py`, `infra/control/browser/setup.py`, `infra/control/mobile/config_probe.py`, `infra/setup/{password_file,self_update}.py`, `infra/setup/tls/{listeners,store}.py`, `infra/cron/delivery.py`, `api/deps.py`, `api/middleware/{jwt_auth,setup_lockdown}.py`, `api/common/{client_ip,public_base}.py`, `api/routers/{auth,health,setup,invites,security,memory_portable,terminal,update,connectors,internal_mcp}.py`
- From the PyPI wheels pinned in `uv.lock` (read only, not installed): `octop_harness` 1.0.5 (`backends/__init__.py`, `backends/local_shell.py`, `backends/bwrap_shell.py`, `runtime_env.py`, `security/models.py`, `security/tool_guard/*`, `middleware/filesystem_guard.py`, `config/env.py`), `octop_browser` 1.0.0 (`install.py`, `cdp/launcher.py`), `octop_gateway` 1.0.3 (channel transports, `channels/telegram/policy.py`)
- Release notes: https://github.com/TencentCloud/Octop/releases/tag/v1.0.3b1
- Open issues filed after the release that affect this template's choices: #2621 (Remote Android capability enabled without opt-in), #2456 (a pending approval can be lost on restart)

## Market templates reviewed (ideas only, nothing copied)

| Template | Source | Use |
|---|---|---|
| `octop-3` "Octop" | official image `1.0.2` by digest, marketplace config and readme only | Starting point: `/data` volume with `HOME=/data`, `0.0.0.0` bind, `/api/health` healthcheck, generated first-boot password, draining. No text or code copied. |
| `octop-4` "Octop" | official image `:latest`, marketplace config and readme only | Compared; no text or code copied. |
| `octop-1` "Octop" | third-party image `ghcr.io/hmseeb/octop-railway:1.0.0-r2`, marketplace config and readme only (source repository not reviewed, license unknown) | Compared; no text or code copied. |

All template files (TEMPLATE.md, template.json, README.md, this NOTICE, the Dockerfile and the Railway wrapper scripts) were written for this package.

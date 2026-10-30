# Octop v1 Multi-User AI Assistant: Railway template spec

## Listing

| Field | Value |
|---|---|
| Name | **Octop v1 Multi-User AI Assistant** (as assigned; `v1` = major version of the pinned `1.0.3b1`; upstream spelling "Octop") |
| Description | Self-hosted multi-agent AI assistant for teams, with chat apps and tools. (73 chars, unchanged) |
| Category | AI/ML |
| Tags | octop, ai-agent, multi-agent, team-assistant, feishu, dingtalk, wecom, telegram, discord, mcp, postgres |
| Icon | `https://cdn.jsdelivr.net/gh/TencentCloud/Octop@v1.0.3b1/docs/assets/octop-logo.svg` (upstream logo pinned to the tag; HTTP 200 `image/svg+xml` checked) |

**"v1" or "v1 beta"?** "v1" stays. The 1.x line is generally available (1.0.0 on 2026-09-14, 1.0.1, 1.0.2 on 2026-10-18). `1.0.3b1` is a beta build of the 1.0.3 patch, but upstream publishes these betas as ordinary releases (the GitHub release is not marked pre-release, and `:latest` points at it). Calling the listing "v1 beta" would suggest the product line is in beta, which it is not. The beta status of the pinned build is stated in the README (Pinning and upgrades). Why the beta is pinned rather than `1.0.2`: it adds encryption at rest for stored keys and size limits on plugin uploads (release notes, "Security"), and the wrapper's use of Octop internals was checked against this exact tag.

The description holds as written:
- **Multi-agent, for teams**: multi-user accounts (admin-created users and invite links, no public sign-up), each user with their own experts; user groups limit who sees which models, skills, knowledge bases, connectors and experts.
- **Chat apps**: Feishu, DingTalk, WeCom, QQ, WeChat, Telegram and Discord bridges are in the image. All of them connect outwards (WebSocket, stream or long polling), so no inbound port is needed. They are configured per expert in the dashboard; Octop has no environment variables for them.
- **Tools**: shell, files, headless Chromium (pre-installed here), web search, knowledge bases, MCP and OAuth connectors, cron.

## Base market template

| Market template | Source | State on 2026-10-30 | Verdict |
|---|---|---|---|
| `octop-3` "Octop" | official image `ghcr.io/tencentcloud/octop@sha256:c15e792f…` (= `1.0.2`), base64 Python supervisor as start command | 4 projects, 2 active | **Strongest base.** Kept: official image pinned by digest, `/data` volume with `HOME=/data`, `0.0.0.0` bind, `/api/health` healthcheck, generated first-boot password with a fixed letter+digit prefix, draining. Problems: fixed username `admin` (five wrong passwords lock it for 15 minutes, repeatable by anyone); upstream entrypoint writes the password in plain text to `/data/.octop/credential.txt` and leaves it in the app's environment, which every agent shell inherits; tool approval off and the shell guard warn-only (upstream defaults); `LANGFUSE_TRACING_ENABLED=false` disables the dashboard's own Langfuse switch; app logs only in a file on the volume; timezone stays Asia/Shanghai; SQLite only; restart `ON_FAILURE` ×5; `RAILWAY_RUN_UID=0` without effect (the image already runs as root). |
| `octop-4` "Octop" | official image `:latest` | 1 project, 0 active | Unpinned; no healthcheck; username `admin`; volume only on `/data/.octop` (HOME caches lost). |
| `octop-1` "Octop" | third-party image `ghcr.io/hmseeb/octop-railway:1.0.0-r2` | 1 project, 0 active | Third-party build of 1.0.0; `OCTOP_BIND_HOST="::"`; username `admin`; advertises `OPENAI_API_KEY`, which Octop does not use to set up a provider (see Variables). |

Upstream references checked at tag `v1.0.3b1`: `docker/Dockerfile`, `docker/docker-entrypoint.sh`, `docker/docker-compose.yml` (one container, volume at `/data/.octop`, `HOME=/data`, `ulimits nofile 65535`), `docker/docker-compose.postgres.yml`, `docs/configuration.md`, ADR 001 (single process, no queue, no worker) and ADR 002 (SQLite or PostgreSQL control plane). Full list in NOTICE.md.

## Pinned versions

| Component | Source | Version | Released | Checked |
|---|---|---|---|---|
| Octop | `ghcr.io/tencentcloud/octop:1.0.3b1@sha256:2ac082ea72efa8497d67dcf5c2421b90ddbc0e8735fc91e49fdc77f2dd89af47` (multi-arch index; amd64 manifest `sha256:6485f947…`, 16 layers, 1.09 GB compressed) | 1.0.3b1 = git tag `v1.0.3b1`, commit `890111b7879665840414ca28ab168b05b0db0921` (image label `org.opencontainers.image.revision`) | 2026-10-25 | 2026-10-30 |
| PostgreSQL client | `postgresql-client-18` from `apt.postgresql.org` `trixie-pgdg` (18.6 at the time of checking) | 18.x | | 2026-10-30 |
| Postgres | `ghcr.io/railwayapp-templates/postgres-ssl:18` (Railway's Postgres template image, from `templates/_railway-base/postgres.json`) | 18 | | 2026-10-30 |

Image facts read from the registry (config blob): `Entrypoint ["docker-entrypoint.sh"]`, `WorkingDir /app`, runs as root, `HOME=/data`, `OCTOP_BIND_HOST=0.0.0.0`, `OCTOP_PORT=8088`, venv `/app/.venv` first on `PATH`, `PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright`, no `VOLUME`. `:latest` has the same index digest as `1.0.3b1`.

The Octop service is built from `services/octop/Dockerfile` (repo `baranberkay96/octop-railway`, root `/services/octop`): a layer on the pinned image that adds PostgreSQL client 18, bubblewrap, Playwright's Chromium with its libraries, and the `railway/` wrapper. Upgrade: change tag and digest in the Dockerfile, read the release notes, redeploy. The build fails early if the Octop helpers the setup script imports have moved, if the Octop version is not the expected one, or if Chromium cannot start.

## Architecture

```
 Feishu · DingTalk · WeCom · QQ · WeChat · Telegram · Discord ◄── outbound bot connections
                                ▲                                  (no inbound ports)
 ┌──────────────────────────────┴───────────────────────────────────────────────┐
 │ Octop (ghcr.io/tencentcloud/octop:1.0.3b1 + railway/ wrapper)                │
 │  podman-init (PID 1) → railway-entrypoint.sh                                 │
 │   1. checks PORT, /data, FORWARDED_ALLOW_IPS, log level; caps CPU threads    │
 │   2. waits for Postgres (pg_isready)                                         │
 │   3. railway_setup.py: TLS guard · migrations · admin from variables ·       │
 │      first-boot security policy                                              │
 │   4. unsets the admin variables; tail of octop.log → stdout                  │
 │   5. exec octop run --host 0.0.0.0 --port 8088   ← main process              │
 │        dashboard (SPA) + REST/SSE/WebSocket API, JWT auth                    │
 │        experts: shell, files, Chromium, knowledge, MCP, cron, channels       │
 │  volume /data: .octop/agents (workspaces), knowledge (indexes), plugins,     │
 │                avatars, logs, config.json; HOME caches (models, profiles)    │
 └──────────────┬─────────────────────────────────────────┬─────────────────────┘
                │ OCTOP_DATABASE_URL (private network)     │ HTTPS (Railway edge) → :8088
 ┌──────────────┴──────────────────────────┐               healthcheck GET /api/health
 │ Postgres (postgres-ssl:18)              │
 │  control plane: users, experts, channels,│
 │  cron, settings, secrets (Fernet keys,  │
 │  JWT secret), audit; agent memory;      │
 │  LangGraph checkpoints                  │
 │  volume /var/lib/postgresql/data        │
 └─────────────────────────────────────────┘
```

Octop is one process by design (ADR 001: no queue, no worker, no Redis). Upstream's compose file is a single container; the only optional backing service upstream documents is PostgreSQL, which this template includes. Nothing was dropped and nothing was added without a function.

### Where data lives

| Layer (ADR 002) | Here | Notes |
|---|---|---|
| Control plane (users, experts, channels, cron, settings, encrypted keys, JWT secret) | Postgres | Upstream default is SQLite in `~/.octop/octop.db`. PostgreSQL is upstream's documented option for externalized state and concurrent writers; the template still runs on SQLite if `OCTOP_DATABASE_URL` is emptied. |
| Agent memory (octop-memory) and LangGraph checkpoints | Postgres | Upstream default when the control plane is PostgreSQL (shared `octop_memory` tables, one namespace per agent). Uses built-in `tsvector`, so no pgvector image is needed. Trade-off: memory **pack/adopt** (export of one expert's memory as a file) is refused by upstream for PostgreSQL memory; per-expert SQLite memory can still be chosen in that expert's config (`"memory": {"backend": {"type": "sqlite"}}`). |
| Workspaces, knowledge-base indexes (SQLite per knowledge base), uploads, plugins, avatars, logs, embedding-model cache | Volume `/data` | One volume per service; Octop is the only writer. |

Backups: the admin backup page runs `pg_dump -Fc` for PostgreSQL (client 18 is in the image) plus archives of the volume content into `/data/.octop/backups`. That protects against bad upgrades, not against losing the volume; use Railway's volume and database backups for that.

### Workspace backends on Railway

Experts without an explicit backend work on the container's file system (`local_shell` rooted at `/`, workspaces under `/data/.octop/agents/<id>`). That is the default here and needs nothing else. Admin → storage backends offers more types:

| Backend | On Railway |
|---|---|
| Local disk (default), `filesystem`, `shell` | Works (volume). A `shell` backend with a narrowed root uses bubblewrap; whether its namespaces work in Railway containers is unverified. |
| PostgreSQL | Works (can use the same Postgres). |
| S3-compatible (`s3`, `custom`; also COS, OSS, OBS) | Works. A Railway Bucket can be added as an S3 backend (endpoint, bucket, keys from the bucket's variables). Not included by default: nothing in Octop uses it until an admin assigns it to an expert. |
| Docker sandbox | **Not available**: no Docker daemon and no Docker-in-Docker on Railway. |
| OpenSandbox | Only with an OpenSandbox server you run elsewhere. |
| Remote Android (redroid) | Not available (needs Docker and binder); forced off with `OCTOP_ENABLE_MOBILE=false` (see upstream issue #2621). |

### Network binding

`octop run` is uvicorn with one worker, so it binds `0.0.0.0` (Rule 8.2: an asyncio socket on `::` is IPv6-only, and Railway's healthcheck and edge use IPv4). Nothing else connects to Octop privately. Postgres listens on all addresses (dual stack) and Octop reaches it at `postgres.railway.internal:5432`. Octop trusts `X-Forwarded-For` only from loopback peers, so its per-address throttles (LDAP binds, invite redemption) see Railway's edge address (the login lockout is per username); it builds OAuth callback URLs from `X-Forwarded-Proto`/`Host`, which Railway sets, so callbacks use `https://{your-domain}/api/connectors/oauth/callback`.

## Service: Octop

| Setting | Value |
|---|---|
| Source | repo `baranberkay96/octop-railway`, root `/services/octop` (Dockerfile) |
| Start | image ENTRYPOINT `/app/railway/railway-entrypoint.sh` (no start command) |
| Healthcheck | `GET /api/health` on `PORT=8088`, timeout 900 s. Public by design, answered once the server has started (database bound, runtime up); it fails with 500 when the database is unreachable. It reports `ok`, start time, user count and running agent count; a database error makes it fail. |
| Public domain | yes, target port 8088 |
| TCP proxy | none |
| Volume | `/data` (`HOME=/data`, `OCTOP_HOME=/data/.octop`) |
| Restart policy | `ALWAYS` (always-on assistant; a clean exit restarts too) |
| Replicas | 1 (ADR 002: single active writer; the volume allows one instance) |
| Draining | `RAILWAY_DEPLOYMENT_DRAINING_SECONDS=30`; uvicorn shutdown stops cron, channels, agents and the pool |

### What the wrapper does on every start

| Step | Effect |
|---|---|
| `PORT` | Must be 1-65535; exported as `OCTOP_PORT` too. |
| `/data` | Warning in the log when it is not a mounted volume. |
| `FORWARDED_ALLOW_IPS` | Unset (logged if present). Otherwise uvicorn would accept forged `X-Forwarded-For` and Octop's per-address throttling could be bypassed. |
| `OCTOP_LOG_LEVEL` | Validated (uvicorn refuses unknown names); invalid → `info`. |
| `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS` | When unset: the CPU quota from `/sys/fs/cgroup/cpu.max` (v1 fallback, then `nproc`), capped at 8 (Rule 8.15). Agent shells inherit them. ONNX Runtime (local OCR) does not read them; see Open questions. |
| Postgres wait | With `OCTOP_DATABASE_URL` set: `pg_isready` every ~5 s up to 540 s; a malformed URL stops at once. Without it: SQLite on the volume. |
| TLS guard | If Octop's own HTTPS listener was switched on in the dashboard (`config.json` → `tls.enabled`), it is switched off: Railway's edge terminates TLS and talks HTTP to `PORT`, so the HTTPS listener would take the service offline. |
| Migrations | `open_cli_services()` (Octop's CLI database helper) loads `~/.octop/env` and `config.json`, opens the database and runs migrations, as `octop init` does. |
| Admin, first boot (no users) | Creates the admin from `OCTOP_ADMIN_USERNAME`, `OCTOP_ADMIN_PASSWORD`, `OCTOP_ADMIN_DISPLAY_NAME`, `OCTOP_ADMIN_LOCALE` (Octop's `octop init` path, plus the locale, which `octop init` cannot set and which defaults to `zh` upstream). **Fails closed**: username not matching `[A-Za-z0-9_.-]{3,64}`, password under 12 characters or rejected by Octop's policy (letters and digits, not a common password) stop the boot. Upstream's entrypoint would instead start the public setup wizard. No `credential.txt` or `octop-login.txt` is written. Writes upstream's `.initialized` marker. |
| Admin, later boots | Keeps a salted HMAC of the applied username and password in `/data/.octop/.railway-admin.json` (0600, never the password). Variable unchanged: nothing happens, so a password changed in the dashboard stays. Password variable changed: the admin's password is reset and the JWT secret rotated (all sessions signed out); an invalid new value is logged and ignored. Username variable not an existing account: logged, nothing changed. |
| Security policy | Only when the database has no `security_policy` setting yet and `OCTOP_SECURITY_DEFAULTS=strict`: stores upstream's default policy with tool approval enabled for upstream's default tool set (`bash`, `execute`, `write_file`, `edit_file`, `delete`), the shell-command guard in `require_approval` mode, and extra file-tool deny rules (below). Anything changed later in the admin security settings is kept. |
| Environment | `OCTOP_ADMIN_PASSWORD`, `OCTOP_DEFAULT_PASSWORD`, `OCTOP_ADMIN_USERNAME`, `OCTOP_ADMIN_DISPLAY_NAME`, `OCTOP_ADMIN_LOCALE`, `OCTOP_SECURITY_DEFAULTS`, `OCTOP_DB_WAIT_SECONDS`, `OCTOP_LOG_TO_STDOUT` are unset before `octop run`, so they are not in the environment agent shells inherit. |
| Logs | Octop writes its application log (agents, channels, cron, errors) only to `/data/.octop/logs/octop.log`. With `OCTOP_LOG_TO_STDOUT=true`, `tail -F` forwards new lines to stdout (Railway's log view), skipping uvicorn's lines, which are on stdout already. |
| Start | `exec octop run --host 0.0.0.0 --port $PORT`, upstream's command; it persists host and port to `config.json`. |

Extra file-tool deny rules (added to upstream's `/etc/**`, `/root/**`, `**/.env`, SSH and AWS paths): read and write of `/data/.octop/config.json`, `/data/.octop/env` (dashboard-managed environment variables), `/data/.octop/backups/**` (database dumps), `/data/.octop/.railway-admin.json`, `/data/.octop/octop.db*` (SQLite fallback holds keys), `credential.txt`, `octop-login.txt`; write of `/data/.octop/security/**` (guard rules), `/data/.octop/plugins/**` and `/app/**` (code the server loads). Agent workspaces stay reachable. These rules cover agent file tools only; shell commands go through approval.

### Variables

None is required at deploy.

| Variable | Default | Notes |
|---|---|---|
| `PORT` | `8088` | Healthcheck port = app port = domain target port (Rule 8.1); upstream's default port |
| `OCTOP_ADMIN_USERNAME` | `admin-${{secret(8, "…")}}` | Random so that nobody can lock the admin out by failing five logins against a known name |
| `OCTOP_ADMIN_PASSWORD` | `Oc1-${{secret(32, "…")}}` | The fixed `Oc1-` prefix guarantees the letter and digit Octop's policy requires (a random 32-character string misses a digit in about 0.7 % of deploys); the 32 random characters carry the strength. Reset by changing it (see above). |
| `OCTOP_ADMIN_DISPLAY_NAME` | `Admin` | First boot only |
| `OCTOP_ADMIN_LOCALE` | `en` | `en` or `zh`; first boot only; language of the admin's dashboard and default experts |
| `OCTOP_DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Upstream variable. Empty = SQLite on the volume |
| `OCTOP_DEFAULT_TIMEZONE` | `UTC` | Upstream variable (upstream default `Asia/Shanghai`); dashboard times and cron |
| `OCTOP_SECURITY_DEFAULTS` | `strict` | `strict` or `upstream`; first boot only (when no policy is stored) |
| `OCTOP_ENABLE_MOBILE` | `false` | Upstream variable; Remote Android cannot run on Railway |
| `OCTOP_LOG_TO_STDOUT` | `true` | Forward the application log to Railway |
| `OCTOP_LOG_LEVEL` | `info` | Upstream variable |
| `RAILWAY_DEPLOYMENT_DRAINING_SECONDS` | `30` | Graceful stop window |

Optional upstream variables that work as documented upstream and are not set: `OCTOP_MAX_UPLOAD_MB` (default 100), `OCTOP_ACCESS_TOKEN_TTL` (86400 s), `OCTOP_LOGIN_MAX_ATTEMPTS` / `OCTOP_LOGIN_LOCKOUT_SECONDS` (5 / 900), `OCTOP_CAPTCHA_*` (login captcha providers), `OCTOP_BACKUP_AUTO_ENABLED` and the other `OCTOP_BACKUP_*` keys (scheduled backups to the volume; off by default because they count against the volume size). Template-only: `OCTOP_DB_WAIT_SECONDS` (Postgres wait, default 540).

Not set on purpose:
- **LLM keys** (`OPENAI_API_KEY`, `DASHSCOPE_API_KEY`). Octop's providers are configured in the dashboard and stored encrypted in the database. The harness can fall back to `OPENAI_API_KEY` from the environment, but every agent's shell inherits the environment, so a key there is readable by every user's experts.
- **Channel tokens**. Octop has no environment variables for them; bots are configured per expert in the dashboard (some, like WeChat and QQ, by QR binding).
- `LANGFUSE_TRACING_ENABLED=false` (one market template sets it): it is the SDK kill switch and silently disables the dashboard's Langfuse setting. Tracing is off unless an admin enables it there.
- `OCTOP_CORS_ORIGINS` (same-origin dashboard), `OCTOP_ENABLE_API_DOCS` (stays off), `OCTOP_REQUIRE_SETUP_PASSWORD` (the wizard is never reached).

## Service: Postgres

Copied from `templates/_railway-base/postgres.json`: `ghcr.io/railwayapp-templates/postgres-ssl:18`, volume `/var/lib/postgresql/data`, generated password, `DATABASE_URL` on the private domain, no public TCP proxy, 60 s draining. Octop uses the `postgres` role in the `railway` database and creates its control-plane tables and memory tables there. No extension is needed (ADR 002: the control plane uses plain types; octop-memory uses `tsvector`).

## Security model

- **Login**: JWT on every `/api/*` route except health, login, captcha config, SSO start/callback, invite validate/redeem, i18n, short-lived download links, the connector OAuth callback and token-protected internal MCP endpoints. The setup wizard's routes answer 410 once a user exists. Login lockout: 5 failures per username lock it for 15 minutes; the slider captcha is a dashboard feature only.
- **No open registration**: Octop has no sign-up. New accounts come only from an admin (user management), from invite links an admin creates, or from SSO/LDAP an admin configures.
- **Admin bootstrap**: created from generated variables before the port opens; no wizard, no plaintext credential file; the password is removed from the app's environment after it is stored (Argon2id hash in the database).
- **Tool approval and guardrails** (seeded on the first boot, see above): shell commands, file writes and deletes wait for approval in the dashboard chat, or in the chat app conversation through Octop's approval commands; risky shell patterns (destructive `rm`, pipe-to-shell, reverse shells, `/proc/*/environ`, privilege escalation, ...) are flagged in the approval; PII and API-key masking stays on (upstream default). Upstream's own default is approval off and the guard in warn-only mode.
- **Multi-user is not isolation.** All experts of all users run in the same container as root, and the default workspace backend is the container's file system. A shell command can read anything there, including the database URL in the environment and `/proc/1/environ` (the container's initial environment, which holds all Railway variables). Approval prompts go to the person chatting with the expert, so a user who can use shell tools can get at the database. Give accounts with shell tools only to people you would give server access, and use Octop's user-group permissions to limit tools and features for others. The upstream README's "JWT multi-user isolation" refers to API access, not to process isolation.
- **Chat apps**: anyone who can message a connected bot talks to that expert and can answer its approval prompts. Use each channel's allowlists (Telegram: allowed user and chat IDs; empty means anyone who finds the bot).
- **Keys at rest**: provider, connector, SSO, storage and voice credentials are Fernet-encrypted in the database (new in 1.0.3b1). The Fernet keys sit in the same database, so this protects copies of single tables, not a full database dump. Treat backups as secrets.
- **Shell tools and the web terminal** (admin and users with the `terminal` permission) are a root shell in the container. Upstream refuses the in-dashboard self-upgrade for editable installs, which `uv sync` produces by default (not verified for this image); a pip upgrade inside the container would be lost on redeploy anyway. Upgrade through the image tag.

## First login

1. Wait for the Octop service to turn healthy (first deploy: a build layer with Chromium and the PostgreSQL client on the 1.1 GB image, Postgres start, migrations).
2. Open the public URL. Sign in with `OCTOP_ADMIN_USERNAME` and `OCTOP_ADMIN_PASSWORD` from the Octop service's Variables tab.
3. Add a model provider and key in the model settings and set the default model (OpenAI, Anthropic, DeepSeek, DashScope/Qwen, Gemini, OpenRouter, Kimi, Zhipu, MiniMax, SiliconFlow, any OpenAI-compatible endpoint, ...).
4. Create an expert from the expert library (there is no default expert on this path; upstream's CLI bootstrap behaves the same) and chat with it.
5. Create users or invite links for your team; set up user groups if not everyone should get shell tools.
6. Connect chat apps per expert; set allowlists.

## Improvements over market templates

1. **Current release, pinned twice**: 1.0.3b1 by tag and index digest, with keys encrypted at rest (market: 1.0.2 by digest, `:latest`, or a third-party 1.0.0 build).
2. **PostgreSQL control plane and memory** (upstream-supported option for externalized state and concurrent multi-user writes), with PostgreSQL 18 client tools so the dashboard's backup and restore work (the official image has no `pg_dump`; every market template uses SQLite only).
3. **Admin that cannot be guessed, locked out, or bypassed**: random username, generated password applied before the port opens, fail-closed instead of upstream's public setup wizard, no plaintext `credential.txt`, password resettable from Railway with session sign-out, English locale (market: `admin` username, first-boot-only password, credential file on the volume).
4. **Tool approval and the shell guard actually on** from the first boot, plus deny rules that keep agent file tools away from Octop's config, dumps and plugin code (market: upstream defaults, approval off and guard warn-only).
5. **Bootstrap secrets kept out of the environment agents inherit** (market: the admin password is readable with `env` from any expert's shell).
6. **Application logs in Railway's log view** (market: only in a file on the volume).
7. **Browser tool works out of the box and after redeploys**: Playwright Chromium and its libraries in the image (market: a dashboard install into the container layer, lost on every redeploy); bubblewrap pre-installed instead of `apt-get install` at every boot.
8. **Self-healing against two foot-guns**: Octop's HTTPS listener switched off if enabled in the dashboard (it would take the service offline behind Railway's TLS), Remote Android forced off (upstream #2621).
9. **Startup robust to service order**: waits for Postgres, restart policy `ALWAYS`, 900 s healthcheck window (market: `ON_FAILURE` with 5 or 10 retries).
10. **Railway-sized defaults**: CPU thread pools from the cgroup quota (Rule 8.15), timezone UTC, `FORWARDED_ALLOW_IPS` guard, Langfuse switch left to the dashboard.

## Resource estimate

Railway prices: RAM $10/GB-month, vCPU $20/vCPU-month, volume $0.15/GB-month. Estimates, not measured (no container was run).

| Service | Idle RAM / CPU | Typical RAM / CPU | Notes |
|---|---|---|---|
| Octop | ~0.5-0.7 GB / 0.02-0.05 vCPU | 1.0-1.5 GB / 0.1-0.3 vCPU | One Python process (FastAPI, LangChain/deepagents harness, gateway). Chromium sessions add 0.3-0.6 GB while browsing; local ONNX embedding or OCR models add 0.2-0.6 GB; each running MCP stdio server is a child process. LLM calls are I/O-bound. |
| Postgres | ~0.06-0.1 GB / 0.01 vCPU | 0.15-0.3 GB / 0.02-0.05 vCPU | Control plane, memory and checkpoints for a team are small. |
| Volumes | Octop ~0.1 GB, Postgres ~0.1 GB after init | Octop 1-5 GB, Postgres 0.2-1 GB | Workspaces, uploads, knowledge indexes, model caches; backups if enabled. |

Estimated monthly cost: **idle ≈ $8-9** (≈ 0.7 GB RAM, 0.04 vCPU, 0.2 GB volume), **typical small team ≈ $15-25**, **heavy use** (browser, local embeddings, 20+ users) **≈ $35-45**. Model usage is billed by the provider.

Minimum plan: **Hobby**. Trial's 1 GB RAM per service is too tight for Octop with the browser or local models. Hobby's 5 GB volume limit per service fits normal use; heavy file or knowledge-base use and on-volume backups need Pro.

## Verification results (2026-10-30, static, no Docker)

Docker was not used. **The Dockerfile has not been built and no container has been run.** Checks done instead:

| Check | How | Result |
|---|---|---|
| Image tags and digest | GHCR registry API (tags list, index, amd64 manifest, config blob) | `1.0.3b1` exists (index `sha256:2ac082ea…`, amd64 + arm64), same digest as `latest`; `1.0.2` = `sha256:c15e792f…` (market `octop-3`); config as described above, no `VOLUME` |
| Tag → commit | `gh api repos/TencentCloud/Octop/commits/v1.0.3b1`, image revision label | both `890111b7…`; release published 2026-10-25, not flagged pre-release |
| Local upstream copy = tag | blob hashes of 5 key files vs `gh api …/contents?ref=v1.0.3b1`; compare API | identical; main has no commits after the tag |
| PGDG repository | `apt.postgresql.org/…/dists/trixie-pgdg/Release` and amd64 `Packages.gz`; key URL | suite exists, `postgresql-client-18` 18.6 available; key URL 200 |
| Icon | HTTP GET | 200 `image/svg+xml` |
| Scripts | `sh -n`, `dash -n`, `bash -n`, shellcheck 0.10 (`-s sh`), ruff 0.8.6 (E,F,W,B,UP,S), `py_compile` | clean |
| `railway_setup.py` logic | run against stub `octop`/`octop_harness` modules written for the test (JSON file as database) | 18 scenarios as specified: first boot (admin, locale, marker, policy), unchanged reboot, password change (hash replaced, JWT rotated), invalid change (kept), short/no-digit/empty password and bad/empty username on first boot (exit 1, nothing created), unknown username later (no change), lost and corrupt state file (adopted), `upstream` mode, invalid mode and locale, TLS on (switched off, file 0600), corrupt and TLS-off `config.json` (untouched); no plaintext password on disk |
| Entrypoint flow | entrypoint with stubbed `pg_isready`, `octop`, setup and `sleep`, under dash and sh | PORT checks, relative `OCTOP_HOME`, Postgres wait/timeout/bad URL, SQLite fallback, setup failure stops the boot, `FORWARDED_ALLOW_IPS` and all bootstrap variables absent from the app's environment, `OCTOP_DATABASE_URL` kept, log-level validation, thread override |
| Log forwarder | stub writes Octop-format lines after start (BSD tail + BWK awk locally) | Octop lines and their tracebacks forwarded, uvicorn lines and their tracebacks skipped |
| CPU thread cap | function extracted and run under dash with fake cgroup files | quota rounding, `max`, garbage, zero period, v1 quota and v1 unlimited, cap of 8 all correct |
| Template | `to_serialized.py`, `ship.py review` | serializes; no problems reported; description 73 characters |
| Upstream API used by the wrapper | read in the v1.0.3b1 source (`open_cli_services`, `UserRepo.count/create/get_by_username/set_password_hash`, `SecretRepo.rotate`, `SettingsRepo.get`, `SecuritySettingsStore.save`, `SecurityPolicy.defaults/to_dict/from_dict`, `validate_password_policy`, `hash_password`) | signatures match; also asserted by the Dockerfile's build-time import check |
| Docker build, container run, Linux tail/mawk, Railway behaviour | | **not run (unverified)** |

## Verification checklist

- [ ] Build log: PGDG install, `playwright install --with-deps chromium`, and the check step (`octop` 1.0.3b1, imports, `verify_chromium`, `pg_dump` 18) pass.
- [ ] Deploy log: `Postgres is accepting connections`, `created admin account 'admin-…' (locale en)`, `security policy stored: …`, `starting Octop on 0.0.0.0:8088`; no `/data is not a mounted volume` warning; then Octop's own `octop.*` lines appear (log forwarder); healthcheck `/api/health` passes.
- [ ] `curl https://{domain}/api/health` → `{"ok": true, "db": true, "users_loaded": 1, …}`; `curl https://{domain}/api/auth/me` → 401; `curl https://{domain}/api/setup/status` → `setup_required: false`.
- [ ] Sign in with the generated credentials; dashboard in English; add a provider; create an expert; a chat reply arrives.
- [ ] Ask the expert to run `ls /data/.octop`: an approval card appears; approve it. Ask it to read `/data/.octop/config.json` with its file tool: denied. `curl … | sh` is flagged in the approval.
- [ ] Ask the expert to run `env | grep -c OCTOP_ADMIN_PASSWORD` (approve): `0`.
- [ ] Browser tool: ask the expert to open a web page and summarise it (Chromium from the image, headless).
- [ ] Admin backup page: create a backup; it contains a PostgreSQL dump (pg_dump 18 against server 18).
- [ ] Persistence: create an expert, a knowledge base with one document and a cron job; redeploy; all still there, the job still runs.
- [ ] Change `OCTOP_ADMIN_PASSWORD`, redeploy: log line `password of '…' reset`, old sessions signed out, new password works.
- [ ] Telegram (optional): connect a bot with an allowlist; DM it; reply arrives; a shell request asks for approval in Telegram.
- [ ] Restart test: `railway ssh` → `pkill -f "octop run"`; the deployment restarts by itself and comes back healthy.

## Open questions

- **Nothing has been built or run.** Likely failure points: `playwright install --with-deps chromium` on the trixie base at build time, the build-time import check, and first-boot migrations on PostgreSQL 18.
- Whether the app's RAM matches the estimate; whether upstream's background bubblewrap and plugin dependency installs at boot (`load_installed(install_deps=True)`) slow the first start noticeably.
- Approval prompts in chat apps were read in the source (gateway HITL coordinator) but not exercised. Upstream issue #2456: a pending approval can be lost when the process restarts.
- Scheduled tasks fail when they need an approval-gated tool (`cron agent run requires user interaction`); teams that rely on cron with shell or file writes must narrow the approval tool list in the admin security settings.
- ONNX Runtime (local OCR, embeddings) sizes its own thread pool from the host's cores; `OMP_NUM_THREADS` does not limit it. Upstream limits local embeddings to two threads; OCR on Railway's many-core hosts may oversubscribe the CPU quota (slow, not stalled, expected).
- A narrowed `shell` storage backend uses bubblewrap namespaces; whether Railway allows them is unknown. The default backend does not use bubblewrap.
- Node.js is not in the official image, so connectors that install npm CLIs (Feishu `lark-cli`, WeCom `wecom-cli`) and `npx`-based MCP servers cannot run; remote (HTTP) MCP servers and the built-in channels are unaffected. Not added here.
- Whether `/api/health` stays fast with many experts (it counts users and agents on every call).

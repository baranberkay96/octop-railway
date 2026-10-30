# Deploy and Host Octop with Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/octop-v1-multi-user-ai-assistant?referralCode=20H68q)

Run Octop, the open-source multi-user AI assistant from Tencent Cloud, for your team on Railway. Each person gets their own experts (agents) with tools, memory, knowledge bases and schedules, reachable from a web dashboard and from Feishu, DingTalk, WeCom, QQ, WeChat, Telegram or Discord.

## About Hosting Octop

Octop is a single Python process: web dashboard, REST and WebSocket API, agent runtime with shell, file and browser tools, chat-app bridges, cron and connectors (OAuth and MCP). Hosting it well needs an always-on machine, a database for users, experts, channels and encrypted keys, durable storage for workspaces and knowledge bases, and a login from the first second. This community template runs the `ghcr.io/tencentcloud/octop:1.0.3b1` image (pinned by digest) with PostgreSQL as the control plane and agent memory, a volume for files, an admin created from generated credentials before the port opens, and tool approval switched on.

## Common Use Cases

- A shared assistant for a team or household: one admin, separate accounts, each with their own experts, models and memory
- Experts connected to Feishu, DingTalk, WeCom or Telegram groups that answer questions, draft documents and run tools on request
- Scheduled briefings and recurring checks written in plain language and delivered to a chat
- Question answering over your own documents with per-team knowledge bases
- Web research and form work with a headless Chromium, plus MCP and OAuth connectors to other systems

## Dependencies for Octop Hosting

- An API key for at least one model provider (OpenAI, Anthropic, DeepSeek, Qwen/DashScope, Gemini, OpenRouter or any OpenAI-compatible endpoint), added in the dashboard after the first login. Not needed to deploy.
- Optional bot credentials for the chat apps you want to connect, entered per expert in the dashboard
- PostgreSQL and a Railway volume at `/data` (both included)

### Deployment Dependencies

- Octop repository and releases: https://github.com/TencentCloud/Octop
- Container image: https://github.com/TencentCloud/Octop/pkgs/container/octop
- Docker deployment notes: https://github.com/TencentCloud/Octop/blob/v1.0.3b1/docker/README.md
- Configuration reference: https://github.com/TencentCloud/Octop/blob/v1.0.3b1/docs/configuration.md
- Database backends (SQLite or PostgreSQL): https://github.com/TencentCloud/Octop/blob/v1.0.3b1/docs/adr/002-database-backends.md
- Connectors and channels: https://github.com/TencentCloud/Octop/blob/v1.0.3b1/docs/connectors.md

### Implementation Details

| Service | Source | Purpose |
|---|---|---|
| Octop | Dockerfile in `services/octop` on `ghcr.io/tencentcloud/octop:1.0.3b1` (pinned by digest) | Dashboard, API, experts, tools, chat channels and cron on port 8088; healthcheck `/api/health`; volume at `/data` (workspaces, knowledge bases, uploads, plugins, model caches); restart policy always |
| Postgres | `ghcr.io/railwayapp-templates/postgres-ssl:18` | Control-plane database (users, experts, channels, schedules, settings, encrypted keys) and agent memory; private network only |

**First login**

1. Wait until the Octop service is healthy. The first deploy adds Chromium and the PostgreSQL client to the 1.1 GB image and waits for Postgres.
2. Open the public URL and sign in with `OCTOP_ADMIN_USERNAME` and `OCTOP_ADMIN_PASSWORD` from the Octop service's Variables tab. Both are generated at deploy; the username is random so nobody can lock the admin out by guessing it.
3. Add a model provider and key in the dashboard's model settings and choose a default model.
4. Create your first expert from the expert library and say hello.
5. Invite your team from the admin's user management (accounts or invite links). There is no public sign-up.
6. Connect chat apps per expert. For Telegram, set the allowed user IDs: an empty list lets anyone who finds the bot talk to the expert.

**Tool approval**: on the first boot the template stores a security policy with tool approval on for shell commands, file writes and deletes, and the shell-command guard set to require approval. Adjust it in the admin's security settings. Scheduled tasks cannot pause for approval, so a task that needs those tools fails until you relax the policy. Set `OCTOP_SECURITY_DEFAULTS=upstream` before the first boot to keep upstream's defaults (approval off).

**Trust model**: all experts share one container and run tools as root there. Anyone who can run and approve shell commands can read the database credentials. Give accounts with shell tools only to people you would give server access.

**Login recovery**: change `OCTOP_ADMIN_PASSWORD` and redeploy; the admin password is reset and all sessions are signed out. A password changed in the dashboard is kept until you change the variable.

**Workspace backends**: experts work on the container's disk (the volume) by default. The Docker sandbox and Remote Android need a Docker daemon, which Railway does not offer. PostgreSQL and S3-compatible storage backends work; a Railway Bucket can be added as an S3 storage backend in the admin settings.

**Scaling**: Octop is a single-writer process. Keep one replica and give the service more RAM and CPU as the team grows (about 0.6 GB idle, 1-1.5 GB for a small team, more with the browser and local embedding models).

**Pinning and upgrades**: the Dockerfile pins `ghcr.io/tencentcloud/octop:1.0.3b1` by tag and digest. 1.0.3b1 is upstream's newest release, a beta build of the 1.0.3 patch on the generally available 1.x line; upstream publishes these betas as regular releases. To move to another release, change the tag, the digest and the version check in the Dockerfile, then redeploy (releases: https://github.com/TencentCloud/Octop/releases). Back up first from the admin's backup page; it uses `pg_dump`, which the template includes.

### Why Deploy Octop on Railway?

A team assistant has to be online when people message it and must keep its memory, files and keys safe. Railway runs Octop and its PostgreSQL database side by side on a private network, with HTTPS, a persistent volume, automatic restarts, logs and SSH access, and no server to maintain. You pay for the resources the assistant uses; model usage is billed by your provider.

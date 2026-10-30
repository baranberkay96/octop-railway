"""Railway setup for Octop, run by railway-entrypoint.sh before ``octop run``.

Every start:

1. TLS guard: Railway terminates TLS at its edge and talks plain HTTP to
   PORT. If Octop's own HTTPS listener was switched on in the dashboard, it is
   switched off again in ``config.json`` (otherwise the service is unreachable).
2. Opens the control-plane database the way Octop's own CLI does
   (``open_cli_services``: ``~/.octop/env``, ``config.json`` + environment,
   migrations).
3. Admin account from ``OCTOP_ADMIN_USERNAME`` / ``OCTOP_ADMIN_PASSWORD``:
   created when the database has no users yet. This fails closed: invalid
   values stop the boot, and no setup wizard is ever served. Afterwards the
   password is reset when the variable changes (all sessions are signed out)
   and left alone otherwise, so a password changed in the dashboard is kept.
4. Security policy: when none is stored yet and ``OCTOP_SECURITY_DEFAULTS`` is
   ``strict``, stores upstream's defaults with tool approval switched on, the
   shell-command guard in ``require_approval`` mode, and Octop's own control
   files added to the file-tool deny list. Later changes in Admin > Security
   are kept.

Nothing secret is printed. Exit code 1 stops the boot.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MIN_PASSWORD_LENGTH = 12
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,64}$")
DISPLAY_NAME_MAX = 64
STATE_FILE = ".railway-admin.json"
INIT_MARKER = ".initialized"  # upstream docker-entrypoint.sh uses the same marker
# octop.infra.agents.security.policy_store._SETTINGS_KEY (asserted at build time)
SECURITY_SETTINGS_KEY = "security_policy"
SECURITY_MODES = ("strict", "upstream")


class SetupError(Exception):
    """Stops the boot. Messages never contain secret values."""


@dataclass(frozen=True)
class AdminSettings:
    username: str
    password: str
    display_name: str
    locale: str


def log(message: str) -> None:
    print(f"[railway] {message}", file=sys.stderr, flush=True)


def octop_home() -> Path:
    raw = os.environ.get("OCTOP_HOME", "").strip()
    return Path(raw) if raw else Path.home() / ".octop"


def read_admin_settings() -> AdminSettings:
    # Octop has two UI and agent languages; normalize_locale maps zh* to zh
    # and everything else to en.
    locale_raw = os.environ.get("OCTOP_ADMIN_LOCALE", "en").strip().lower()
    if locale_raw.startswith("zh"):
        locale = "zh"
    else:
        if locale_raw and not locale_raw.startswith("en"):
            log(f"OCTOP_ADMIN_LOCALE '{locale_raw}' is not en or zh; using en")
        locale = "en"
    display_name = os.environ.get("OCTOP_ADMIN_DISPLAY_NAME", "").strip()[:DISPLAY_NAME_MAX]
    return AdminSettings(
        username=os.environ.get("OCTOP_ADMIN_USERNAME", "").strip(),
        password=os.environ.get("OCTOP_ADMIN_PASSWORD", ""),
        display_name=display_name or "Admin",
        locale=locale,
    )


def read_security_mode() -> str:
    mode = os.environ.get("OCTOP_SECURITY_DEFAULTS", "strict").strip().lower() or "strict"
    if mode not in SECURITY_MODES:
        log(f"OCTOP_SECURITY_DEFAULTS '{mode}' is not one of {', '.join(SECURITY_MODES)}; using strict")
        return "strict"
    return mode


def password_problem(password: str) -> str | None:
    """Reason why *password* is not acceptable, or None. Never echoes it."""
    from octop.infra.errors import OctopError
    from octop.infra.users.password import validate_password_policy

    if len(password) < MIN_PASSWORD_LENGTH:
        return f"shorter than {MIN_PASSWORD_LENGTH} characters"
    try:
        validate_password_policy(password)
    except OctopError as exc:
        return str(exc.message)
    return None


def write_private_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomically write *payload* as JSON readable by the owner only."""
    tmp = path.with_name(f"{path.name}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


# --- TLS guard -----------------------------------------------------------------


def disable_octop_tls(home: Path) -> None:
    path = home / "config.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return
    except (OSError, ValueError):
        # Octop itself refuses a corrupt config.json with the parser position.
        return
    tls = raw.get("tls") if isinstance(raw, dict) else None
    if not (isinstance(tls, dict) and tls.get("enabled")):
        return
    write_private_json(path, {**raw, "tls": {**tls, "enabled": False}})
    log("Octop's own HTTPS listener was enabled in config.json; switched it off (Railway terminates TLS at its edge)")


# --- Admin account -------------------------------------------------------------


def fingerprint(salt: bytes, username: str, password: str) -> str:
    return hmac.new(salt, f"{username}\0{password}".encode(), hashlib.sha256).hexdigest()


def load_state(path: Path) -> dict[str, str] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        log(f"{path.name} is unreadable; it will be recreated")
        return None
    if not isinstance(data, dict):
        return None
    if not all(isinstance(data.get(key), str) for key in ("username", "salt", "hmac")):
        return None
    return {key: data[key] for key in ("username", "salt", "hmac")}


def save_state(path: Path, admin: AdminSettings) -> None:
    salt = secrets.token_bytes(16)
    write_private_json(
        path,
        {
            "version": 1,
            "username": admin.username,
            "salt": salt.hex(),
            "hmac": fingerprint(salt, admin.username, admin.password),
        },
    )


def state_matches(state: dict[str, str], admin: AdminSettings) -> bool:
    try:
        salt = bytes.fromhex(state["salt"])
    except ValueError:
        return False
    expected = fingerprint(salt, admin.username, admin.password)
    return state["username"] == admin.username and hmac.compare_digest(state["hmac"], expected)


def create_first_admin(services: Any, admin: AdminSettings, home: Path) -> None:
    from octop.infra.users.password import hash_password

    if not USERNAME_RE.match(admin.username):
        raise SetupError(
            "OCTOP_ADMIN_USERNAME must be 3-64 characters of letters, digits, '.', '_' or '-'; "
            "no admin was created"
        )
    problem = password_problem(admin.password)
    if problem is not None:
        raise SetupError(
            f"OCTOP_ADMIN_PASSWORD is not acceptable ({problem}); no admin was created. "
            "Set a new value in the service's Variables and redeploy"
        )
    services.user_repo.create(
        username=admin.username,
        password_hash=hash_password(admin.password),
        role="admin",
        display_name=admin.display_name,
        locale=admin.locale,
    )
    save_state(home / STATE_FILE, admin)
    (home / INIT_MARKER).touch()
    log(f"created admin account '{admin.username}' (locale {admin.locale})")


def ensure_admin(services: Any, admin: AdminSettings, home: Path) -> None:
    from octop.infra.users.password import hash_password

    repo = services.user_repo
    if repo.count() == 0:
        create_first_admin(services, admin, home)
        return

    row = repo.get_by_username(admin.username) if admin.username else None
    if row is None:
        log(
            f"WARNING: OCTOP_ADMIN_USERNAME '{admin.username}' is not an existing account; "
            "accounts are left unchanged (usernames cannot be changed from variables)"
        )
        return

    state_path = home / STATE_FILE
    state = load_state(state_path)
    if state is None or state["username"] != admin.username:
        save_state(state_path, admin)
        log(f"admin '{admin.username}' exists; recorded the current OCTOP_ADMIN_PASSWORD without changing the account")
        return
    if state_matches(state, admin):
        return

    problem = password_problem(admin.password)
    if problem is not None:
        log(f"ERROR: OCTOP_ADMIN_PASSWORD changed but is not acceptable ({problem}); the existing password is kept")
        return
    repo.set_password_hash(row.id, hash_password(admin.password))
    # Same as `octop admin rotate-jwt-secret`: every issued token stops working.
    services.secret_repo.rotate("jwt", os.urandom(32))
    save_state(state_path, admin)
    log(f"password of '{admin.username}' reset from OCTOP_ADMIN_PASSWORD; all sessions were signed out")


# --- Security policy -------------------------------------------------------------


def octop_file_rules(home: Path) -> list[dict[str, Any]]:
    """Deny rules for Octop's own control files (agent file tools only).

    Agent workspaces live under ``<home>/agents`` and stay reachable. Shell
    commands are not covered by these rules; they go through tool approval.
    """
    root = str(home).rstrip("/")
    return [
        {
            "operations": ["read", "write"],
            "mode": "deny",
            "paths": [
                f"{root}/config.json",
                f"{root}/env",
                f"{root}/backups/**",
                f"{root}/{STATE_FILE}",
                f"{root}/octop.db",
                f"{root}/octop.db-wal",
                f"{root}/octop.db-shm",
                f"{root}/credential.txt",
                f"{root}/octop-login.txt",
            ],
        },
        {
            "operations": ["write"],
            "mode": "deny",
            "paths": [
                f"{root}/security/**",
                f"{root}/plugins/**",
                "/app/**",
            ],
        },
    ]


def ensure_security_policy(services: Any, home: Path, mode: str) -> None:
    from octop.infra.agents.security.policy_store import SecuritySettingsStore
    from octop_harness.security.models import SecurityPolicy

    if services.settings_repo.get(SECURITY_SETTINGS_KEY):
        log("security policy already stored; keeping what is configured in Admin > Security")
        return
    if mode == "upstream":
        log("OCTOP_SECURITY_DEFAULTS=upstream: keeping upstream defaults (tool approval off, shell guard only warns)")
        return

    policy = SecurityPolicy.defaults().to_dict()
    policy["hitl"] = {**policy["hitl"], "enabled": True, "tools": "default"}
    policy["tool_guard"] = {"enabled": True, "mode": "require_approval"}
    policy["filesystem"] = {
        "enabled": True,
        "rules": [*policy["filesystem"]["rules"], *octop_file_rules(home)],
    }
    saved = SecuritySettingsStore(settings_repo=services.settings_repo).save(policy)
    if not (saved.hitl.enabled and saved.tool_guard.enabled and saved.tool_guard.mode == "require_approval"):
        raise SetupError("the security policy did not round-trip as expected; Octop was not started")
    log(
        "security policy stored: tool approval on (shell, file writes and deletes), "
        "risky shell commands need approval, Octop control files hidden from agent file tools"
    )


# --- Main ------------------------------------------------------------------------


def main() -> int:
    home = octop_home()
    home.mkdir(parents=True, exist_ok=True)
    admin = read_admin_settings()
    mode = read_security_mode()
    disable_octop_tls(home)
    try:
        from octop.cli.support.db import open_cli_services
    except ImportError as exc:
        raise SetupError(f"Octop's CLI helpers could not be imported ({exc}); the image does not match this wrapper") from exc
    with open_cli_services(home) as services:
        ensure_admin(services, admin, home)
        ensure_security_policy(services, home, mode)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SetupError as err:
        log(f"FATAL: {err}")
        sys.exit(1)

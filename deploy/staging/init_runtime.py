#!/usr/bin/env python3
"""Create isolated staging credentials outside the source tree. Never print secrets."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import subprocess

REPO = Path(__file__).resolve().parents[2]


def validate_domain(domain: str) -> str:
    if len(domain) > 253 or not re.fullmatch(
        r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", domain
    ):
        raise ValueError("Use a lowercase DNS hostname, without scheme, port or path")
    return domain


def gateway_config(domain: str, token: str) -> str:
    validate_domain(domain)
    if not re.fullmatch(r"[a-f0-9]{64}", token):
        raise ValueError("Invalid preview token")
    # Basic auth establishes the evaluator cookie. Subsequent API calls can use
    # their own Bearer Authorization without colliding with Basic authentication.
    # No `always` on Set-Cookie: a failed Basic challenge MUST NOT mint a token.
    return f'''map $http_cookie $preview_realm {{
    default "LearnHouse evaluator access";
    "~(?:^|;[[:space:]]*)__Host-LH_preview={token}(?:;|$)" off;
}}
map $remote_user $preview_cookie {{
    "" "";
    default "__Host-LH_preview={token}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=28800";
}}
map "$request_method:$uri" $registration_blocked {{
    default 0;
    ~^POST:/api/signup/?$ 1;
    ~^POST:/api/v1/users/?$ 1;
    ~^POST:/api/v1/users/[0-9]+/?$ 1;
}}
map $http_authorization $application_authorization {{
    default $http_authorization;
    ~*^Basic\\s "";
}}
map $http_upgrade $upgrade_connection {{
    default upgrade;
    "" close;
}}
server {{
    listen 80;
    server_name {domain};
    access_log off;
    server_tokens off;
    client_max_body_size 25m;
    if ($registration_blocked) {{ return 403; }}
    auth_basic $preview_realm;
    auth_basic_user_file /run/secrets/preview.htpasswd;
    add_header Set-Cookie $preview_cookie;
    add_header X-Robots-Tag "noindex, nofollow, noarchive" always;
    location / {{
        proxy_pass http://app:80;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Authorization $application_authorization;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $upgrade_connection;
        proxy_read_timeout 3600s;
    }}
}}
'''


def write_private(path: Path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as file:
        file.write(text)


def initialize(directory: Path, domain: str, admin_email: str) -> None:
    domain = validate_domain(domain)
    directory = directory.expanduser().resolve()
    if directory.is_relative_to(REPO):
        raise ValueError("Runtime secrets must be outside the source checkout")
    if not re.fullmatch(r"[a-zA-Z0-9._+%-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", admin_email):
        raise ValueError("Invalid administrator email")
    if directory.exists():
        raise FileExistsError("Refusing to overwrite existing credentials")

    preview_password = secrets.token_urlsafe(32)
    admin_password = secrets.token_urlsafe(32)
    db_password = secrets.token_hex(32)
    preview_token = secrets.token_hex(32)
    # Password is supplied on stdin, never visible in the process command line.
    hashed = subprocess.run(
        ["openssl", "passwd", "-6", "-stdin"], input=preview_password + "\n",
        text=True, capture_output=True, check=True,
    ).stdout.strip()
    if not hashed.startswith("$6$"):
        raise ValueError("Unexpected password hash")

    directory.mkdir(mode=0o700, parents=True)
    base = f"https://{domain}"
    values = {
        "HOSTNAME": "0.0.0.0",
        "PORT": "8000",
        "LEARNHOUSE_PORT": "9000",
        "COLLAB_PORT": "4000",
        "LEARNHOUSE_DOMAIN": domain,
        "LEARNHOUSE_FRONTEND_DOMAIN": domain,
        "LEARNHOUSE_TENANCY": "single",
        "LEARNHOUSE_SSL": "true",
        "LEARNHOUSE_OSS": "true",
        "LEARNHOUSE_DISABLE_EE": "1",
        "NEXT_PUBLIC_LEARNHOUSE_OSS": "true",
        "NEXT_PUBLIC_LEARNHOUSE_API_URL": base + "/api/v1/",
        "NEXT_PUBLIC_LEARNHOUSE_BACKEND_URL": base + "/",
        "NEXT_PUBLIC_LEARNHOUSE_DOMAIN": domain,
        "NEXT_PUBLIC_LEARNHOUSE_TOP_DOMAIN": domain,
        "NEXT_PUBLIC_LEARNHOUSE_MULTI_ORG": "false",
        "NEXT_PUBLIC_LEARNHOUSE_DEFAULT_ORG": "default",
        "NEXT_PUBLIC_LEARNHOUSE_HTTPS": "true",
        "NEXT_PUBLIC_COLLAB_URL": f"wss://{domain}/collab",
        "LEARNHOUSE_INTERNAL_API_URL": "http://127.0.0.1:9000/api/v1/",
        "LEARNHOUSE_INTERNAL_BACKEND_URL": "http://127.0.0.1:9000/",
        "LEARNHOUSE_API_URL": "http://127.0.0.1:9000",
        "NEXTAUTH_URL": base,
        "NEXTAUTH_SECRET": secrets.token_urlsafe(48),
        "LEARNHOUSE_AUTH_JWT_SECRET_KEY": secrets.token_urlsafe(48),
        "COLLAB_INTERNAL_KEY": secrets.token_urlsafe(48),
        "LEARNHOUSE_SQL_CONNECTION_STRING": f"postgresql://learnhouse:{db_password}@db:5432/learnhouse",
        "LEARNHOUSE_REDIS_CONNECTION_STRING": "redis://redis:6379/0",
        "LEARNHOUSE_REDIS_URL": "redis://redis:6379/0",
        "LEARNHOUSE_ALLOWED_ORIGINS": base,
        "LEARNHOUSE_ALLOWED_REGEXP": "^https://" + re.escape(domain) + "$",
        "LEARNHOUSE_INITIAL_ADMIN_EMAIL": admin_email,
        "LEARNHOUSE_INITIAL_ADMIN_PASSWORD": admin_password,
        "LEARNHOUSE_INITIAL_ORG_NAME": "CourseMax Preview",
        "LEARNHOUSE_INITIAL_ORG_SLUG": "default",
        "LEARNHOUSE_CONTENT_DELIVERY_TYPE": "filesystem",
        "LEARNHOUSE_DEVELOPMENT_MODE": "false",
        "LEARNHOUSE_IS_AI_ENABLED": "false",
        "LEARNHOUSE_LOGFIRE_ENABLED": "false",
        "LEARNHOUSE_NUDGES_ENABLED": "false",
        "LEARNHOUSE_DEMO_ENABLED": "false",
        "LEARNHOUSE_HLS_ENABLED": "false",
        "LEARNHOUSE_MAX_REQUEST_BODY_MB": "25",
        "NEXT_TELEMETRY_DISABLED": "1",
        "UV_NO_SYNC": "1",
    }
    # Values are quoted as dotenv strings; generated secrets contain no dollars.
    env = "".join(f"{key}={json.dumps(value)}\n" for key, value in values.items())
    write_private(directory / "app.env", env)
    write_private(directory / "db.env", f"POSTGRES_DB=learnhouse\nPOSTGRES_USER=learnhouse\nPOSTGRES_PASSWORD={db_password}\n")
    write_private(directory / "gateway.conf", gateway_config(domain, preview_token))
    write_private(directory / "preview.htpasswd", f"evaluator:{hashed}\n")
    # Nginx workers are unprivileged. The host's mode-0700 parent still protects
    # this file; the sole container mount is read-only.
    (directory / "preview.htpasswd").chmod(0o444)
    write_private(directory / "compose.env", f"LEARNHOUSE_RUNTIME_DIR={json.dumps(str(directory))}\nLEARNHOUSE_HOST={domain}\n")
    write_private(directory / "ACCESS.txt", (
        f"STAGING ONLY — do not publish this file.\nURL: {base}\n"
        f"Evaluator username: evaluator\nEvaluator password: {preview_password}\n"
        f"Application admin email: {admin_email}\nApplication admin password: {admin_password}\n"
        "No email, OAuth provider or real student identity has been configured.\n"
        "Rotate BOTH preview token and password to revoke all evaluator access.\n"
        "Browser cookie max-age is not server-side expiration of the shared preview token.\n"
    ))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--admin-email", required=True)
    args = parser.parse_args()
    initialize(args.runtime_dir, args.domain, args.admin_email)
    print("Private runtime files created. Credentials were not printed. No services started.")

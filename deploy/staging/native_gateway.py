"""Explicitly approved native-login-only staging gateway; no evaluator secret.

Removing the outer gate does not complete native authorization or permit real data.
Keep registration blocked and never forward browsers' cached Basic credentials.
"""
import argparse
from init_runtime import validate_domain


def native_gateway_config(domain: str) -> str:
    validate_domain(domain)
    upstream = '''        proxy_pass http://app:80;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Authorization $application_authorization;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $upgrade_connection;
        proxy_read_timeout 3600s;'''
    return f'''map "$request_method:$uri" $registration_blocked {{
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
    add_header Set-Cookie "__Host-LH_preview=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0" always;
    add_header X-Robots-Tag "noindex, nofollow, noarchive" always;
    location ~ ^/api/v1/attendance/sessions/[1-9][0-9]*/events/?$ {{
        proxy_buffering off;
{upstream}
    }}
    location / {{
{upstream}
    }}
}}
'''


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--confirm-remove-evaluator-gate", action="store_true", required=True)
    args = parser.parse_args()
    print(native_gateway_config(args.domain), end="")

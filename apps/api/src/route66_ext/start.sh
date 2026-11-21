#!/bin/sh
# Staging process composition: native web/collab/nginx, extension-composed API.
# Compose waits for healthy PostgreSQL/Redis before starting this container.
set -eu
export PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8
pm2 start server-wrapper.js --cwd /app/web --name learnhouse-web
pm2 start uv --cwd /app/api --name learnhouse-api -- run python -m src.route66_ext
pm2 start node --cwd /app/collab --name learnhouse-collab -- dist/index.js
pm2 status
nginx -g 'daemon off;' &
exec pm2 logs --raw

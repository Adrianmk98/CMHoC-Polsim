#!/bin/bash
# Pulls the latest compose config + image and restarts web.
# Covers cases watchtower can't: changes to docker-compose.yml itself.
set -e
cd "$(dirname "$0")"
git pull
docker compose pull web
docker compose up -d
docker image prune -f

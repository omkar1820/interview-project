#!/usr/bin/env bash
# Runs ON the EC2 host (streamed by Jenkins over SSH):  bash -s -- <IMAGE> <REGION> <DB_SECRET_ID> <APP_SECRET_ID>
set -euo pipefail
IMAGE="$1"; REGION="$2"; DB_SECRET="$3"; APP_SECRET="$4"
NAME=interview-app
ENV_FILE=/opt/interview-app.env

aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "${IMAGE%%/*}"
docker pull "$IMAGE"

umask 077
DB_JSON=$(aws secretsmanager get-secret-value --region "$REGION" --secret-id "$DB_SECRET" --query SecretString --output text)
APP_JSON=$(aws secretsmanager get-secret-value --region "$REGION" --secret-id "$APP_SECRET" --query SecretString --output text)
{
  echo "DB_HOST=$(jq -r .host <<<"$DB_JSON")"
  echo "DB_PORT=$(jq -r .port <<<"$DB_JSON")"
  echo "DB_USER=$(jq -r .username <<<"$DB_JSON")"
  echo "DB_PASSWORD=$(jq -r .password <<<"$DB_JSON")"
  echo "DB_NAME=$(jq -r .dbname <<<"$DB_JSON")"
  echo "OPENAI_API_KEY=$(jq -r '.OPENAI_API_KEY // empty' <<<"$APP_JSON")"
  echo "ADMIN_API_KEY=$(jq -r .ADMIN_API_KEY <<<"$APP_JSON")"
  echo "LLM_MODE=auto"
} > "$ENV_FILE"

# --- Sandbox runner: executes candidate code. No network, no secrets, read-only fs, no capabilities ---
RUNNER=interview-runner
SOCK_DIR=/opt/runner-sock
mkdir -p "$SOCK_DIR" && chmod 777 "$SOCK_DIR"
docker rm -f "$RUNNER" >/dev/null 2>&1 || true
docker run -d --name "$RUNNER" --restart unless-stopped --network none --read-only \
  --tmpfs /tmp:rw,nosuid,size=64m --cap-drop ALL --security-opt no-new-privileges \
  --pids-limit 128 --memory 512m --memory-swap 512m --cpus 1 --user 1002:1002 \
  -v "$SOCK_DIR":/run/runner -e RUNNER_SOCKET=/run/runner/sock \
  "$IMAGE" python -m app.runner

PREV_IMAGE=$(docker inspect -f '{{.Config.Image}}' "$NAME" 2>/dev/null || true)
docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" --restart unless-stopped -p 80:8000 -v "$SOCK_DIR":/run/runner --env-file "$ENV_FILE" "$IMAGE"

for i in $(seq 1 30); do
  if curl -fs http://localhost:80/health >/dev/null; then echo "Deployed $IMAGE - healthy"; exit 0; fi
  sleep 5
done

echo "Health check failed - rolling back" >&2
docker logs --tail 50 "$NAME" >&2 || true
docker rm -f "$NAME" >/dev/null 2>&1 || true
if [ -n "$PREV_IMAGE" ]; then
  docker run -d --name "$NAME" --restart unless-stopped -p 80:8000 -v "$SOCK_DIR":/run/runner --env-file "$ENV_FILE" "$PREV_IMAGE"
  echo "Rolled back to $PREV_IMAGE" >&2
fi
exit 1

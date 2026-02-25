#!/bin/sh
set -e

echo "Waiting for DB..."
until nc -z "$POSTGRES_HOST" "$POSTGRES_PORT"; do
  sleep 1
done

echo "Checking data file..."
ls -la /app/data
test -f /app/data/videos.json

echo "Loading DB..."
python -m scripts.load_json

echo "Starting bot..."
python -m bot.main

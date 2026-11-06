#!/bin/bash
# Keep-alive script for Render free tier.
# Pings the /health endpoint to prevent the server from sleeping.
# Usage: run via crontab every 8 minutes.

HEALTH_URL="https://nobara-backend.onrender.com/health"

response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$HEALTH_URL")

if [ "$response" = "200" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Keep-alive ping OK (HTTP $response)"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Keep-alive ping FAILED (HTTP $response)"
fi

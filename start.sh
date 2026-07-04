#!/bin/bash
set -e
echo "Reel-to-Itinerary — starting (api + redis)..."
if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  echo "Created backend/.env — add your API keys, then re-run."
fi
docker-compose up --build

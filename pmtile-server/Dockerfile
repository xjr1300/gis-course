FROM python:3.10-slim-bullseye AS base
RUN <<EOF
    apt update
    apt install -y git
    pip3 install --no-cache-dir fastapi uvicorn[standard] git+http://github.com/developmentseed/aiopmtiles
EOF

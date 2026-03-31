FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

USER root

# Minimal system dependencies for general Python development in the Brunot project.
# The base image may include a Yarn APT repo whose GPG key is missing in some environments,
# causing `apt-get update` to fail. Remove that repo before updating.
RUN rm -f /etc/apt/sources.list.d/yarn.list && \
    apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Switch back to the non-root user created by the devcontainers base image
USER vscode
WORKDIR /workspaces/Brunot


ARG BASE_IMAGE=debian:bookworm-slim@sha256:3783cc01769c7b2b1b83a5c5ad96c815348e28ed7da68e2e3687004faa906251
FROM ${BASE_IMAGE}
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 ewf-tools sleuthkit e2fsprogs \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work
CMD ["python3", "/probe/probe.py", "/work/linux-01"]

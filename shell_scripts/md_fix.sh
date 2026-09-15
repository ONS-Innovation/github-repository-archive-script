#!/bin/bash

podman run -v "$PWD:/workdir" ghcr.io/igorshubovych/markdownlint-cli:latest "**/*.md" --fix

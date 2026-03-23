#!/usr/bin/env bash
set -euo pipefail
cmake -S . -B build/native -G Ninja
cmake --build build/native
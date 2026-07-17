#!/bin/zsh
# Benchmark reference Python flynt 1.x vs the Rust flynt binary.
# Usage: ./run_bench.sh    (from bench/; prints hyperfine markdown tables)
# Env overrides:
#   CORPUS   — directory of .py files to convert (default: ../bench-corpus/django
#              relative to the repo root; clone e.g. django 1.11 there)
#   PY_FLYNT — reference python flynt executable (flynt 1.x)
set -e

ROOT=$(cd "$(dirname "$0")/.." && pwd)              # repo root
CORPUS="${CORPUS:-$ROOT/../bench-corpus/django}"
PY_FLYNT="${PY_FLYNT:-$ROOT/../.venv/bin/flynt}"
RS_FLYNT="$ROOT/target/release/flynt"
WORK=/tmp/flynt-bench

cd "$ROOT" && cargo build --release -q

# 1. Full-corpus conversion
hyperfine --warmup 1 --runs 5 \
  --prepare "rm -rf $WORK && cp -r $CORPUS $WORK" \
  --export-markdown /tmp/bench_corpus.md \
  -n "python flynt (corpus)" "$PY_FLYNT $WORK" \
  -n "flynt 2.0 (corpus)"    "$RS_FLYNT $WORK"

# 2. Idempotent re-run (already converted tree; the CI/linter scenario)
rm -rf $WORK && cp -r $CORPUS $WORK && $RS_FLYNT $WORK > /dev/null
hyperfine --warmup 1 --runs 5 \
  --export-markdown /tmp/bench_noop.md \
  -n "python flynt (no-op re-run)" "$PY_FLYNT $WORK" \
  -n "flynt 2.0 (no-op re-run)"    "$RS_FLYNT $WORK"

# 3. Single big file
BIG=$(find $CORPUS -name "*.py" -exec wc -l {} + | sort -rn | sed -n '2p' | awk '{print $2}')
echo "big file: $BIG ($(wc -l < $BIG) lines)"
hyperfine --warmup 1 --runs 10 \
  --prepare "rm -rf $WORK && mkdir -p $WORK && cp $BIG $WORK/big.py" \
  --export-markdown /tmp/bench_bigfile.md \
  -n "python flynt (1 big file)" "$PY_FLYNT $WORK/big.py" \
  -n "flynt 2.0 (1 big file)"    "$RS_FLYNT $WORK/big.py"

echo "\n\n=== corpus ===";  cat /tmp/bench_corpus.md
echo "\n=== no-op ===";     cat /tmp/bench_noop.md
echo "\n=== big file ===";  cat /tmp/bench_bigfile.md

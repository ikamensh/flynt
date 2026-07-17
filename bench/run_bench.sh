#!/bin/zsh
# Benchmark Python flynt 1.0.6 vs flynt-rs on the Django 1.11 corpus.
# Usage: ./run_bench.sh   (from flynt-rust/bench; writes results.md)
set -e

ROOT=$(cd "$(dirname "$0")/../.." && pwd)   # flynt-migration
CORPUS="$ROOT/bench-corpus/django"
PY_FLYNT="$ROOT/.venv/bin/flynt"
RS_FLYNT="$ROOT/flynt-rust/target/release/flynt-rs"
WORK=/tmp/flynt-bench

cd "$ROOT/flynt-rust" && cargo build --release -q

# 1. Full-corpus conversion (2400 files, ~530 modified)
hyperfine --warmup 1 --runs 5 \
  --prepare "rm -rf $WORK && cp -r $CORPUS $WORK" \
  --export-markdown /tmp/bench_corpus.md \
  -n "python flynt (django corpus)" "$PY_FLYNT $WORK" \
  -n "flynt-rs (django corpus)"     "$RS_FLYNT $WORK"

# 2. Idempotent re-run (already converted tree; the CI/linter scenario)
rm -rf $WORK && cp -r $CORPUS $WORK && $RS_FLYNT $WORK > /dev/null
hyperfine --warmup 1 --runs 5 \
  --export-markdown /tmp/bench_noop.md \
  -n "python flynt (no-op re-run)" "$PY_FLYNT $WORK" \
  -n "flynt-rs (no-op re-run)"     "$RS_FLYNT $WORK"

# 3. Single big file
BIG=$(find $CORPUS -name "*.py" -exec wc -l {} + | sort -rn | sed -n '2p' | awk '{print $2}')
echo "big file: $BIG ($(wc -l < $BIG) lines)"
hyperfine --warmup 1 --runs 10 \
  --prepare "rm -rf $WORK && mkdir -p $WORK && cp $BIG $WORK/big.py" \
  --export-markdown /tmp/bench_bigfile.md \
  -n "python flynt (1 big file)" "$PY_FLYNT $WORK/big.py" \
  -n "flynt-rs (1 big file)"     "$RS_FLYNT $WORK/big.py"

echo "\n\n=== corpus ===";  cat /tmp/bench_corpus.md
echo "\n=== no-op ===";     cat /tmp/bench_noop.md
echo "\n=== big file ===";  cat /tmp/bench_bigfile.md

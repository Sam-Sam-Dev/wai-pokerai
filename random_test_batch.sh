#!/bin/sh
set -eu

cd "$(dirname "$0")"

for i in $(seq 1 10); do
    echo "Run $i of 100"
    sh ./random_test.sh
done
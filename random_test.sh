#!/bin/sh
set -eu

cd "$(dirname "$0")"
export PATH="$PWD/.venv/bin:$PATH"

exec python3 - "${1:-100}" <<'PY'
import ast
import os
from pathlib import Path
import random
import shlex
import sys

try:
    matches = int(sys.argv[1])
except ValueError:
    sys.exit('The match count must be a positive integer.')
if matches < 1:
    sys.exit('The match count must be a positive integer.')

examples = []
for path in Path('examples').glob('*.py'):
    try:
        tree = ast.parse(path.read_text())
    except (SyntaxError, UnicodeError):
        continue
    if any(isinstance(node, ast.FunctionDef) and node.name == 'myAI' for node in tree.body):
        examples.append(str(path))
if len(examples) < 8:
    sys.exit('At least 8 example bots are required.')

bots = ['myAI.py'] + random.sample(examples, 8)
random.shuffle(bots)
command = ['poker', 'test', str(matches), *bots]
print(shlex.join(command), flush=True)
os.execvp('poker', command)
PY

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

bots = ['myAI2.py'] + examples
#bots = ['myAI2.py','examples/exploiter.py','examples/player_notes.py','examples/phil_hellmuth.py','myAI.py']
#bots = ['myAI2.py','examples/exploiter.py','examples/player_notes.py','myAI.py']
#bots = ['myAI.py','examples/raise_by_half_of_stack.py','examples/raise_by_pot.py','examples/call_preflop.py','examples/call.py','examples/bill_chen.py','examples/phil_hellmuth.py','examples/real_play_statistics.py']
#bots = ['myAI2.py','myAI2.py','myAI2.py','myAI2.py','myAI2.py','myAI2.py']
#bots = ['myAI2.py','examples/player_notes.py']
random.shuffle(bots)
command = ['poker', 'test', str(matches), *bots]
command = ['poker', 'test', str(50), *bots]
#command = ['poker','run',*bots]
print(shlex.join(command), flush=True)
os.execvp('poker', command)
PY

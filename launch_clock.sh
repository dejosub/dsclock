#!/bin/bash
# Launch the analog clock silently in the background

cd "$(dirname "$0")"
nohup python3 dsclock.py >/dev/null 2>&1 & disown

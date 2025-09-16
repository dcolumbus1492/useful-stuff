#!/usr/bin/env python3
"""Test status line that shows update frequency."""

import json
import sys
import time
from datetime import datetime

# Simple counter to track calls
counter_file = '/tmp/statusline_counter.txt'

try:
    with open(counter_file, 'r') as f:
        counter = int(f.read().strip())
except:
    counter = 0

counter += 1

with open(counter_file, 'w') as f:
    f.write(str(counter))

# Read input
try:
    input_data = json.loads(sys.stdin.read())
    cost = input_data.get('cost', {}).get('total_cost_usd', 0.0)
    print(f"💰 ${cost:.3f} | Updates: {counter} | Time: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
except:
    print(f"Status line test | Updates: {counter} | Time: {datetime.now().strftime('%H:%M:%S')}")
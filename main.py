"""Run the Smart Fitness Session Analyzer.

Example:
    python3 main.py --profiles data/participants.csv \
        --sessions data/fitness_sessions.csv data/fitness_sessions_invalid.csv --output output
"""

import sys

from fitness_analyzer.app import run

if __name__ == "__main__":
    sys.exit(run())

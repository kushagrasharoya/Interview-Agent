"""
config.py

This file stores settings that other files need, in one place.

Why this file exists:
Instead of writing the same file path in five different files, we write
it once here, and every other file imports it from here. If the data
files ever move, we only have to change this one line.

Nothing in this file "does" anything by itself. It just holds values.
"""

from pathlib import Path

# BASE_DIR points to the "backend" folder, no matter where the app is run
# from. Path(__file__) is this config.py file. .resolve() turns it into a
# full path. .parent goes up one folder (from app/ to backend/).
BASE_DIR = Path(__file__).resolve().parent.parent

# Folder that holds the provided JSON data files.
DATA_DIR = BASE_DIR / "data"

# Exact paths to the two provided data files.
CANDIDATES_FILE = DATA_DIR / "candidates.json"
CURRICULUM_FILE = DATA_DIR / "curriculum.json"

# Interview rules from the technical specification / hackathon brief.
# Part 2 and Part 3 will use these constants when deciding how long the
# interview should run. They live here so no one has to "guess" the
# numbers later or hard-code them inside interview logic.
MINIMUM_QUESTIONS = 8
MINIMUM_CURRICULUM_DAYS_COVERED = 4

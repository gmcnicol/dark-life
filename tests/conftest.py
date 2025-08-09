import sys
from pathlib import Path

# Ensure project root is importable when running tests with importlib mode
sys.path.append(str(Path(__file__).resolve().parents[1]))

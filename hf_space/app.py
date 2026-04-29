from __future__ import annotations
import sys
from pathlib import Path

# Add the src/ directory to the Python path so Hugging Face Spaces can find the module
sys.path.append(str(Path(__file__).parent.parent / "src"))

from persistentpoker_bench.web_ui import build_web_app

demo = build_web_app()

if __name__ == "__main__":
    demo.launch()

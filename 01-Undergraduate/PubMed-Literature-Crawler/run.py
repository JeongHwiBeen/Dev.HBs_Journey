"""Run from project root: python run.py run --profile synthetic_biology."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from pubmed_crawler.cli import main  # noqa: E402


if __name__ == '__main__':
    raise SystemExit(main())

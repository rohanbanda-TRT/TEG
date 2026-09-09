import subprocess
import sys
from pathlib import Path

from app.kb import pricing
from config.settings import get_settings


def test_load_is_cached():
    assert pricing.load_pricing() is pricing.load_pricing()


def test_ladders_have_three_tiers_except_visitor():
    ladders = pricing.load_pricing()
    for persona, ladder in ladders.items():
        if persona == "visitor":
            assert len(ladder) == 1
        else:
            assert len(ladder) == 3, persona


def test_ladder_prices_match_the_current_kb_markdown():
    root = Path(get_settings().kb_path).resolve()
    md = (root / "pricing" / "pricing_and_packages.md").read_text("utf-8")
    ladders = pricing.load_pricing()
    for ladder in ladders.values():
        for pkg in ladder:
            if pkg.price_line.startswith("ticketed entry"):
                continue  # visitor: no rupee figure to check
            # every non-visitor tier's rupee figure must appear verbatim in the KB
            rupee = pkg.price_line.split(" + GST", 1)[0].split("–", 1)[0]
            assert rupee in md, f"{pkg.name!r} price {rupee!r} not found in KB markdown"


def test_build_check_matches_committed_file():
    r = subprocess.run(
        [sys.executable, "scripts/build_kb_pricing.py", "--check"],
        capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr

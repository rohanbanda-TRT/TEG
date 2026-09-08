import subprocess
import sys

from app.kb import facts


def test_load_is_cached():
    assert facts.load() is facts.load()


def test_cleared_testimonials_well_formed():
    ts = facts.load().cleared_testimonials
    assert len(ts) >= 4
    assert all(t.name and t.quote for t in ts)
    names = {t.name for t in ts}
    assert "Sonu Sharma" in names
    assert "Kanaksinh Rana" in names


def test_exhibitor_names_contains_known():
    f = facts.load()
    assert "Third Rock Techkno" in f.exhibitor_names
    assert "ViitorCloud" in f.exhibitor_names
    assert len(f.exhibitor_names) > 50
    assert "third rock techkno" in f.exhibitor_names_lower


def test_official_industries_are_the_teg_18():
    ind = facts.load().official_industries
    assert len(ind) == 18
    assert ind[0] == "Manufacturing"
    assert "Ceramic" in ind
    assert "Textile" in ind
    # buyer industries, not exhibitor tech categories
    assert "Cybersecurity" not in ind


def test_build_check_matches_committed_file():
    r = subprocess.run(
        [sys.executable, "scripts/build_kb_facts.py", "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr

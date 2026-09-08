import pytest

from app.claude.skill_loader import SkillContent, load_skill


def _write(root, rel: str, body: str):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def test_load_skill_reads_instructions_and_references(tmp_path):
    _write(tmp_path, "teg-proposal/SKILL.md", "---\nname: teg-proposal\n---\nBody here.")
    _write(tmp_path, "teg-proposal/references/pain-library.md", "PAINS")
    _write(tmp_path, "teg-proposal/references/gold-standard.md", "GOLD")

    skill = load_skill(tmp_path, "teg-proposal",
                       references=["pain-library.md", "gold-standard.md"])

    assert isinstance(skill, SkillContent)
    assert "Body here." in skill.instructions
    assert skill.references["pain-library.md"] == "PAINS"
    assert skill.references["gold-standard.md"] == "GOLD"


def test_load_skill_strips_the_frontmatter_from_instructions(tmp_path):
    _write(tmp_path, "s/SKILL.md", "---\nname: s\ndescription: d\n---\n\nReal content.")

    skill = load_skill(tmp_path, "s")

    assert "description: d" not in skill.instructions
    assert skill.instructions.strip() == "Real content."


def test_load_skill_keeps_a_body_that_has_no_frontmatter(tmp_path):
    _write(tmp_path, "s/SKILL.md", "Just content, no frontmatter.")

    skill = load_skill(tmp_path, "s")

    assert skill.instructions.strip() == "Just content, no frontmatter."


def test_load_skill_raises_a_clear_error_for_a_missing_skill(tmp_path):
    with pytest.raises(FileNotFoundError, match="SKILL.md"):
        load_skill(tmp_path, "nope")


def test_load_skill_raises_a_clear_error_for_a_missing_reference(tmp_path):
    _write(tmp_path, "s/SKILL.md", "body")

    with pytest.raises(FileNotFoundError, match="missing.md"):
        load_skill(tmp_path, "s", references=["missing.md"])

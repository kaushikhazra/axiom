"""
Unit tests for axiom.skills.registry.SkillsRegistry -- discovery, exclusion
of malformed skills, get_skill()/SkillNotFoundError, search(), and the
empty/missing/unreadable skills_dir cases (SK-1, SK-2, SK-5, SK-6).
"""

from __future__ import annotations

import os
import stat
import sys

import pytest

from axiom.skills.port import SkillNotFoundError
from axiom.skills.registry import SkillsRegistry


def _write_skill(
    skills_dir,
    name: str,
    description: str = "A test skill.",
    body: str = "Do the thing.\n",
):
    skill_dir = skills_dir / name
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n{body}",
        encoding="utf-8",
    )


class TestEmptyOrMissingSkillsDir:
    def test_nonexistent_skills_dir_returns_empty_catalog(self, tmp_path) -> None:
        registry = SkillsRegistry(skills_dir=tmp_path / "does-not-exist")
        assert registry.list_skills() == []

    def test_empty_skills_dir_returns_empty_catalog(self, tmp_path) -> None:
        registry = SkillsRegistry(skills_dir=tmp_path)
        assert registry.list_skills() == []

    def test_search_on_missing_dir_returns_empty(self, tmp_path) -> None:
        registry = SkillsRegistry(skills_dir=tmp_path / "nope")
        assert registry.search("anything") == []

    def test_get_skill_on_missing_dir_raises_not_found(self, tmp_path) -> None:
        registry = SkillsRegistry(skills_dir=tmp_path / "nope")
        with pytest.raises(SkillNotFoundError):
            registry.get_skill("x")


class TestDiscovery:
    def test_valid_skill_discovered(self, tmp_path) -> None:
        _write_skill(tmp_path, "csv-summarizer", description="Summarizes CSV files.")
        registry = SkillsRegistry(skills_dir=tmp_path)
        specs = registry.list_skills()
        assert len(specs) == 1
        assert specs[0].name == "csv-summarizer"
        assert specs[0].description == "Summarizes CSV files."

    def test_multiple_valid_skills_discovered(self, tmp_path) -> None:
        _write_skill(tmp_path, "skill-a")
        _write_skill(tmp_path, "skill-b")
        registry = SkillsRegistry(skills_dir=tmp_path)
        names = {s.name for s in registry.list_skills()}
        assert names == {"skill-a", "skill-b"}

    def test_directory_without_skill_md_ignored(self, tmp_path) -> None:
        (tmp_path / "not-a-skill").mkdir()
        registry = SkillsRegistry(skills_dir=tmp_path)
        assert registry.list_skills() == []

    def test_non_directory_entry_ignored(self, tmp_path) -> None:
        (tmp_path / "stray-file.txt").write_text("hello", encoding="utf-8")
        registry = SkillsRegistry(skills_dir=tmp_path)
        assert registry.list_skills() == []

    def test_invalid_skill_excluded_valid_sibling_kept(self, tmp_path) -> None:
        _write_skill(tmp_path, "good-skill")
        bad_dir = tmp_path / "Bad-Skill"
        bad_dir.mkdir()
        (bad_dir / "SKILL.md").write_text(
            "---\nname: Bad-Skill\ndescription: x.\n---\nbody\n", encoding="utf-8"
        )
        registry = SkillsRegistry(skills_dir=tmp_path)
        names = {s.name for s in registry.list_skills()}
        assert names == {"good-skill"}

    def test_rediscovery_picks_up_newly_written_skill(self, tmp_path) -> None:
        """D3: no caching -- a skill written after construction is picked
        up on the next list_skills() call, without re-instantiating the
        registry."""
        registry = SkillsRegistry(skills_dir=tmp_path)
        assert registry.list_skills() == []
        _write_skill(tmp_path, "new-skill")
        assert [s.name for s in registry.list_skills()] == ["new-skill"]


class TestGetSkill:
    def test_get_skill_returns_full_content(self, tmp_path) -> None:
        _write_skill(tmp_path, "detailed-skill", body="Step 1.\nStep 2.\n")
        registry = SkillsRegistry(skills_dir=tmp_path)
        content = registry.get_skill("detailed-skill")
        assert content.name == "detailed-skill"
        assert "Step 1." in content.body

    def test_get_unknown_skill_raises_not_found(self, tmp_path) -> None:
        _write_skill(tmp_path, "exists")
        registry = SkillsRegistry(skills_dir=tmp_path)
        with pytest.raises(SkillNotFoundError, match="no such skill"):
            registry.get_skill("does-not-exist")

    def test_get_invalid_skill_raises_not_found(self, tmp_path) -> None:
        """An invalid skill is excluded the same way from get_skill() as
        from list_skills() (SK-2) -- not a different error type."""
        bad_dir = tmp_path / "Bad-Name"
        bad_dir.mkdir()
        (bad_dir / "SKILL.md").write_text(
            "---\nname: Bad-Name\ndescription: x.\n---\nbody\n", encoding="utf-8"
        )
        registry = SkillsRegistry(skills_dir=tmp_path)
        with pytest.raises(SkillNotFoundError):
            registry.get_skill("Bad-Name")


class TestSearch:
    def test_search_matches_description(self, tmp_path) -> None:
        _write_skill(tmp_path, "csv-summarizer", description="Summarizes CSV files.")
        _write_skill(tmp_path, "pdf-processing", description="Extracts PDF text.")
        registry = SkillsRegistry(skills_dir=tmp_path)
        results = registry.search("csv")
        assert [r.name for r in results] == ["csv-summarizer"]

    def test_search_matches_name(self, tmp_path) -> None:
        _write_skill(tmp_path, "csv-summarizer", description="Summarizes tabular data.")
        registry = SkillsRegistry(skills_dir=tmp_path)
        results = registry.search("summarizer")
        assert [r.name for r in results] == ["csv-summarizer"]

    def test_search_excludes_non_matching_sibling(self, tmp_path) -> None:
        _write_skill(tmp_path, "csv-summarizer", description="Summarizes CSV files.")
        _write_skill(tmp_path, "weather-lookup", description="Fetches weather data.")
        registry = SkillsRegistry(skills_dir=tmp_path)
        results = registry.search("csv")
        names = {r.name for r in results}
        assert "weather-lookup" not in names

    def test_search_case_insensitive(self, tmp_path) -> None:
        _write_skill(tmp_path, "csv-summarizer", description="Summarizes CSV files.")
        registry = SkillsRegistry(skills_dir=tmp_path)
        assert [r.name for r in registry.search("CSV")] == ["csv-summarizer"]


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="POSIX permission bits don't map cleanly to Windows ACLs",
)
class TestUnreadableSkillsDir:
    def test_permission_denied_directory_degrades_to_empty(self, tmp_path) -> None:
        _write_skill(tmp_path, "unreachable")
        os.chmod(tmp_path, stat.S_IWUSR)  # remove read+execute
        try:
            registry = SkillsRegistry(skills_dir=tmp_path)
            assert registry.list_skills() == []
        finally:
            os.chmod(tmp_path, stat.S_IRWXU)  # restore so pytest can clean up tmp_path

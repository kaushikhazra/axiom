"""
Unit tests for axiom.skills.parser -- SKILL.md frontmatter validation
against the agentskills.io spec (SK-2).
"""

from __future__ import annotations

import pytest

from axiom.skills.parser import SkillValidationError, parse_skill_md


def _write_skill(tmp_path, name: str, content: str):
    skill_dir = tmp_path / name
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(content, encoding="utf-8")
    return skill_md


class TestValidSkill:
    def test_minimal_valid_skill_parses(self, tmp_path) -> None:
        path = _write_skill(
            tmp_path,
            "pdf-processing",
            "---\nname: pdf-processing\ndescription: Extract PDF text.\n---\nDo the thing.\n",
        )
        content = parse_skill_md(path)
        assert content.name == "pdf-processing"
        assert content.description == "Extract PDF text."
        assert content.body.strip() == "Do the thing."

    def test_optional_fields_parsed(self, tmp_path) -> None:
        path = _write_skill(
            tmp_path,
            "data-analysis",
            "---\n"
            "name: data-analysis\n"
            "description: Analyze data.\n"
            "license: Apache-2.0\n"
            "metadata:\n"
            "  author: example-org\n"
            '  version: "1.0"\n'
            "---\n"
            "Body content.\n",
        )
        content = parse_skill_md(path)
        assert content.frontmatter["license"] == "Apache-2.0"
        assert content.frontmatter["metadata"] == {
            "author": "example-org",
            "version": "1.0",
        }

    def test_body_after_frontmatter_preserved(self, tmp_path) -> None:
        path = _write_skill(
            tmp_path,
            "code-review",
            "---\nname: code-review\ndescription: Review code.\n---\n# Steps\n1. Read\n2. Comment\n",
        )
        content = parse_skill_md(path)
        assert "# Steps" in content.body
        assert "1. Read" in content.body


class TestInvalidName:
    def test_uppercase_name_rejected(self, tmp_path) -> None:
        path = _write_skill(
            tmp_path,
            "PDF-Processing",
            "---\nname: PDF-Processing\ndescription: x.\n---\nbody\n",
        )
        with pytest.raises(SkillValidationError, match="lowercase"):
            parse_skill_md(path)

    def test_leading_hyphen_rejected(self, tmp_path) -> None:
        path = _write_skill(
            tmp_path, "-pdf", "---\nname: -pdf\ndescription: x.\n---\nbody\n"
        )
        with pytest.raises(SkillValidationError):
            parse_skill_md(path)

    def test_consecutive_hyphens_rejected(self, tmp_path) -> None:
        path = _write_skill(
            tmp_path,
            "pdf--processing",
            "---\nname: pdf--processing\ndescription: x.\n---\nbody\n",
        )
        with pytest.raises(SkillValidationError):
            parse_skill_md(path)

    def test_name_exceeding_64_chars_rejected(self, tmp_path) -> None:
        long_name = "a" * 65
        path = _write_skill(
            tmp_path, long_name, f"---\nname: {long_name}\ndescription: x.\n---\nbody\n"
        )
        with pytest.raises(SkillValidationError, match="1-64 chars"):
            parse_skill_md(path)

    def test_name_not_matching_directory_rejected(self, tmp_path) -> None:
        path = _write_skill(
            tmp_path,
            "actual-dir",
            "---\nname: different-name\ndescription: x.\n---\nbody\n",
        )
        with pytest.raises(SkillValidationError, match="must match parent directory"):
            parse_skill_md(path)

    def test_missing_name_rejected(self, tmp_path) -> None:
        path = _write_skill(tmp_path, "no-name", "---\ndescription: x.\n---\nbody\n")
        with pytest.raises(SkillValidationError, match="'name' is required"):
            parse_skill_md(path)


class TestInvalidDescription:
    def test_missing_description_rejected(self, tmp_path) -> None:
        path = _write_skill(tmp_path, "no-desc", "---\nname: no-desc\n---\nbody\n")
        with pytest.raises(SkillValidationError, match="'description' is required"):
            parse_skill_md(path)

    def test_description_exceeding_1024_chars_rejected(self, tmp_path) -> None:
        long_desc = "x" * 1025
        path = _write_skill(
            tmp_path,
            "long-desc",
            f"---\nname: long-desc\ndescription: {long_desc}\n---\nbody\n",
        )
        with pytest.raises(SkillValidationError, match="exceeds 1024"):
            parse_skill_md(path)


class TestMalformedFrontmatter:
    def test_missing_frontmatter_block_rejected(self, tmp_path) -> None:
        path = _write_skill(tmp_path, "no-frontmatter", "just a plain markdown file\n")
        with pytest.raises(
            SkillValidationError, match="missing or malformed frontmatter"
        ):
            parse_skill_md(path)

    def test_unclosed_frontmatter_block_rejected(self, tmp_path) -> None:
        path = _write_skill(
            tmp_path,
            "unclosed",
            "---\nname: unclosed\ndescription: x.\nbody with no closing delim\n",
        )
        with pytest.raises(SkillValidationError):
            parse_skill_md(path)

    def test_multiline_scalar_description_rejected(self, tmp_path) -> None:
        path = _write_skill(
            tmp_path,
            "multiline-desc",
            "---\nname: multiline-desc\ndescription: |\n  line one\n  line two\n---\nbody\n",
        )
        with pytest.raises(SkillValidationError, match="multi-line YAML scalar"):
            parse_skill_md(path)


class TestReadFailures:
    def test_non_utf8_file_rejected_not_crashed(self, tmp_path) -> None:
        skill_dir = tmp_path / "binary-skill"
        skill_dir.mkdir()
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_bytes(b"\xff\xfe\x00\x01not valid utf-8")
        with pytest.raises(SkillValidationError, match="failed to read"):
            parse_skill_md(skill_md)

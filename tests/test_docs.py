"""Verify documentation stays consistent with code."""

import argparse
from pathlib import Path

from scholar_paper_mcp import cli
from scholar_paper_mcp.config import Settings


def _subcommand_names(parser: argparse.ArgumentParser) -> list[str]:
    """Top-level spm subcommand names, sourced from the parser itself."""
    names: list[str] = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            names.extend(action.choices)
    return names


def test_readme_lists_all_commands() -> None:
    """README commands table must include every spm subcommand."""
    readme = Path(__file__).parent.parent / "README.md"
    text = readme.read_text()
    commands = _subcommand_names(cli.build_parser())
    assert len(commands) == 13  # 12 flat + session group
    for cmd in commands:
        assert f"spm {cmd}" in text, f"command spm {cmd} not in README"


def test_configuration_documents_all_env_vars() -> None:
    """CONFIGURATION.md must document every SPM_* env var in Settings."""
    doc = Path(__file__).parent.parent / "docs" / "CONFIGURATION.md"
    text = doc.read_text()
    settings_fields = Settings.model_fields
    for name in settings_fields:
        env_var = f"SPM_{name.upper()}"
        assert env_var in text, f"{env_var} not in CONFIGURATION.md"


def test_readme_has_no_mcp_registration_and_documents_skill() -> None:
    """README must drop MCP registration and point to the spm skill."""
    readme = Path(__file__).parent.parent / "README.md"
    text = readme.read_text()
    assert "mcpServers" not in text
    assert "skills/spm/SKILL.md" in text


def test_agents_md_mentions_current_state() -> None:
    """AGENTS.md should reflect current project state."""
    agents = Path(__file__).parent.parent / "AGENTS.md"
    text = agents.read_text()
    assert "Status" in text
    assert "spm" in text
    assert "TDD" in text
    assert "ponytail" in text

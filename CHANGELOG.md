# Changelog

## Unreleased

### Fixed
- `models.Paper`: int fields (`citation_count`, `reference_count`, `influential_citation_count`) now coerce `None` to 0 via `field_validator(mode="before")`.
- `models.Paper`: list fields (`publication_types`, `fields_of_study`, `authors`) and `is_open_access` coerce `None` to safe default.
- `models.Author`: `name` now `str | None`; list fields (`affiliations`, `papers`, `aliases`) coerce `None` to `[]`.
- `models.Paper.external_ids`: `None` values in dict are filtered out (e.g. `{"DOI": "x", "CorpusId": null}` keeps only `DOI`).
- `models.Paper.external_ids`: integer values (e.g. `CorpusId: 272999614`) coerce to string.
- `tools.authors._name_similarity`: accepts `None` inputs without crashing; returns 0.0 for None/None.
- `tools.authors.consolidate_authors`: skips None when building alias set (no more `None` in `seen_aliases`).
- `storage.citations.insert_citation` and `insert_reference`: auto-insert stub paper rows for `from_paper_id` and `to_paper_id` so FK constraints pass when cited papers are not yet cached.
- `api.client.search_authors`: uses `DEFAULT_AUTHOR_SEARCH_FIELDS` (no `aliases`, no `papers`) because S2 `/author/search` rejects those fields with HTTP 400.
- `server.py`: added 1-line docstrings to all 15 MCP tool wrappers (was missing; broke tool descriptions for AI clients).
- `exceptions.py`: removed ASCII art tree and em-dashes from module docstring.
- 4 storage modules (`authors`, `papers`, `sessions`, `__init__`) and `storage/citations.py` gained module-level docstrings.

### Changed
- Renamed `_none_to` helper to `_or_default` in `models.py` (5 uses).
- `storage/citations.py` functions now have `conn: sqlite3.Connection` type hints.
- `models.Paper._coerce_external_ids` return type widened from `dict[str, str]` to `Any` for consistency with sibling validators.
- `tests/test_models.py`: moved `from datetime import timedelta` to module-level import (was duplicated inside 6 test functions).
- `tests/test_client.py::test_search_authors_omits_unsupported_fields`: added explicit `@pytest.mark.asyncio` marker for consistency.

### Tests
- +6 new tests: null int fields, null lists, null bool, external_ids None filtering, name_similarity None handling, search_authors field filtering, plus 2 stub-paper FK tests.
- Total: 276 passing (was 266), 1 deselected (`test_no_api_key_header_when_not_configured` requires `SPM_API_KEY` unset in env).

## v0.1.0

Initial feature-complete release. 14 of 14 planned issues done. 266 tests pass.

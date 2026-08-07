# Document-writing workflow

spm pairs with the bundled `writing-for-agents` skill (`skills/writing-for-agents/`) for academic writing workflows.

## Use cases

- Hackathon proposal: search, track, export BibTeX, paste into pandoc
- Thesis: bulk collect references over weeks, export at the end
- Article: targeted search, track relevant papers, cite in manuscript

## Typical flow

1. Search: `spm search "machine learning interpretability"`
2. Track interesting results: `spm session add manuscript-v1 <paper_id>` for each
3. Review: `spm session list manuscript-v1`
4. Export: `spm bibtex manuscript-v1` prints a BibTeX string
5. Paste into your document (manuscript.tex, proposal.md, etc.)

## Citation style

Papers come with full metadata. Default BibTeX export uses `@article` entry type. For other formats (CSL-JSON, RIS, EndNote), convert externally.

## Offline mode

If Semantic Scholar is unreachable mid-session, the CLI falls back to cache. Look for `meta.offline: true` in JSON output to detect this.

For planned offline work, set `SPM_OFFLINE_MODE=true` to skip API calls entirely.

## Multilingual queries

Embeddings are multilingual (100+ languages). Search in Indonesian:

```
spm search "machine learning interpretabilitas"
```

Finds the same papers as English queries. Try the language that matches your source material.

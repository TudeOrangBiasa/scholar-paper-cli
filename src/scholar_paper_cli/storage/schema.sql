CREATE TABLE IF NOT EXISTS papers (
    paper_id TEXT PRIMARY KEY NOT NULL,
    title TEXT,
    abstract TEXT,
    year INTEGER,
    venue TEXT,
    publication_types TEXT,       -- JSON array
    fields_of_study TEXT,         -- JSON array
    citation_count INTEGER NOT NULL DEFAULT 0,
    reference_count INTEGER NOT NULL DEFAULT 0,
    influential_citation_count INTEGER NOT NULL DEFAULT 0,
    is_open_access INTEGER NOT NULL DEFAULT 0,
    open_access_pdf_url TEXT,
    external_ids TEXT,            -- JSON object with DOI, ArXiv, etc.
    authors_json TEXT,            -- JSON array of author briefs
    embedding BLOB,               -- 384-dim float32 raw vector
    raw_json TEXT,                -- full API response JSON
    fetched_at TEXT NOT NULL,
    ttl_until TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(year);
CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(json_extract(external_ids, '$.DOI'));
CREATE INDEX IF NOT EXISTS idx_papers_arxiv ON papers(json_extract(external_ids, '$.ArXiv'));

CREATE TABLE IF NOT EXISTS authors (
    author_id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    affiliations TEXT,             -- JSON array
    h_index INTEGER,
    paper_count INTEGER,
    aliases TEXT,                  -- JSON array
    papers_json TEXT,              -- JSON array of paper briefs
    raw_json TEXT,
    fetched_at TEXT NOT NULL,
    ttl_until TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_authors_name ON authors(name);

CREATE TABLE IF NOT EXISTS paper_authors (
    paper_id TEXT NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    author_id TEXT NOT NULL REFERENCES authors(author_id) ON DELETE CASCADE,
    author_position INTEGER NOT NULL,
    PRIMARY KEY (paper_id, author_id)
);

CREATE INDEX IF NOT EXISTS idx_paper_authors_author ON paper_authors(author_id);

CREATE TABLE IF NOT EXISTS citations (
    from_paper_id TEXT NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    to_paper_id TEXT NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    context_intent TEXT,           -- JSON array
    is_influential INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (from_paper_id, to_paper_id)
);

CREATE INDEX IF NOT EXISTS idx_citations_to ON citations(to_paper_id);

CREATE TABLE IF NOT EXISTS paper_references (
    from_paper_id TEXT NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    to_paper_id TEXT NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    is_influential INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (from_paper_id, to_paper_id)
);

CREATE INDEX IF NOT EXISTS idx_paper_references_to ON paper_references(to_paper_id);

CREATE TABLE IF NOT EXISTS session_papers (
    session_id TEXT NOT NULL,
    paper_id TEXT NOT NULL REFERENCES papers(paper_id) ON DELETE CASCADE,
    added_at TEXT NOT NULL,
    PRIMARY KEY (session_id, paper_id)
);

CREATE INDEX IF NOT EXISTS idx_session_papers_session ON session_papers(session_id);

CREATE VIRTUAL TABLE IF NOT EXISTS embeddings_vec USING vec0(
    paper_id TEXT PRIMARY KEY,
    embedding float[384]
);

CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
    title,
    abstract,
    content='papers',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS papers_ai AFTER INSERT ON papers BEGIN
    INSERT INTO papers_fts(rowid, title, abstract)
    VALUES (new.rowid, new.title, new.abstract);
END;

CREATE TRIGGER IF NOT EXISTS papers_ad AFTER DELETE ON papers BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, title, abstract)
    VALUES ('delete', old.rowid, old.title, old.abstract);
END;

CREATE TRIGGER IF NOT EXISTS papers_au AFTER UPDATE ON papers BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, title, abstract)
    VALUES ('delete', old.rowid, old.title, old.abstract);
    INSERT INTO papers_fts(rowid, title, abstract)
    VALUES (new.rowid, new.title, new.abstract);
END;

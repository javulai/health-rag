"""Initial knowledge schema (fixed 384-dimensional embedding space)."""

from alembic import op

revision = "0001_knowledge"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE EXTENSION IF NOT EXISTS vector""")
    op.execute("""
CREATE TABLE sources (
    id UUID NOT NULL,
    canonical_url TEXT NOT NULL,
    title TEXT NOT NULL,
    organization TEXT NOT NULL,
    language VARCHAR(16) NOT NULL,
    topic TEXT NOT NULL,
    reuse_note TEXT,
    enabled BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (canonical_url)
)

""")
    op.execute("""
CREATE TABLE document_versions (
    id UUID NOT NULL,
    source_id UUID NOT NULL,
    version_no INTEGER NOT NULL,
    checksum VARCHAR(64) NOT NULL,
    source_published_at DATE,
    source_updated_at DATE,
    fetched_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    file_path TEXT NOT NULL,
    status VARCHAR(16) NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_dimension INTEGER NOT NULL,
    chunking_config JSONB NOT NULL,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    reviewer_ref TEXT,
    activated_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (id),
    UNIQUE (source_id, version_no),
    CHECK (version_no > 0),
    CHECK (status IN ('staging', 'active', 'retired', 'failed')),
    CHECK (embedding_dimension = 384),
    FOREIGN KEY(source_id) REFERENCES sources (id) ON DELETE RESTRICT
)

""")
    op.execute(
        """CREATE UNIQUE INDEX uq_source_active ON document_versions (source_id)
        WHERE status = 'active'"""
    )
    op.execute("""
CREATE TABLE chunks (
    id UUID NOT NULL,
    document_version_id UUID NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    locator TEXT NOT NULL,
    language VARCHAR(16) NOT NULL,
    token_count INTEGER NOT NULL,
    embedding VECTOR(384),
    PRIMARY KEY (id),
    UNIQUE (document_version_id, chunk_index),
    CHECK (chunk_index >= 0),
    CHECK (token_count > 0),
    FOREIGN KEY(document_version_id) REFERENCES document_versions (id) ON DELETE RESTRICT
)

""")
    op.execute("""CREATE INDEX ix_chunks_document_version ON chunks (document_version_id)""")


def downgrade():
    op.drop_table("chunks")
    op.drop_table("document_versions")
    op.drop_table("sources")
    # The shared vector extension is intentionally retained.

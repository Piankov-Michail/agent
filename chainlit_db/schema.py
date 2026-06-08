CHAINLIT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    "id" TEXT PRIMARY KEY,
    "identifier" TEXT,
    "createdAt" TEXT,
    "metadata" JSONB
);

CREATE TABLE IF NOT EXISTS threads (
    "id" TEXT PRIMARY KEY,
    "createdAt" TEXT,
    "name" TEXT,
    "userId" TEXT,
    "userIdentifier" TEXT,
    "tags" JSONB,
    "metadata" JSONB
);

CREATE TABLE IF NOT EXISTS steps (
    "id" TEXT PRIMARY KEY,
    "name" TEXT,
    "type" TEXT,
    "threadId" TEXT,
    "parentId" TEXT,
    "streaming" BOOLEAN,
    "waitForAnswer" BOOLEAN,
    "isError" BOOLEAN,
    "metadata" JSONB,
    "tags" JSONB,
    "input" TEXT,
    "output" TEXT,
    "createdAt" TEXT,
    "start" TEXT,
    "end" TEXT,
    "generation" JSONB,
    "showInput" TEXT,
    "language" TEXT,
    "defaultOpen" BOOLEAN,
    "autoCollapse" BOOLEAN
);

CREATE TABLE IF NOT EXISTS feedbacks (
    "id" TEXT PRIMARY KEY,
    "forId" TEXT,
    "value" DOUBLE PRECISION,
    "comment" TEXT
);

CREATE TABLE IF NOT EXISTS elements (
    "id" TEXT PRIMARY KEY,
    "threadId" TEXT,
    "type" TEXT,
    "chainlitKey" TEXT,
    "url" TEXT,
    "objectKey" TEXT,
    "name" TEXT,
    "display" TEXT,
    "size" TEXT,
    "language" TEXT,
    "page" TEXT,
    "forId" TEXT,
    "mime" TEXT,
    "props" TEXT,
    "autoPlay" TEXT,
    "playerConfig" TEXT
);

ALTER TABLE steps ADD COLUMN IF NOT EXISTS "defaultOpen" BOOLEAN;
ALTER TABLE steps ADD COLUMN IF NOT EXISTS "autoCollapse" BOOLEAN;

ALTER TABLE steps ALTER COLUMN tags TYPE JSONB USING NULLIF(tags, '')::jsonb;
ALTER TABLE steps ALTER COLUMN metadata TYPE JSONB USING NULLIF(metadata, '')::jsonb;
ALTER TABLE steps ALTER COLUMN generation TYPE JSONB USING NULLIF(generation, '')::jsonb;
ALTER TABLE threads ALTER COLUMN tags TYPE JSONB USING NULLIF(tags, '')::jsonb;
ALTER TABLE threads ALTER COLUMN metadata TYPE JSONB USING NULLIF(metadata, '')::jsonb;
ALTER TABLE users ALTER COLUMN metadata TYPE JSONB USING NULLIF(metadata, '')::jsonb;
"""

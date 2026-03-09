
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    wechat_id VARCHAR(64) NOT NULL UNIQUE,

    birth_date DATE,
    birth_time TIME,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,

    chart_snapshot JSONB,
    chart_summary TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_wechat_id ON users(wechat_id);

CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    summary TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_conversations_user_id ON conversations(user_id);

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,

    role VARCHAR(16) NOT NULL CHECK (role IN ('system', 'user', 'assistant')),

    content TEXT NOT NULL,

    token_count INTEGER,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);

CREATE TABLE system_prompt (
    id INTEGER PRIMARY KEY DEFAULT 1,
    content TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ
);
-- ============================================================
-- MenuElf Friends System Schema
-- Migration 002 – Supabase / Postgres
-- ============================================================

-- 1. User profiles (public info)
CREATE TABLE IF NOT EXISTS user_profiles (
    id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    username text UNIQUE NOT NULL,
    display_name text,
    avatar_emoji text DEFAULT '🧝',
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- Username must be lowercase, alphanumeric + underscores, 3-20 chars
ALTER TABLE user_profiles ADD CONSTRAINT username_format
     CHECK (username ~ '^[a-z0-9_]{3,20}$');

-- 2. Friend requests
CREATE TABLE IF NOT EXISTS friend_requests (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    from_user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
    to_user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'declined')),
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    UNIQUE(from_user_id, to_user_id)
);

-- 3. Friendships (created when a request is accepted)
CREATE TABLE IF NOT EXISTS friendships (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_a_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
    user_b_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at timestamptz DEFAULT now(),
    UNIQUE(user_a_id, user_b_id),
    CHECK (user_a_id < user_b_id)  -- Enforce ordering to prevent duplicates
);

-- 4. Indexes
CREATE INDEX idx_friend_requests_to ON friend_requests(to_user_id, status);
CREATE INDEX idx_friend_requests_from ON friend_requests(from_user_id, status);
CREATE INDEX idx_friendships_a ON friendships(user_a_id);
CREATE INDEX idx_friendships_b ON friendships(user_b_id);
CREATE INDEX idx_user_profiles_username ON user_profiles(username);

-- 5. RLS policies
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE friend_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE friendships ENABLE ROW LEVEL SECURITY;

-- Profiles: anyone can read, only own can update/insert
CREATE POLICY "profiles_read" ON user_profiles FOR SELECT USING (true);
CREATE POLICY "profiles_update" ON user_profiles FOR UPDATE USING (auth.uid() = id);
CREATE POLICY "profiles_insert" ON user_profiles FOR INSERT WITH CHECK (auth.uid() = id);

-- Friend requests: can see own sent/received, can insert own, recipient can update
CREATE POLICY "requests_read" ON friend_requests FOR SELECT
     USING (auth.uid() = from_user_id OR auth.uid() = to_user_id);
CREATE POLICY "requests_insert" ON friend_requests FOR INSERT
     WITH CHECK (auth.uid() = from_user_id);
CREATE POLICY "requests_update" ON friend_requests FOR UPDATE
     USING (auth.uid() = to_user_id);

-- Friendships: can see own
CREATE POLICY "friendships_read" ON friendships FOR SELECT
     USING (auth.uid() = user_a_id OR auth.uid() = user_b_id);

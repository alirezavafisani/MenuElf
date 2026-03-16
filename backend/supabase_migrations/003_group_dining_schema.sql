-- ============================================================
-- MenuElf Group Dining Schema
-- Migration 003 – Supabase / Postgres
-- ============================================================

-- 1. Dining plans (groups)
CREATE TABLE IF NOT EXISTS dining_plans (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    creator_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
    name text NOT NULL,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'decided', 'cancelled')),
    decided_restaurant_slug text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

-- 2. Plan members
CREATE TABLE IF NOT EXISTS dining_plan_members (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    plan_id uuid REFERENCES dining_plans(id) ON DELETE CASCADE,
    user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'invited' CHECK (status IN ('invited', 'joined', 'declined')),
    joined_at timestamptz,
    created_at timestamptz DEFAULT now(),
    UNIQUE(plan_id, user_id)
);

-- 3. Group chat messages
CREATE TABLE IF NOT EXISTS group_messages (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    plan_id uuid REFERENCES dining_plans(id) ON DELETE CASCADE,
    sender_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    sender_type text NOT NULL DEFAULT 'user' CHECK (sender_type IN ('user', 'ai')),
    content text NOT NULL,
    created_at timestamptz DEFAULT now()
);

-- 4. Indexes
CREATE INDEX idx_dining_plan_members_plan ON dining_plan_members(plan_id);
CREATE INDEX idx_dining_plan_members_user ON dining_plan_members(user_id, status);
CREATE INDEX idx_group_messages_plan ON group_messages(plan_id, created_at);
CREATE INDEX idx_dining_plans_creator ON dining_plans(creator_id);

-- 5. RLS
ALTER TABLE dining_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE dining_plan_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE group_messages ENABLE ROW LEVEL SECURITY;

-- Plans: members can see
CREATE POLICY "plans_read" ON dining_plans FOR SELECT USING (
    id IN (SELECT plan_id FROM dining_plan_members WHERE user_id = auth.uid())
    OR creator_id = auth.uid()
);
CREATE POLICY "plans_insert" ON dining_plans FOR INSERT WITH CHECK (auth.uid() = creator_id);
CREATE POLICY "plans_update" ON dining_plans FOR UPDATE USING (auth.uid() = creator_id);

-- Members: can see own plans' members
CREATE POLICY "members_read" ON dining_plan_members FOR SELECT USING (
    plan_id IN (SELECT plan_id FROM dining_plan_members AS dpm WHERE dpm.user_id = auth.uid())
);
CREATE POLICY "members_insert" ON dining_plan_members FOR INSERT WITH CHECK (
    plan_id IN (SELECT id FROM dining_plans WHERE creator_id = auth.uid())
);
CREATE POLICY "members_update" ON dining_plan_members FOR UPDATE USING (user_id = auth.uid());

-- Messages: members can read and insert
CREATE POLICY "messages_read" ON group_messages FOR SELECT USING (
    plan_id IN (SELECT plan_id FROM dining_plan_members WHERE user_id = auth.uid())
);
CREATE POLICY "messages_insert" ON group_messages FOR INSERT WITH CHECK (
    plan_id IN (SELECT plan_id FROM dining_plan_members WHERE user_id = auth.uid() AND status = 'joined')
);

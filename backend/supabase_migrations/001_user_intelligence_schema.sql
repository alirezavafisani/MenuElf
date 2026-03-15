-- ============================================================
-- MenuElf User Intelligence Schema
-- Migration 001 – Supabase / Postgres
-- ============================================================

-- 1. user_taste_profiles
CREATE TABLE IF NOT EXISTS user_taste_profiles (
    id                    uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    spice_tolerance       float NOT NULL DEFAULT 0.5 CHECK (spice_tolerance >= 0.0 AND spice_tolerance <= 1.0),
    sweetness_preference  float NOT NULL DEFAULT 0.5 CHECK (sweetness_preference >= 0.0 AND sweetness_preference <= 1.0),
    adventurousness       float NOT NULL DEFAULT 0.5 CHECK (adventurousness >= 0.0 AND adventurousness <= 1.0),
    price_comfort         float NOT NULL DEFAULT 0.5 CHECK (price_comfort >= 0.0 AND price_comfort <= 1.0),
    protein_preference    jsonb NOT NULL DEFAULT '{"beef":0.5,"chicken":0.5,"pork":0.5,"fish":0.5,"vegetarian":0.5,"vegan":0.3}',
    cuisine_preferences   jsonb NOT NULL DEFAULT '{"italian":0.5,"mexican":0.5,"japanese":0.5,"chinese":0.5,"indian":0.5,"thai":0.5,"korean":0.5,"mediterranean":0.5,"american":0.5,"french":0.5,"vietnamese":0.5,"middle_eastern":0.5}',
    dietary_restrictions  jsonb NOT NULL DEFAULT '[]',
    texture_preferences   jsonb NOT NULL DEFAULT '{"crispy":0.5,"creamy":0.5,"crunchy":0.5,"soupy":0.5,"chewy":0.5}',
    meal_size_preference  float NOT NULL DEFAULT 0.5 CHECK (meal_size_preference >= 0.0 AND meal_size_preference <= 1.0),
    onboarding_completed  boolean NOT NULL DEFAULT false,
    profile_version       integer NOT NULL DEFAULT 1,
    last_updated          timestamptz NOT NULL DEFAULT now(),
    created_at            timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE user_taste_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own taste profile"
    ON user_taste_profiles FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can insert own taste profile"
    ON user_taste_profiles FOR INSERT
    WITH CHECK (auth.uid() = id);

CREATE POLICY "Users can update own taste profile"
    ON user_taste_profiles FOR UPDATE
    USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);


-- 2. interaction_logs
CREATE TABLE IF NOT EXISTS interaction_logs (
    id                uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id           uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    interaction_type  text NOT NULL CHECK (interaction_type IN (
        'chat_message', 'dish_view', 'dish_save', 'dish_unsave',
        'restaurant_tap', 'restaurant_chat_open', 'search_query',
        'filter_apply', 'onboarding_choice'
    )),
    payload           jsonb NOT NULL DEFAULT '{}',
    created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_interaction_logs_user_type_time
    ON interaction_logs (user_id, interaction_type, created_at);

ALTER TABLE interaction_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can insert own interaction logs"
    ON interaction_logs FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can read own interaction logs"
    ON interaction_logs FOR SELECT
    USING (auth.uid() = user_id);


-- 3. saved_dishes
CREATE TABLE IF NOT EXISTS saved_dishes (
    id               uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id          uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    dish_name        text NOT NULL,
    restaurant_slug  text NOT NULL,
    restaurant_name  text NOT NULL,
    price            numeric,
    category         text,
    dietary_info     jsonb NOT NULL DEFAULT '[]',
    notes            text,
    saved_at         timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE saved_dishes
    ADD CONSTRAINT uq_saved_dishes_user_dish_restaurant
    UNIQUE (user_id, dish_name, restaurant_slug);

ALTER TABLE saved_dishes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own saved dishes"
    ON saved_dishes FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own saved dishes"
    ON saved_dishes FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own saved dishes"
    ON saved_dishes FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own saved dishes"
    ON saved_dishes FOR DELETE
    USING (auth.uid() = user_id);


-- 4. chat_sessions
CREATE TABLE IF NOT EXISTS chat_sessions (
    id                           uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id                      uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    restaurant_slug              text NOT NULL,
    messages                     jsonb NOT NULL DEFAULT '[]',
    preference_signals_extracted jsonb NOT NULL DEFAULT '[]',
    created_at                   timestamptz NOT NULL DEFAULT now(),
    updated_at                   timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own chat sessions"
    ON chat_sessions FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own chat sessions"
    ON chat_sessions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own chat sessions"
    ON chat_sessions FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own chat sessions"
    ON chat_sessions FOR DELETE
    USING (auth.uid() = user_id);


-- 5. onboarding_questions (public read-only, no RLS)
CREATE TABLE IF NOT EXISTS onboarding_questions (
    id                serial PRIMARY KEY,
    question_index    integer NOT NULL CHECK (question_index BETWEEN 1 AND 5),
    option_a_image_url text NOT NULL,
    option_a_label     text NOT NULL,
    option_a_signals   jsonb NOT NULL,
    option_b_image_url text NOT NULL,
    option_b_label     text NOT NULL,
    option_b_signals   jsonb NOT NULL,
    is_active          boolean NOT NULL DEFAULT true,
    created_at         timestamptz NOT NULL DEFAULT now()
);

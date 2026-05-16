-- ============================================================
-- DiabetesSense AI — Supabase Schema
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─────────────────────────────────────────────────────────────
-- TABLE 1: user_profiles
-- Extends Supabase auth.users with health + gamification data
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.user_profiles (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  auth_user_id    UUID UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
  username        TEXT,
  date_of_birth   DATE,
  gender          SMALLINT,             -- 1=Male, 2=Female
  -- Gamification
  total_points    INT NOT NULL DEFAULT 0,
  level           INT NOT NULL DEFAULT 1,
  streak_days     INT NOT NULL DEFAULT 0,
  last_active_at  TIMESTAMPTZ,
  scans_completed INT NOT NULL DEFAULT 0,
  -- Preferences
  units           TEXT DEFAULT 'metric', -- 'metric' | 'imperial'
  notifications   BOOLEAN DEFAULT TRUE,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- RLS: users can only read/write their own profile
ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own profile"
  ON public.user_profiles FOR SELECT
  USING (auth.uid() = auth_user_id);

CREATE POLICY "Users update own profile"
  ON public.user_profiles FOR UPDATE
  USING (auth.uid() = auth_user_id);

-- ─────────────────────────────────────────────────────────────
-- TABLE 2: scans
-- Each uploaded medical image creates one scan record
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.scans (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id         UUID REFERENCES public.user_profiles(id) ON DELETE SET NULL,
  document_type   TEXT DEFAULT 'medical_report',
  filename        TEXT,
  storage_path    TEXT,               -- Supabase Storage path
  -- OCR results
  ocr_text        TEXT,
  ocr_confidence  FLOAT,
  ocr_engine      TEXT,
  -- Extracted parameters (stored as JSONB for flexibility)
  extracted_params JSONB DEFAULT '{}',
  completeness_score FLOAT DEFAULT 0,
  -- Processing status
  status          TEXT DEFAULT 'pending',  -- pending|processing|complete|failed
  error_message   TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.scans ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own scans"
  ON public.scans FOR SELECT
  USING (
    user_id IN (
      SELECT id FROM public.user_profiles WHERE auth_user_id = auth.uid()
    )
  );

CREATE POLICY "Users insert own scans"
  ON public.scans FOR INSERT
  WITH CHECK (
    user_id IN (
      SELECT id FROM public.user_profiles WHERE auth_user_id = auth.uid()
    )
  );

-- Index for fast user scan retrieval
CREATE INDEX idx_scans_user_id ON public.scans(user_id);
CREATE INDEX idx_scans_created_at ON public.scans(created_at DESC);

-- ─────────────────────────────────────────────────────────────
-- TABLE 3: predictions
-- ML model results for each scan
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.predictions (
  id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  scan_id               UUID REFERENCES public.scans(id) ON DELETE CASCADE,
  user_id               UUID REFERENCES public.user_profiles(id) ON DELETE SET NULL,
  -- Risk output
  risk_class            SMALLINT NOT NULL,  -- 0=Low, 1=Medium, 2=High
  risk_level            TEXT NOT NULL,
  confidence            FLOAT,
  health_score          INT,
  diabetes_probability  FLOAT,
  prediabetes_probability FLOAT,
  normal_probability    FLOAT,
  -- Model details
  model_version         TEXT DEFAULT '2.0',
  top_risk_factors      JSONB DEFAULT '[]',
  clinical_explanation  TEXT,
  -- Gamification
  points_awarded        INT DEFAULT 0,
  created_at            TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.predictions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own predictions"
  ON public.predictions FOR SELECT
  USING (
    user_id IN (
      SELECT id FROM public.user_profiles WHERE auth_user_id = auth.uid()
    )
  );

CREATE INDEX idx_predictions_user_id ON public.predictions(user_id);
CREATE INDEX idx_predictions_created_at ON public.predictions(created_at DESC);

-- ─────────────────────────────────────────────────────────────
-- TABLE 4: recommendations
-- AI-generated recommendations per prediction
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.recommendations (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  prediction_id   UUID REFERENCES public.predictions(id) ON DELETE CASCADE,
  user_id         UUID REFERENCES public.user_profiles(id) ON DELETE SET NULL,
  risk_level      TEXT NOT NULL,
  recommendations JSONB DEFAULT '[]',
  ai_message      TEXT,
  daily_goal      TEXT,
  -- Completion tracking (gamification)
  completed_ids   JSONB DEFAULT '[]',   -- array of completed recommendation ids
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.recommendations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own recommendations"
  ON public.recommendations FOR SELECT
  USING (
    user_id IN (
      SELECT id FROM public.user_profiles WHERE auth_user_id = auth.uid()
    )
  );

-- ─────────────────────────────────────────────────────────────
-- TABLE 5: gamification_events
-- Append-only log of every points transaction
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.gamification_events (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id     UUID REFERENCES public.user_profiles(id) ON DELETE CASCADE,
  event_type  TEXT NOT NULL,  -- 'scan_complete'|'recommendation_done'|'streak'|'mission'
  points      INT NOT NULL,
  description TEXT,
  metadata    JSONB DEFAULT '{}',
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.gamification_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own events"
  ON public.gamification_events FOR SELECT
  USING (
    user_id IN (
      SELECT id FROM public.user_profiles WHERE auth_user_id = auth.uid()
    )
  );

CREATE INDEX idx_events_user_id ON public.gamification_events(user_id);

-- ─────────────────────────────────────────────────────────────
-- TABLE 6: missions
-- Template missions library
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.missions (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  title       TEXT NOT NULL,
  description TEXT,
  category    TEXT,                -- 'diet'|'exercise'|'sleep'|'monitoring'
  points      INT NOT NULL,
  difficulty  TEXT DEFAULT 'easy', -- 'easy'|'medium'|'hard'
  is_active   BOOLEAN DEFAULT TRUE,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Seed missions
INSERT INTO public.missions (title, description, category, points, difficulty) VALUES
  ('First scan',          'Upload your first medical report',                     'monitoring', 50,  'easy'),
  ('Daily walker',        'Log 30 minutes of walking 5 days in a row',            'exercise',   75,  'easy'),
  ('Sugar-free week',     'Go 7 days without sugary drinks',                      'diet',       100, 'medium'),
  ('Sleep champion',      'Get 8+ hours of sleep for 5 consecutive nights',       'sleep',      80,  'medium'),
  ('Hydration hero',      'Drink 8 glasses of water daily for a week',            'diet',       60,  'easy'),
  ('Check-up warrior',    'Schedule and complete a health check-up',              'monitoring', 150, 'hard'),
  ('Veggie boost',        'Eat vegetables with every meal for 5 days',            'diet',       70,  'medium'),
  ('Stress buster',       'Complete 10 minutes of meditation 3 days in a row',   'sleep',      60,  'easy'),
  ('10-day streak',       'Use DiabetesSense for 10 days in a row',              'monitoring', 200, 'hard'),
  ('Family shield',       'Share your health report with a family member',        'monitoring', 40,  'easy');

-- ─────────────────────────────────────────────────────────────
-- TABLE 7: user_missions
-- Tracks each user's mission progress
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.user_missions (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id     UUID REFERENCES public.user_profiles(id) ON DELETE CASCADE,
  mission_id  UUID REFERENCES public.missions(id) ON DELETE CASCADE,
  status      TEXT DEFAULT 'pending', -- 'pending'|'in_progress'|'completed'
  started_at  TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  UNIQUE(user_id, mission_id)
);

ALTER TABLE public.user_missions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own missions"
  ON public.user_missions FOR ALL
  USING (
    user_id IN (
      SELECT id FROM public.user_profiles WHERE auth_user_id = auth.uid()
    )
  );

-- ─────────────────────────────────────────────────────────────
-- TABLE 8: badges
-- Achievement badges library
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.badges (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name        TEXT UNIQUE NOT NULL,
  description TEXT,
  icon        TEXT,          -- emoji or icon name
  condition   TEXT           -- description of how to earn
);

INSERT INTO public.badges (name, description, icon, condition) VALUES
  ('First step',    'Uploaded your first medical report',      '🩺', 'Complete first scan'),
  ('Streak starter','Logged in 3 days in a row',               '🔥', '3-day login streak'),
  ('Sugar warrior', 'Went sugar-free for a full week',         '🍃', 'Complete sugar-free week mission'),
  ('Healthy heart', 'Maintained low risk for 3 consecutive scans', '❤️', '3 consecutive Low risk results'),
  ('Level up',      'Reached Level 5',                         '⭐', 'Reach level 5');

-- ─────────────────────────────────────────────────────────────
-- TABLE 9: user_badges (junction)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.user_badges (
  user_id     UUID REFERENCES public.user_profiles(id) ON DELETE CASCADE,
  badge_id    UUID REFERENCES public.badges(id) ON DELETE CASCADE,
  earned_at   TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (user_id, badge_id)
);

-- ─────────────────────────────────────────────────────────────
-- LEADERBOARD VIEW (public read — anonymised)
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW public.leaderboard AS
SELECT
  ROW_NUMBER() OVER (ORDER BY total_points DESC) AS rank,
  COALESCE(username, 'Anonymous') AS username,
  total_points,
  level,
  streak_days
FROM public.user_profiles
WHERE total_points > 0
ORDER BY total_points DESC
LIMIT 100;

-- ─────────────────────────────────────────────────────────────
-- FUNCTION: award points + update level atomically
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.award_points(
  p_user_id   UUID,
  p_points    INT,
  p_event     TEXT,
  p_desc      TEXT DEFAULT NULL
) RETURNS VOID AS $$
DECLARE
  new_total INT;
  new_level INT;
BEGIN
  -- Update total points
  UPDATE public.user_profiles
  SET total_points = total_points + p_points,
      updated_at = NOW()
  WHERE id = p_user_id
  RETURNING total_points INTO new_total;

  -- Compute level (every 100 points = 1 level)
  new_level := GREATEST(1, FLOOR(new_total / 100) + 1);
  UPDATE public.user_profiles SET level = new_level WHERE id = p_user_id;

  -- Log event
  INSERT INTO public.gamification_events (user_id, event_type, points, description)
  VALUES (p_user_id, p_event, p_points, p_desc);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

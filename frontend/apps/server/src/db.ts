import { Pool } from "pg";

const pool = new Pool({
  connectionString:
    process.env.DATABASE_URL ||
    "postgresql://postgres:VVITIjFrjZOkNZTXjJoKBLxSnxrzVnqs@junction.proxy.rlwy.net:20463/railway",
  ssl: false,
});

export async function initDb() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS users (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      first_name TEXT NOT NULL,
      email TEXT UNIQUE,
      general_goal TEXT,
      quest_budget REAL DEFAULT 25,
      difficulty INTEGER DEFAULT 1,
      frequency INTEGER DEFAULT 1,
      pool_amount REAL DEFAULT 50,
      group_mode INTEGER DEFAULT 0,
      group_name TEXT,
      wallet_address TEXT,
      xp INTEGER DEFAULT 0,
      level INTEGER DEFAULT 1,
      created_at TIMESTAMPTZ DEFAULT NOW(),
      updated_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS user_friends (
      id SERIAL PRIMARY KEY,
      user_id UUID NOT NULL REFERENCES users(id),
      friend_id UUID REFERENCES users(id),
      phone TEXT NOT NULL,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS quests (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id UUID NOT NULL REFERENCES users(id),
      title TEXT NOT NULL,
      description TEXT,
      tone TEXT,
      status TEXT NOT NULL DEFAULT 'active',
      grade TEXT,
      xp_earned INTEGER DEFAULT 0,
      reward_amount REAL DEFAULT 0,
      time_limit_minutes INTEGER,
      duration_minutes INTEGER,
      started_at TIMESTAMPTZ DEFAULT NOW(),
      completed_at TIMESTAMPTZ,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS quest_steps (
      id SERIAL PRIMARY KEY,
      quest_id UUID NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
      step_order INTEGER NOT NULL,
      type TEXT NOT NULL DEFAULT 'action',
      title TEXT NOT NULL,
      subtitle TEXT,
      icon TEXT DEFAULT 'star',
      done BOOLEAN DEFAULT false,
      active BOOLEAN DEFAULT false,
      content TEXT,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS quest_actions (
      id SERIAL PRIMARY KEY,
      quest_id UUID NOT NULL REFERENCES quests(id) ON DELETE CASCADE,
      user_id UUID NOT NULL REFERENCES users(id),
      action TEXT NOT NULL,
      xp INTEGER DEFAULT 0,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS transactions (
      id SERIAL PRIMARY KEY,
      user_id UUID NOT NULL REFERENCES users(id),
      type TEXT NOT NULL,
      label TEXT NOT NULL,
      amount REAL NOT NULL,
      tx_hash TEXT,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS badges (
      id SERIAL PRIMARY KEY,
      name TEXT NOT NULL UNIQUE,
      emoji TEXT NOT NULL,
      description TEXT
    );

    CREATE TABLE IF NOT EXISTS user_badges (
      id SERIAL PRIMARY KEY,
      user_id UUID NOT NULL REFERENCES users(id),
      badge_id INTEGER NOT NULL REFERENCES badges(id),
      unlocked_at TIMESTAMPTZ DEFAULT NOW(),
      UNIQUE(user_id, badge_id)
    );

    CREATE TABLE IF NOT EXISTS personality_traits (
      id SERIAL PRIMARY KEY,
      user_id UUID NOT NULL REFERENCES users(id),
      label TEXT NOT NULL,
      value INTEGER NOT NULL DEFAULT 50,
      UNIQUE(user_id, label)
    );

    CREATE TABLE IF NOT EXISTS activity_feed (
      id SERIAL PRIMARY KEY,
      user_id UUID NOT NULL REFERENCES users(id),
      action TEXT NOT NULL,
      quest_title TEXT,
      grade TEXT,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );

    -- Migrations: add columns to existing tables
    ALTER TABLE users ADD COLUMN IF NOT EXISTS xp INTEGER DEFAULT 0;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS level INTEGER DEFAULT 1;
    ALTER TABLE user_friends ADD COLUMN IF NOT EXISTS friend_id UUID REFERENCES users(id);

    -- Quest step camera fields
    ALTER TABLE quest_steps ADD COLUMN IF NOT EXISTS camera_prompt TEXT;
    ALTER TABLE quest_steps ADD COLUMN IF NOT EXISTS success_condition TEXT;
    ALTER TABLE quest_steps ADD COLUMN IF NOT EXISTS player_action TEXT;
    ALTER TABLE quest_steps ADD COLUMN IF NOT EXISTS narrative_intro TEXT;

    -- Seed default badges if empty
    INSERT INTO badges (name, emoji, description) VALUES
      ('Shadow Agent', '🥷', 'Complete a quest in stealth mode'),
      ('Perfect Shot', '🎯', 'Get an A+ grade'),
      ('Mastermind', '🧠', 'Solve all puzzles in a quest'),
      ('Speed Runner', '⚡', 'Complete a quest under par time'),
      ('Untouchable', '🛡️', 'Complete a quest with zero fails'),
      ('Silver Tongue', '💬', 'Max trust with all characters'),
      ('Lockpicker', '🔓', 'Unlock a hidden path'),
      ('Globetrotter', '🌐', 'Complete quests in 3 different cities')
    ON CONFLICT (name) DO NOTHING;
  `);
}

export default pool;

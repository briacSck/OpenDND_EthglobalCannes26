#!/bin/bash
# Reset all data in the Railway PostgreSQL database (keeps tables, deletes all rows)

PGPASSWORD=VVITIjFrjZOkNZTXjJoKBLxSnxrzVnqs psql -h junction.proxy.rlwy.net -p 20463 -U postgres -d railway <<'SQL'
TRUNCATE
  quest_actions,
  quest_steps,
  quest_stakes,
  transactions,
  activity_feed,
  user_badges,
  personality_traits,
  user_friends,
  quests,
  users
CASCADE;

-- Re-seed badges
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

SELECT 'Done — all data cleared.' AS status;
SQL

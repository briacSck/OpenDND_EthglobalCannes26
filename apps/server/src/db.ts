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
      created_at TIMESTAMPTZ DEFAULT NOW(),
      updated_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS user_friends (
      id SERIAL PRIMARY KEY,
      user_id UUID NOT NULL REFERENCES users(id),
      phone TEXT NOT NULL,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );
  `);
}

export default pool;

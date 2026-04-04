import { Router } from "express";
import pool from "../db";

const router = Router();

// POST /api/users — create user from onboarding
router.post("/", async (req, res) => {
  const {
    firstName,
    email,
    generalGoal,
    questBudget,
    difficulty,
    frequency,
    poolAmount,
    groupMode,
    groupName,
    friends,
    walletAddress,
  } = req.body;

  if (!firstName) {
    res.status(400).json({ error: "firstName is required" });
    return;
  }

  const client = await pool.connect();
  try {
    await client.query("BEGIN");

    const { rows } = await client.query(
      `INSERT INTO users (first_name, email, general_goal, quest_budget, difficulty, frequency, pool_amount, group_mode, group_name, wallet_address)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
       RETURNING id, first_name, email`,
      [
        firstName,
        email || null,
        generalGoal || null,
        questBudget ?? 25,
        difficulty ?? 1,
        frequency ?? 1,
        poolAmount ?? 50,
        groupMode ?? 0,
        groupName || null,
        walletAddress || null,
      ]
    );

    const userId = rows[0].id;

    if (Array.isArray(friends)) {
      for (const phone of friends) {
        if (typeof phone === "string" && phone.trim()) {
          await client.query(
            "INSERT INTO user_friends (user_id, phone) VALUES ($1, $2)",
            [userId, phone.trim()]
          );
        }
      }
    }

    await client.query("COMMIT");
    res.status(201).json(rows[0]);
  } catch (err: any) {
    await client.query("ROLLBACK");
    if (err.code === "23505") {
      res.status(409).json({ error: "Email already registered" });
      return;
    }
    console.error("Failed to create user:", err);
    res.status(500).json({ error: "Failed to create user" });
  } finally {
    client.release();
  }
});

// GET /api/users/:id
router.get("/:id", async (req, res) => {
  try {
    const { rows: users } = await pool.query(
      "SELECT * FROM users WHERE id = $1",
      [req.params.id]
    );
    if (!users.length) {
      res.status(404).json({ error: "User not found" });
      return;
    }
    const { rows: friends } = await pool.query(
      "SELECT phone, friend_id FROM user_friends WHERE user_id = $1",
      [req.params.id]
    );
    res.json({ ...users[0], friends: friends.map((f) => f.phone) });
  } catch {
    res.status(500).json({ error: "Server error" });
  }
});

// GET /api/users?email=...
router.get("/", async (req, res) => {
  try {
    const { email } = req.query;
    if (email) {
      const { rows } = await pool.query(
        "SELECT * FROM users WHERE email = $1",
        [email]
      );
      if (!rows.length) {
        res.status(404).json({ error: "User not found" });
        return;
      }
      const { rows: friends } = await pool.query(
        "SELECT phone FROM user_friends WHERE user_id = $1",
        [rows[0].id]
      );
      res.json({ ...rows[0], friends: friends.map((f) => f.phone) });
      return;
    }
    const { rows } = await pool.query(
      "SELECT * FROM users ORDER BY created_at DESC"
    );
    res.json(rows);
  } catch {
    res.status(500).json({ error: "Server error" });
  }
});

// PATCH /api/users/:id — update user
router.patch("/:id", async (req, res) => {
  const { walletAddress, xp, level } = req.body;
  const updates: string[] = [];
  const values: any[] = [];
  let idx = 1;

  if (walletAddress !== undefined) {
    updates.push(`wallet_address = $${idx++}`);
    values.push(walletAddress);
  }
  if (xp !== undefined) {
    updates.push(`xp = $${idx++}`);
    values.push(xp);
  }
  if (level !== undefined) {
    updates.push(`level = $${idx++}`);
    values.push(level);
  }

  if (!updates.length) {
    res.status(400).json({ error: "No fields to update" });
    return;
  }

  updates.push(`updated_at = NOW()`);
  values.push(req.params.id);

  try {
    const { rows } = await pool.query(
      `UPDATE users SET ${updates.join(", ")} WHERE id = $${idx} RETURNING *`,
      values
    );
    if (!rows.length) {
      res.status(404).json({ error: "User not found" });
      return;
    }
    res.json(rows[0]);
  } catch (err) {
    console.error("Failed to update user:", err);
    res.status(500).json({ error: "Server error" });
  }
});

export default router;

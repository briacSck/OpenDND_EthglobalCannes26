import { Router } from "express";
import pool from "../db";

const router = Router();

// GET /api/social/leaderboard — top players by XP
router.get("/leaderboard", async (_req, res) => {
  try {
    const { rows } = await pool.query(
      `SELECT id, first_name, xp, level FROM users ORDER BY xp DESC LIMIT 50`
    );
    res.json(
      rows.map((u: any, i: number) => ({
        rank: i + 1,
        id: u.id,
        name: u.first_name,
        avatar: u.first_name.charAt(0).toUpperCase(),
        xp: u.xp || 0,
        level: u.level || 1,
      }))
    );
  } catch (err) {
    console.error("Failed to fetch leaderboard:", err);
    res.status(500).json({ error: "Server error" });
  }
});

// GET /api/social/activity/:userId — friend activity feed
router.get("/activity/:userId", async (req, res) => {
  try {
    // Get friend IDs
    const { rows: friendLinks } = await pool.query(
      `SELECT friend_id FROM user_friends WHERE user_id = $1 AND friend_id IS NOT NULL`,
      [req.params.userId]
    );
    const friendIds = friendLinks.map((f: any) => f.friend_id);

    if (!friendIds.length) {
      // Fallback: show all activity
      const { rows } = await pool.query(
        `SELECT af.id, af.action, af.quest_title, af.grade, af.created_at,
                u.first_name, u.id as user_id
         FROM activity_feed af JOIN users u ON af.user_id = u.id
         WHERE af.user_id != $1
         ORDER BY af.created_at DESC LIMIT 20`,
        [req.params.userId]
      );
      res.json(
        rows.map((a: any) => ({
          id: a.id,
          userId: a.user_id,
          name: a.first_name,
          avatar: a.first_name.charAt(0).toUpperCase(),
          action: formatAction(a.action, a.quest_title),
          grade: a.grade,
          time: a.created_at,
        }))
      );
      return;
    }

    const placeholders = friendIds.map((_: any, i: number) => `$${i + 1}`).join(",");
    const { rows } = await pool.query(
      `SELECT af.id, af.action, af.quest_title, af.grade, af.created_at,
              u.first_name, u.id as user_id
       FROM activity_feed af JOIN users u ON af.user_id = u.id
       WHERE af.user_id IN (${placeholders})
       ORDER BY af.created_at DESC LIMIT 20`,
      friendIds
    );

    res.json(
      rows.map((a: any) => ({
        id: a.id,
        userId: a.user_id,
        name: a.first_name,
        avatar: a.first_name.charAt(0).toUpperCase(),
        action: formatAction(a.action, a.quest_title),
        grade: a.grade,
        time: a.created_at,
      }))
    );
  } catch (err) {
    console.error("Failed to fetch activity:", err);
    res.status(500).json({ error: "Server error" });
  }
});

// GET /api/social/badges/:userId — user's badges
router.get("/badges/:userId", async (req, res) => {
  try {
    const { rows } = await pool.query(
      `SELECT b.id, b.name, b.emoji, b.description,
              CASE WHEN ub.id IS NOT NULL THEN true ELSE false END as unlocked,
              ub.unlocked_at
       FROM badges b
       LEFT JOIN user_badges ub ON ub.badge_id = b.id AND ub.user_id = $1
       ORDER BY b.id`,
      [req.params.userId]
    );
    res.json(rows);
  } catch (err) {
    console.error("Failed to fetch badges:", err);
    res.status(500).json({ error: "Server error" });
  }
});

// GET /api/social/personality/:userId — personality traits
router.get("/personality/:userId", async (req, res) => {
  try {
    const { rows } = await pool.query(
      `SELECT label, value FROM personality_traits WHERE user_id = $1 ORDER BY value DESC`,
      [req.params.userId]
    );
    res.json(rows);
  } catch (err) {
    console.error("Failed to fetch personality:", err);
    res.status(500).json({ error: "Server error" });
  }
});

// POST /api/social/badges/:userId — award a badge
router.post("/badges/:userId", async (req, res) => {
  const { badgeId } = req.body;
  try {
    await pool.query(
      `INSERT INTO user_badges (user_id, badge_id) VALUES ($1, $2) ON CONFLICT DO NOTHING`,
      [req.params.userId, badgeId]
    );

    // Add to activity feed
    const { rows: badge } = await pool.query(`SELECT name FROM badges WHERE id = $1`, [badgeId]);
    if (badge.length) {
      await pool.query(
        `INSERT INTO activity_feed (user_id, action, quest_title) VALUES ($1, 'badge', $2)`,
        [req.params.userId, badge[0].name]
      );
    }

    res.json({ ok: true });
  } catch (err) {
    console.error("Failed to award badge:", err);
    res.status(500).json({ error: "Server error" });
  }
});

function formatAction(action: string, questTitle: string | null): string {
  switch (action) {
    case "completed":
      return `completed ${questTitle || "a quest"}`;
    case "started":
      return `started ${questTitle || "a quest"}`;
    case "badge":
      return `unlocked ${questTitle || "a badge"} badge`;
    case "level_up":
      return `reached ${questTitle || "a new level"}`;
    default:
      return action;
  }
}

export default router;

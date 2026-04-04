import { Router } from "express";
import pool from "../db";

const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY || "";

const router = Router();

// POST /api/quests/generate — generate a quest via FastAPI backend and save to DB
router.post("/generate", async (req, res) => {
  req.setTimeout(30000);
  res.setTimeout(30000);

  const { userId, goal, location, duration, difficulty } = req.body;
  if (!userId) {
    res.status(400).json({ error: "userId required" });
    return;
  }

  const BACKEND_URL = process.env.BACKEND_URL || "https://backend-production-77f8.up.railway.app";

  try {
    const questLocation = location || "Cannes, France";
    const questDuration = duration || 60;
    const questDifficulty = difficulty || "medium";

    console.log(`[Generate] Calling FastAPI backend for ${questLocation}...`);

    const backendRes = await fetch(`${BACKEND_URL}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        location: questLocation,
        tone: "loufoque",
        skill: "exploration",
        budget: 50,
        duration: `${questDuration}m`,
        players: 1,
        goal: goal || "discover the city",
        datetime: new Date().toISOString().slice(0, 16).replace("T", " "),
      }),
    });

    if (!backendRes.ok) {
      const errText = await backendRes.text();
      console.error("[Generate] FastAPI error:", backendRes.status, errText);
      res.status(502).json({ error: "Quest generation failed", detail: errText });
      return;
    }

    const questOutput = await backendRes.json() as any;
    console.log(`[Generate] Got quest: ${questOutput.title} with ${questOutput.steps?.length || 0} steps`);

    // Save to DB
    const client = await pool.connect();
    try {
      await client.query("BEGIN");

      const description = questOutput.narrative_universe?.hook || questOutput.narrative_universe?.context || null;

      const { rows } = await client.query(
        `INSERT INTO quests (user_id, title, description, tone, time_limit_minutes)
         VALUES ($1, $2, $3, $4, $5) RETURNING *`,
        [userId, questOutput.title, description, questOutput.tone || null, questDuration]
      );
      const quest = rows[0];

      const steps = questOutput.steps || [];
      for (let i = 0; i < steps.length; i++) {
        const s = steps[i];
        const activity = s.activity || {};
        await client.query(
          `INSERT INTO quest_steps (quest_id, step_order, type, title, subtitle, icon, active, content, camera_prompt, success_condition, player_action, narrative_intro)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)`,
          [
            quest.id, i + 1,
            s.is_skill_step ? "skill" : (s.is_collaborative ? "collaborative" : "action"),
            s.title,
            activity.name ? `${activity.name} — ${activity.address || ""}` : null,
            "star",
            i === 0,
            s.instruction || s.narrative_intro || null,
            s.camera_prompt || null,
            s.verification?.success_condition || null,
            s.player_action || null,
            s.narrative_intro || null,
          ]
        );
      }

      await client.query("COMMIT");

      const { rows: savedSteps } = await pool.query(
        `SELECT id, step_order, type, title, subtitle, icon, done, active, content, camera_prompt, success_condition, player_action, narrative_intro
         FROM quest_steps WHERE quest_id = $1 ORDER BY step_order`,
        [quest.id]
      );

      res.status(201).json({
        ...quest,
        steps: savedSteps,
        actions: [],
        completedSteps: 0,
        totalSteps: savedSteps.length,
        progress: 0,
      });
    } catch (err) {
      await client.query("ROLLBACK");
      throw err;
    } finally {
      client.release();
    }
  } catch (err) {
    console.error("Failed to generate quest:", err);
    const message = err instanceof Error ? err.message : String(err);
    res.status(500).json({ error: "Quest generation failed", detail: message });
  }
});

// GET /api/quests/active/:userId — get active quest with steps & actions
router.get("/active/:userId", async (req, res) => {
  try {
    const { rows: quests } = await pool.query(
      `SELECT * FROM quests WHERE user_id = $1 AND status = 'active' ORDER BY started_at DESC LIMIT 1`,
      [req.params.userId]
    );
    if (!quests.length) {
      res.json(null);
      return;
    }
    const quest = quests[0];

    const { rows: steps } = await pool.query(
      `SELECT id, step_order, type, title, subtitle, icon, done, active, content, camera_prompt, success_condition, player_action, narrative_intro
       FROM quest_steps WHERE quest_id = $1 ORDER BY step_order`,
      [quest.id]
    );

    const { rows: actions } = await pool.query(
      `SELECT id, action, xp, created_at FROM quest_actions
       WHERE quest_id = $1 ORDER BY created_at DESC LIMIT 20`,
      [quest.id]
    );

    const completedSteps = steps.filter((s: any) => s.done).length;

    res.json({
      ...quest,
      steps,
      actions,
      completedSteps,
      totalSteps: steps.length,
      progress: steps.length > 0 ? completedSteps / steps.length : 0,
    });
  } catch (err) {
    console.error("Failed to fetch active quest:", err);
    res.status(500).json({ error: "Server error" });
  }
});

// GET /api/quests/history/:userId — completed quests
router.get("/history/:userId", async (req, res) => {
  try {
    const { rows } = await pool.query(
      `SELECT id, title, grade, xp_earned, reward_amount, duration_minutes, completed_at
       FROM quests WHERE user_id = $1 AND status = 'completed'
       ORDER BY completed_at DESC`,
      [req.params.userId]
    );
    res.json(rows);
  } catch (err) {
    console.error("Failed to fetch quest history:", err);
    res.status(500).json({ error: "Server error" });
  }
});

// POST /api/quests — create a new quest
router.post("/", async (req, res) => {
  const { userId, title, description, tone, timeLimitMinutes, steps } = req.body;
  if (!userId || !title) {
    res.status(400).json({ error: "userId and title required" });
    return;
  }

  const client = await pool.connect();
  try {
    await client.query("BEGIN");

    const { rows } = await client.query(
      `INSERT INTO quests (user_id, title, description, tone, time_limit_minutes)
       VALUES ($1, $2, $3, $4, $5) RETURNING *`,
      [userId, title, description || null, tone || null, timeLimitMinutes || null]
    );
    const quest = rows[0];

    if (Array.isArray(steps)) {
      for (let i = 0; i < steps.length; i++) {
        const s = steps[i];
        await client.query(
          `INSERT INTO quest_steps (quest_id, step_order, type, title, subtitle, icon, active, content)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
          [quest.id, i + 1, s.type || "action", s.title, s.subtitle || null, s.icon || "star", i === 0, s.content || null]
        );
      }
    }

    await client.query("COMMIT");
    res.status(201).json(quest);
  } catch (err) {
    await client.query("ROLLBACK");
    console.error("Failed to create quest:", err);
    res.status(500).json({ error: "Failed to create quest" });
  } finally {
    client.release();
  }
});

// POST /api/quests/:questId/complete — mark quest as completed
router.post("/:questId/complete", async (req, res) => {
  const { grade, xpEarned, rewardAmount, durationMinutes } = req.body;
  try {
    const { rows } = await pool.query(
      `UPDATE quests SET status = 'completed', grade = $2, xp_earned = $3,
       reward_amount = $4, duration_minutes = $5, completed_at = NOW()
       WHERE id = $1 RETURNING *`,
      [req.params.questId, grade || null, xpEarned || 0, rewardAmount || 0, durationMinutes || null]
    );
    if (!rows.length) {
      res.status(404).json({ error: "Quest not found" });
      return;
    }

    // Update user XP
    if (xpEarned) {
      await pool.query(
        `UPDATE users SET xp = xp + $1, updated_at = NOW() WHERE id = $2`,
        [xpEarned, rows[0].user_id]
      );
    }

    // Create reward transaction
    if (rewardAmount) {
      await pool.query(
        `INSERT INTO transactions (user_id, type, label, amount) VALUES ($1, 'credit', $2, $3)`,
        [rows[0].user_id, rows[0].title, rewardAmount]
      );
    }

    // Add to activity feed
    await pool.query(
      `INSERT INTO activity_feed (user_id, action, quest_title, grade) VALUES ($1, $2, $3, $4)`,
      [rows[0].user_id, "completed", rows[0].title, grade]
    );

    res.json(rows[0]);
  } catch (err) {
    console.error("Failed to complete quest:", err);
    res.status(500).json({ error: "Server error" });
  }
});

// POST /api/quests/:questId/steps/:stepOrder/done — mark step as done
router.post("/:questId/steps/:stepOrder/done", async (req, res) => {
  try {
    // Mark current step done
    await pool.query(
      `UPDATE quest_steps SET done = true, active = false WHERE quest_id = $1 AND step_order = $2`,
      [req.params.questId, req.params.stepOrder]
    );
    // Activate next step
    const nextOrder = parseInt(req.params.stepOrder) + 1;
    await pool.query(
      `UPDATE quest_steps SET active = true WHERE quest_id = $1 AND step_order = $2`,
      [req.params.questId, nextOrder]
    );
    res.json({ ok: true });
  } catch (err) {
    console.error("Failed to update step:", err);
    res.status(500).json({ error: "Server error" });
  }
});

// POST /api/quests/:questId/steps/:stepOrder/verify — verify step with camera (Claude Vision)
router.post("/:questId/steps/:stepOrder/verify", async (req, res) => {
  const { imageBase64, cameraPrompt, successCondition, playerAction, stepTitle } = req.body;
  if (!imageBase64) {
    res.status(400).json({ error: "imageBase64 required" });
    return;
  }

  const BACKEND_URL = process.env.BACKEND_URL || "https://backend-production-77f8.up.railway.app";

  try {
    console.log(`[Verify] Step ${req.params.stepOrder} of quest ${req.params.questId} — sending to Vision...`);

    const verifyRes = await fetch(`${BACKEND_URL}/verify-step`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image_base64: imageBase64,
        quest_id: req.params.questId,
        step_id: parseInt(req.params.stepOrder),
        camera_prompt: cameraPrompt || "",
        success_condition: successCondition || "",
        player_action: playerAction || "",
        step_title: stepTitle || "",
      }),
    });

    if (!verifyRes.ok) {
      const errText = await verifyRes.text();
      console.error("[Verify] Backend error:", verifyRes.status, errText);
      res.status(502).json({ error: "Verification failed", detail: errText });
      return;
    }

    const result = await verifyRes.json() as any;
    console.log(`[Verify] Result: validated=${result.validated}, confidence=${result.confidence}`);

    // If validated, mark step as done and activate next
    if (result.validated) {
      await pool.query(
        `UPDATE quest_steps SET done = true, active = false WHERE quest_id = $1 AND step_order = $2`,
        [req.params.questId, req.params.stepOrder]
      );
      const nextOrder = parseInt(req.params.stepOrder) + 1;
      await pool.query(
        `UPDATE quest_steps SET active = true WHERE quest_id = $1 AND step_order = $2`,
        [req.params.questId, nextOrder]
      );

      // Log action
      const { userId } = req.body;
      if (userId) {
        await pool.query(
          `INSERT INTO quest_actions (quest_id, user_id, action, xp) VALUES ($1, $2, $3, $4)`,
          [req.params.questId, userId, `Step ${req.params.stepOrder} verified via camera`, result.xp_earned || 15]
        );
      }
    }

    res.json(result);
  } catch (err) {
    console.error("Failed to verify step:", err);
    const message = err instanceof Error ? err.message : String(err);
    res.status(500).json({ error: "Verification failed", detail: message });
  }
});

// POST /api/quests/:questId/actions — log an action
router.post("/:questId/actions", async (req, res) => {
  const { userId, action, xp } = req.body;
  try {
    const { rows } = await pool.query(
      `INSERT INTO quest_actions (quest_id, user_id, action, xp) VALUES ($1, $2, $3, $4) RETURNING *`,
      [req.params.questId, userId, action, xp || 0]
    );
    res.status(201).json(rows[0]);
  } catch (err) {
    console.error("Failed to log action:", err);
    res.status(500).json({ error: "Server error" });
  }
});

export default router;

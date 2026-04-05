import { Router } from "express";
import pool from "../db";

const router = Router();

const BACKEND_URL = process.env.BACKEND_URL || "https://backend-production-77f8.up.railway.app";

// POST /api/blockchain/stake — stake HBAR for a quest
router.post("/stake", async (req, res) => {
  const { questId, userId, amount } = req.body;
  if (!questId || !userId || !amount) {
    res.status(400).json({ error: "questId, userId, amount required" });
    return;
  }

  try {
    // Get user's wallet address + hedera account
    const { rows: users } = await pool.query(
      `SELECT wallet_address, hedera_account_id FROM users WHERE id = $1`,
      [userId]
    );
    if (!users.length || !users[0].wallet_address) {
      res.status(400).json({ error: "User has no wallet address" });
      return;
    }

    // Record stake in DB
    await pool.query(
      `INSERT INTO quest_stakes (quest_id, user_id, amount, status)
       VALUES ($1, $2, $3, 'locked')`,
      [questId, userId, amount]
    );

    // Update user's locked balance
    await pool.query(
      `UPDATE users SET pool_amount = COALESCE(pool_amount, 0) + $1 WHERE id = $2`,
      [amount, userId]
    );

    // Record as a debit transaction
    await pool.query(
      `INSERT INTO transactions (user_id, type, label, amount) VALUES ($1, 'debit', $2, $3)`,
      [userId, `Quest stake locked`, amount]
    );

    // Ensure user has a Hedera account
    try {
      if (!users[0].hedera_account_id) {
        const accRes = await fetch(`${BACKEND_URL}/blockchain/create-account`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ evm_address: users[0].wallet_address }),
        });
        if (accRes.ok) {
          const accData = await accRes.json() as any;
          await pool.query(`UPDATE users SET hedera_account_id = $1 WHERE id = $2`, [accData.hedera_account_id, userId]);
          console.log(`[Blockchain] Created Hedera account ${accData.hedera_account_id} for ${users[0].wallet_address}`);
        }
      }
    } catch (accErr) {
      console.warn(`[Blockchain] Account creation failed:`, accErr);
    }

    // Call FastAPI blockchain endpoint
    let chainResult: any = null;
    try {
      const backendRes = await fetch(`${BACKEND_URL}/blockchain/stake`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          quest_id: questId,
          player_account_id: users[0].wallet_address,
          amount: Math.round(amount), // HBAR amount (1:1 with dollar for testnet)
          stake_tx_hash: `stake-${questId}-${Date.now()}`,
        }),
      });

      if (backendRes.ok) {
        chainResult = await backendRes.json();
        console.log(`[Blockchain] Stake recorded on-chain:`, chainResult);
      } else {
        const errText = await backendRes.text();
        console.warn(`[Blockchain] On-chain stake failed:`, errText);
      }
    } catch (chainErr) {
      console.warn(`[Blockchain] On-chain stake call failed:`, chainErr);
    }

    res.status(201).json({ ok: true, questId, amount, status: "locked", chain: chainResult });
  } catch (err) {
    console.error("Failed to stake:", err);
    res.status(500).json({ error: "Staking failed" });
  }
});

// POST /api/blockchain/resolve — resolve quest stake (win/lose)
router.post("/resolve", async (req, res) => {
  const { questId, outcome } = req.body;
  if (!questId || !outcome) {
    res.status(400).json({ error: "questId, outcome required" });
    return;
  }

  try {
    // Get all stakes for this quest
    const { rows: stakes } = await pool.query(
      `SELECT * FROM quest_stakes WHERE quest_id = $1 AND status = 'locked'`,
      [questId]
    );

    if (!stakes.length) {
      res.status(404).json({ error: "No locked stakes for this quest" });
      return;
    }

    const results = [];

    for (const stake of stakes) {
      if (outcome === "win") {
        // Calculate bonus: 50% of total lost stakes pool
        const { rows: lostPool } = await pool.query(
          `SELECT COALESCE(SUM(amount), 0) as pool FROM quest_stakes WHERE status = 'lost'`
        );
        const { rows: paidBonuses } = await pool.query(
          `SELECT COALESCE(SUM(bonus), 0) as paid FROM quest_stakes WHERE status = 'won'`
        );
        const availablePool = (lostPool[0]?.pool || 0) - (paidBonuses[0]?.paid || 0);
        const bonus = Math.max(0, availablePool * 0.5);
        const payout = stake.amount + bonus;

        // Update stake record
        await pool.query(
          `UPDATE quest_stakes SET status = 'won', bonus = $1, resolved_at = NOW() WHERE id = $2`,
          [bonus, stake.id]
        );

        // Unlock from user's pool
        await pool.query(
          `UPDATE users SET pool_amount = GREATEST(COALESCE(pool_amount, 0) - $1, 0) WHERE id = $2`,
          [stake.amount, stake.user_id]
        );

        // Credit the payout
        await pool.query(
          `INSERT INTO transactions (user_id, type, label, amount) VALUES ($1, 'credit', $2, $3)`,
          [stake.user_id, `Quest reward (${bonus > 0 ? "stake + bonus" : "stake refund"})`, payout]
        );

        results.push({ userId: stake.user_id, payout, bonus, status: "won" });

      } else {
        // Lose: burn the stake
        await pool.query(
          `UPDATE quest_stakes SET status = 'lost', resolved_at = NOW() WHERE id = $1`,
          [stake.id]
        );

        // Remove from locked
        await pool.query(
          `UPDATE users SET pool_amount = GREATEST(COALESCE(pool_amount, 0) - $1, 0) WHERE id = $2`,
          [stake.amount, stake.user_id]
        );

        results.push({ userId: stake.user_id, payout: 0, bonus: 0, status: "lost" });
      }
    }

    // Call FastAPI blockchain endpoint
    try {
      await fetch(`${BACKEND_URL}/blockchain/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ quest_id: questId, outcome }),
      });
    } catch (chainErr) {
      console.warn(`[Blockchain] On-chain resolve failed (continuing with DB):`, chainErr);
    }

    res.json({ ok: true, questId, outcome, results });
  } catch (err) {
    console.error("Failed to resolve:", err);
    res.status(500).json({ error: "Resolution failed" });
  }
});

// POST /api/blockchain/bet — friend bets on a quest
router.post("/bet", async (req, res) => {
  const { questId, userId, amount, prediction } = req.body;
  if (!questId || !userId || !amount) {
    res.status(400).json({ error: "questId, userId, amount required" });
    return;
  }

  try {
    await pool.query(
      `INSERT INTO quest_stakes (quest_id, user_id, amount, status, is_bet, prediction)
       VALUES ($1, $2, $3, 'locked', true, $4)`,
      [questId, userId, amount, prediction || "win"]
    );

    // Debit the bettor
    await pool.query(
      `INSERT INTO transactions (user_id, type, label, amount) VALUES ($1, 'debit', $2, $3)`,
      [userId, `Bet on quest`, amount]
    );

    // Update locked balance
    await pool.query(
      `UPDATE users SET pool_amount = COALESCE(pool_amount, 0) + $1 WHERE id = $2`,
      [amount, userId]
    );

    res.status(201).json({ ok: true, questId, userId, amount, prediction: prediction || "win" });
  } catch (err) {
    console.error("Failed to place bet:", err);
    res.status(500).json({ error: "Bet failed" });
  }
});

// GET /api/blockchain/stake/:questId — get stake info for a quest
router.get("/stake/:questId", async (req, res) => {
  try {
    const { rows } = await pool.query(
      `SELECT qs.*, u.first_name FROM quest_stakes qs
       JOIN users u ON u.id = qs.user_id
       WHERE qs.quest_id = $1
       ORDER BY qs.created_at`,
      [req.params.questId]
    );

    const totalStaked = rows.reduce((sum: number, s: any) => sum + (s.amount || 0), 0);
    const bets = rows.filter((s: any) => s.is_bet);
    const playerStake = rows.find((s: any) => !s.is_bet);

    res.json({
      questId: req.params.questId,
      totalStaked,
      playerStake: playerStake ? { amount: playerStake.amount, status: playerStake.status } : null,
      bets: bets.map((b: any) => ({
        userId: b.user_id,
        name: b.first_name,
        amount: b.amount,
        prediction: b.prediction,
        status: b.status,
      })),
    });
  } catch (err) {
    console.error("Failed to get stake:", err);
    res.status(500).json({ error: "Server error" });
  }
});

export default router;

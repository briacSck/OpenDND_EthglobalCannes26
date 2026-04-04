import { Router } from "express";
import pool from "../db";

const router = Router();

// GET /api/wallet/:userId — balance + transactions
router.get("/:userId", async (req, res) => {
  try {
    const { rows: users } = await pool.query(
      `SELECT id, wallet_address, pool_amount FROM users WHERE id = $1`,
      [req.params.userId]
    );
    if (!users.length) {
      res.status(404).json({ error: "User not found" });
      return;
    }

    const { rows: transactions } = await pool.query(
      `SELECT id, type, label, amount, tx_hash, created_at
       FROM transactions WHERE user_id = $1 ORDER BY created_at DESC LIMIT 50`,
      [req.params.userId]
    );

    // Compute balances from transactions
    let totalCredits = 0;
    let totalDebits = 0;
    for (const tx of transactions) {
      if (tx.type === "credit") totalCredits += tx.amount;
      else totalDebits += Math.abs(tx.amount);
    }

    const available = totalCredits - totalDebits;

    // Pending = credits from last 2 hours
    const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString();
    const { rows: pendingRows } = await pool.query(
      `SELECT COALESCE(SUM(amount), 0) as pending FROM transactions
       WHERE user_id = $1 AND type = 'credit' AND created_at > $2`,
      [req.params.userId, twoHoursAgo]
    );

    res.json({
      walletAddress: users[0].wallet_address,
      available: Math.round(available * 100) / 100,
      locked: users[0].pool_amount || 0,
      pending: Math.round((pendingRows[0]?.pending || 0) * 100) / 100,
      transactions: transactions.map((tx: any) => ({
        id: tx.id,
        type: tx.type,
        label: tx.label,
        amount: tx.amount,
        date: tx.created_at,
      })),
    });
  } catch (err) {
    console.error("Failed to fetch wallet:", err);
    res.status(500).json({ error: "Server error" });
  }
});

// POST /api/wallet/:userId/transaction — add a transaction
router.post("/:userId/transaction", async (req, res) => {
  const { type, label, amount, txHash } = req.body;
  if (!type || !label || amount === undefined) {
    res.status(400).json({ error: "type, label, amount required" });
    return;
  }
  try {
    const { rows } = await pool.query(
      `INSERT INTO transactions (user_id, type, label, amount, tx_hash)
       VALUES ($1, $2, $3, $4, $5) RETURNING *`,
      [req.params.userId, type, label, amount, txHash || null]
    );
    res.status(201).json(rows[0]);
  } catch (err) {
    console.error("Failed to add transaction:", err);
    res.status(500).json({ error: "Server error" });
  }
});

export default router;

import express from "express";
import cors from "cors";
import { initDb } from "./db";
import usersRouter from "./routes/users";
import questsRouter from "./routes/quests";
import walletRouter from "./routes/wallet";
import socialRouter from "./routes/social";
import blockchainRouter from "./routes/blockchain";

const app = express();
const PORT = process.env.PORT || 3002;

app.use(cors());
app.use(express.json({ limit: "20mb" }));

app.get("/health", (_req, res) => {
  res.json({ status: "ok", timestamp: new Date().toISOString() });
});

app.use("/api/users", usersRouter);
app.use("/api/quests", questsRouter);
app.use("/api/wallet", walletRouter);
app.use("/api/social", socialRouter);
app.use("/api/blockchain", blockchainRouter);

async function start() {
  await initDb();
  console.log("Database tables ready");

  const server = app.listen(Number(PORT), "0.0.0.0", () => {
    console.log(`Server running on http://0.0.0.0:${PORT}`);
  });
  // Allow long-running requests (quest generation takes 2-3 min)
  server.timeout = 300000;
  server.keepAliveTimeout = 300000;
  server.headersTimeout = 310000;
}

start().catch((err) => {
  console.error("Failed to start server:", err);
  process.exit(1);
});

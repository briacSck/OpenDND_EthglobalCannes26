import express from "express";
import cors from "cors";
import { initDb } from "./db";
import usersRouter from "./routes/users";
import questsRouter from "./routes/quests";
import walletRouter from "./routes/wallet";
import socialRouter from "./routes/social";

const app = express();
const PORT = process.env.PORT || 3002;

app.use(cors());
app.use(express.json());

app.get("/health", (_req, res) => {
  res.json({ status: "ok", timestamp: new Date().toISOString() });
});

app.use("/api/users", usersRouter);
app.use("/api/quests", questsRouter);
app.use("/api/wallet", walletRouter);
app.use("/api/social", socialRouter);

async function start() {
  await initDb();
  console.log("Database tables ready");

  app.listen(Number(PORT), "0.0.0.0", () => {
    console.log(`Server running on http://0.0.0.0:${PORT}`);
  });
}

start().catch((err) => {
  console.error("Failed to start server:", err);
  process.exit(1);
});

import express from "express";
import { initDb } from "./db";
import usersRouter from "./routes/users";

const app = express();
const PORT = process.env.PORT || 3002;

app.use(express.json());

app.get("/health", (_req, res) => {
  res.json({ status: "ok", timestamp: new Date().toISOString() });
});

app.use("/api/users", usersRouter);

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

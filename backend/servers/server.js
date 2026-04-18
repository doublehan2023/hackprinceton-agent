import express from "express";
import cors from "cors";
import chatRoute from "./routes/chat.js";

const app = express();

app.use(cors());
app.use(express.json());

app.use("/api/chat", chatRoute);

app.listen(5000, () => {
  console.log("Backend running on port 5000");
});
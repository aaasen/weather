import { serve } from "@hono/node-server";
import { serveStatic } from "@hono/node-server/serve-static";
import { Hono } from "hono";
import { health, inbound, testPage } from "./routes.js";

const app = new Hono();

app.get("/health", health);
app.post("/inbound", inbound);
app.get("/test", testPage);
app.post("/test", testPage);
app.use("/*", serveStatic({ root: process.env["CLIENT_DIR"] ?? "./packages/client/dist" }));

const port = parseInt(process.env["PORT"] ?? "8080");
serve({ fetch: app.fetch, port }, () => {
  console.log(`Server listening on :${port}`);
});

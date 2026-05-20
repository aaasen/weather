import type { Context } from "hono";
import { fetchForecast, parseRequest } from "./forecast.js";
import { sendGarminReply } from "./garmin.js";

const REPLY_ADDRESS = "wx@email.laneaasen.com";

export async function inbound(c: Context) {
  const form = await c.req.parseBody();
  const text = String(form["text"] ?? "");
  const sender = String(form["from"] ?? "");
  const match = text.match(/https:\/\/inreachlink\.com\/\S+/);
  const replyUrl = match?.[0] ?? null;

  console.log("=== Inbound Email ===");
  console.log("from:", sender);
  console.log("subject:", form["subject"]);
  console.log("text:", text);
  console.log("reply_url:", replyUrl);

  if (replyUrl) {
    const body = text.replace(replyUrl, "").trim();
    const params = parseRequest(body);
    console.log("forecast request params:", params);

    let encoded: string;
    try {
      encoded = await fetchForecast(params);
      console.log(`forecast fetched (len=${encoded.length}): ${encoded}`);
    } catch (e) {
      console.error("fetchForecast failed:", e);
      return c.text("OK", 200);
    }

    try {
      const success = await sendGarminReply(replyUrl, REPLY_ADDRESS, encoded);
      console.log("garmin reply sent:", success);
    } catch (e) {
      console.error("sendGarminReply failed:", e);
    }
  }

  return c.text("OK", 200);
}

export function health(c: Context) {
  return c.text("OK", 200);
}

const TEST_HTML = (opts: {
  replyUrl: string;
  replyAddress: string;
  message: string;
  result: string;
}) => `<!doctype html>
<html>
<head><meta charset=utf-8><title>Garmin Reply Test</title>
<style>
  body { font-family: sans-serif; max-width: 600px; margin: 40px auto; padding: 0 16px; }
  label { display: block; margin-top: 16px; font-weight: bold; }
  input, textarea { width: 100%; box-sizing: border-box; padding: 6px; margin-top: 4px; font-family: monospace; }
  textarea { height: 80px; }
  button { margin-top: 16px; padding: 8px 20px; font-size: 1em; cursor: pointer; }
  pre { background: #f4f4f4; padding: 12px; white-space: pre-wrap; word-break: break-all; }
  .ok { color: green; } .err { color: red; }
</style>
</head>
<body>
<h2>Garmin Reply Test</h2>
<form method=post>
  <label>Reply URL (inreachlink.com/…)</label>
  <input name=reply_url value="${opts.replyUrl}" required>
  <label>Reply address</label>
  <input name=reply_address value="${opts.replyAddress}">
  <label>Message</label>
  <textarea name=message>${opts.message}</textarea>
  <button type=submit>Send</button>
</form>
${opts.result}
</body></html>`;

export async function testPage(c: Context) {
  let replyUrl = "";
  let replyAddress = "wx@email.laneaasen.com";
  let message = "";
  let resultHtml = "";

  if (c.req.method === "POST") {
    const form = await c.req.parseBody();
    replyUrl = String(form["reply_url"] ?? "").trim();
    replyAddress = String(form["reply_address"] ?? replyAddress).trim();
    message = String(form["message"] ?? "").trim();
    try {
      const success = await sendGarminReply(replyUrl, replyAddress, message);
      resultHtml = success
        ? `<p class=ok><b>Success</b></p>`
        : `<p class=err><b>Failed</b></p>`;
    } catch (e) {
      resultHtml = `<pre class=err>${e}</pre>`;
    }
  }

  return c.html(TEST_HTML({ replyUrl, replyAddress, message, result: resultHtml }));
}

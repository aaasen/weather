import logging
import os
import re

import requests
from flask import Flask, request, send_from_directory, Response

from forecast import fetch_forecast, parse_keyword

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DECODER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "decoder")

app = Flask(__name__)


# ── Decoder (static PWA) ──────────────────────────────────────────────────────


@app.route("/")
def index():
    return send_from_directory(DECODER_DIR, "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(DECODER_DIR, filename)


# ── Garmin inReach webhook ────────────────────────────────────────────────────


@app.route("/inbound", methods=["POST"])
def inbound():
    form = request.form
    text = form.get("text", "")
    sender = form.get("from", "")
    match = re.search(r"https://inreachlink\.com/\S+", text)
    reply_url = match.group(0) if match else None

    logger.info("=== Inbound Email ===")
    logger.info("from: %s", sender)
    logger.info("subject: %s", form.get("subject"))
    logger.info("text: %s", text)
    logger.info("reply_url: %s", reply_url)

    if reply_url:
        body = text.replace(reply_url, "").strip()
        keyword = parse_keyword(body)
        logger.info("forecast type keyword: %r", keyword)
        try:
            encoded = fetch_forecast(keyword)
            success = send_garmin_reply(reply_url, sender, encoded)
            logger.info(
                "forecast reply sent (keyword=%r, len=%d): %s",
                keyword,
                len(encoded),
                success,
            )
        except Exception as exc:
            logger.error("fetch_forecast failed: %s", exc)

    return "OK", 200


@app.route("/health", methods=["GET"])
def health():
    return "OK", 200


# ── Test page ─────────────────────────────────────────────────────────────────

_TEST_PAGE = """<!doctype html>
<html>
<head><meta charset=utf-8><title>Garmin Reply Test</title>
<style>
  body {{ font-family: sans-serif; max-width: 600px; margin: 40px auto; padding: 0 16px; }}
  label {{ display: block; margin-top: 16px; font-weight: bold; }}
  input, textarea {{ width: 100%; box-sizing: border-box; padding: 6px; margin-top: 4px; font-family: monospace; }}
  textarea {{ height: 80px; }}
  button {{ margin-top: 16px; padding: 8px 20px; font-size: 1em; cursor: pointer; }}
  pre {{ background: #f4f4f4; padding: 12px; white-space: pre-wrap; word-break: break-all; }}
  .ok {{ color: green; }} .err {{ color: red; }}
</style>
</head>
<body>
<h2>Garmin Reply Test</h2>
<form method=post>
  <label>Reply URL (inreachlink.com/…)</label>
  <input name=reply_url value="{reply_url}" required>
  <label>Reply address</label>
  <input name=reply_address value="{reply_address}">
  <label>Message</label>
  <textarea name=message>{message}</textarea>
  <button type=submit>Send</button>
</form>
{result}
</body></html>"""


@app.route("/test", methods=["GET", "POST"])
def test_page():
    reply_url = ""
    reply_address = "wx@email.laneaasen.com"
    message = ""
    result_html = ""

    if request.method == "POST":
        reply_url = request.form.get("reply_url", "").strip()
        reply_address = request.form.get("reply_address", "").strip()
        message = request.form.get("message", "").strip()
        try:
            success = send_garmin_reply(reply_url, reply_address, message)
            cls = "ok" if success else "err"
            label = "Success" if success else "Failed"
            result_html = f'<p class={cls}><b>{label}</b></p>'
        except Exception as exc:
            result_html = f'<pre class=err>{exc}</pre>'

    html = _TEST_PAGE.format(
        reply_url=reply_url,
        reply_address=reply_address,
        message=message,
        result=result_html,
    )
    return Response(html, mimetype="text/html")


# ── Garmin reply ──────────────────────────────────────────────────────────────


_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/148.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "DNT": "1",
}


def send_garmin_reply(reply_url: str, reply_address: str, message: str) -> bool:
    session = requests.Session()
    session.headers.update(_BROWSER_HEADERS)

    logger.info("garmin: fetching reply page %s", reply_url)
    page = session.get(reply_url)
    logger.info("garmin: page status=%d final_url=%s", page.status_code, page.url)

    guid_match = re.search(r'id="Guid"[^>]+value="([^"]+)"', page.text)
    msg_id_match = re.search(r'id="MessageId"[^>]+value="([^"]+)"', page.text)

    if not guid_match:
        logger.error("garmin: Guid not found in page (len=%d)", len(page.text))
        logger.debug("garmin: page body: %s", page.text[:2000])
        return False
    if not msg_id_match:
        logger.error("garmin: MessageId not found in page")
        logger.debug("garmin: page body: %s", page.text[:2000])
        return False

    guid = guid_match.group(1)
    message_id = msg_id_match.group(1)
    logger.info("garmin: guid=%s message_id=%s", guid, message_id)

    base_url = page.url.split("/textmessage")[0]
    api_url = f"{base_url}/TextMessage/TxtMsg"
    logger.info("garmin: posting to %s (message len=%d)", api_url, len(message))

    response = session.post(
        api_url,
        json={
            "ReplyAddress": reply_address,
            "ReplyMessage": message,
            "Guid": guid,
            "MessageId": message_id,
        },
        headers={
            "X-Requested-With": "XMLHttpRequest",
            "Origin": base_url,
            "Referer": page.url,
        },
    )

    logger.info("garmin: post status=%d body=%s", response.status_code, response.text[:500])

    try:
        result = response.json()
    except Exception:
        logger.error("garmin: response is not JSON: %s", response.text[:500])
        return False

    success = result.get("Success", False)
    if not success:
        logger.error("garmin: Success=False, full response: %s", result)
    return success

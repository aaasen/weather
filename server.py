import logging
import os
import re

import requests
from flask import Flask, request, send_from_directory

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


# ── Garmin reply ──────────────────────────────────────────────────────────────


def send_garmin_reply(reply_url: str, reply_address: str, message: str) -> bool:
    session = requests.Session()

    page = session.get(reply_url)

    guid = re.search(r'id="Guid"[^>]+value="([^"]+)"', page.text).group(1)
    message_id = re.search(r'id="MessageId"[^>]+value="([^"]+)"', page.text).group(1)

    base_url = page.url.split("/textmessage")[0]
    api_url = f"{base_url}/TextMessage/TxtMsg"

    response = session.post(
        api_url,
        json={
            "ReplyAddress": reply_address,
            "ReplyMessage": message,
            "Guid": guid,
            "MessageId": message_id,
        },
        headers={"X-Requested-With": "XMLHttpRequest"},
    )

    result = response.json()
    return result.get("Success", False)

import logging
import re

import requests
from flask import Flask, request

from forecast import fetch_forecast, parse_keyword

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)


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
    logger.info("full form dict: %s", dict(form))

    if reply_url:
        body    = text.replace(reply_url, "").strip()
        keyword = parse_keyword(body)
        logger.info("forecast type keyword: %r", keyword)
        try:
            encoded = fetch_forecast(keyword)
            success = send_garmin_reply(reply_url, sender, encoded)
            logger.info("forecast reply sent (keyword=%r, len=%d): %s",
                        keyword, len(encoded), success)
        except Exception as exc:
            logger.error("fetch_forecast failed: %s", exc)

    return "OK", 200


@app.route("/health", methods=["GET"])
def health():
    return "OK", 200


def send_garmin_reply(reply_url: str, reply_address: str, message: str) -> bool:
    """
    reply_url: the inreachlink.com URL from the Garmin email
    reply_address: your email (shown as sender to the device)
    message: the forecast text, max 160 chars
    """
    session = requests.Session()

    # Follow redirect from inreachlink.com -> us0.explore.garmin.com
    page = session.get(reply_url)

    # Extract Guid and MessageId from hidden inputs in the HTML
    guid = re.search(r'id="Guid"[^>]+value="([^"]+)"', page.text).group(1)
    message_id = re.search(r'id="MessageId"[^>]+value="([^"]+)"', page.text).group(1)

    # POST to the resolved base URL (us0.explore.garmin.com)
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


if __name__ == "__main__":
    success = send_garmin_reply(
        reply_url="https://inreachlink.com/g3ER8EmX53PBrwwj2SN40kg",
        reply_address="wx@email.laneaasen.com",
        message="test program",
    )
    print("Success:", success)

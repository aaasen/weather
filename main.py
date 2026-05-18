import logging
import re
from flask import Flask, request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/inbound", methods=["POST"])
def inbound():
    form = request.form
    text = form.get("text", "")
    match = re.search(r"https://inreachlink\.com/\S+", text)
    reply_url = match.group(0) if match else None

    logger.info("=== Inbound Email ===")
    logger.info("from: %s", form.get("from"))
    logger.info("subject: %s", form.get("subject"))
    logger.info("text: %s", text)
    logger.info("reply_url: %s", reply_url)
    logger.info("full form dict: %s", dict(form))
    return "OK", 200


@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

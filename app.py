import json
import logging
import os
import re

import flask.cli
import httpx
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("code-review-assistant")

WORD_LIMIT = 200
MODEL_NAME = "gemini-flash-lite-latest"
REQUEST_TIMEOUT_MS = 10_000

REVIEW_PROMPT = """You are an expert code reviewer. You will be given a short code snippet. Analyze it and return ONLY a JSON object (no markdown, no code fences) with exactly this shape:

{{
  "language": "<detected programming language>",
  "positive_note": "<one specific, genuine positive observation about the code>",
  "improvements": ["<specific actionable improvement>", ...]
}}

Rules:
- "positive_note" is always required - find one genuine strength, even in flawed code.
- "improvements" must contain between 0 and 3 items.
- Only include an improvement if it is a real, specific, actionable issue with this exact snippet. Do not invent filler improvements to reach 3.
- If the code is already correct and has no meaningful improvements, return an empty "improvements" array - do not fabricate suggestions.
- Each improvement must reference a specific line, pattern, or behavior - no generic advice.
- Do not rewrite the whole snippet inside the JSON.

Code snippet:
'''
{code}
'''
"""

app = Flask(__name__, static_folder="static", static_url_path="")

_client = None


def get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable is not set")
        _client = genai.Client(api_key=api_key)
    return _client


def extract_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError("Model response did not contain valid JSON")


@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/config")
def config():
    return jsonify({"word_limit": WORD_LIMIT})


@app.route("/review", methods=["POST"])
def review():
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()

    if not code:
        logger.warning("Rejected request: empty code snippet")
        return jsonify({"error": "Please paste a code snippet before submitting."}), 400

    word_count = len(code.split())
    logger.info("Received review request (%d words)", word_count)

    if word_count > WORD_LIMIT:
        logger.warning("Rejected request: %d words exceeds limit of %d", word_count, WORD_LIMIT)
        return jsonify({
            "error": f"Snippet is {word_count} words, which exceeds the {WORD_LIMIT}-word limit."
        }), 400

    try:
        logger.info("Calling Gemini model %s...", MODEL_NAME)
        client = get_client()
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=REVIEW_PROMPT.format(code=code),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
            ),
        )
        result = extract_json(response.text)
    except RuntimeError as exc:
        logger.error("Configuration error: %s", exc)
        return jsonify({"error": str(exc)}), 500
    except httpx.TimeoutException:
        logger.error("Gemini request timed out after %d ms", REQUEST_TIMEOUT_MS)
        return jsonify({"error": "The review took too long and was cancelled. Please try again."}), 504
    except genai_errors.APIError as exc:
        logger.exception("Gemini API error (code %s)", exc.code)
        if exc.code == 503:
            message = "The Gemini API is currently overloaded. Please try again in a moment."
        elif exc.code == 429:
            message = "Rate limit reached for the Gemini API. Please wait a moment and try again."
        elif exc.code in (401, 403):
            message = "The Gemini API key is invalid or missing permissions."
        else:
            message = exc.message or "The review service returned an unexpected error."
        return jsonify({"error": message}), 502
    except Exception:
        logger.exception("Gemini request failed")
        return jsonify({"error": "The review service is unavailable right now. Please try again."}), 502

    improvements = result.get("improvements") or []
    if not isinstance(improvements, list):
        improvements = []

    logger.info("Review complete: %d improvement(s) returned", len(improvements[:3]))

    return jsonify({
        "language": result.get("language", ""),
        "positive_note": result.get("positive_note", ""),
        "improvements": improvements[:3],
    })


if __name__ == "__main__":
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    flask.cli.show_server_banner = lambda *args, **kwargs: None
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        logger.info("Serving Flask app 'app' (debug mode: on)")
        logger.info("Running on http://127.0.0.1:8000")
    app.run(port=8000, debug=True)

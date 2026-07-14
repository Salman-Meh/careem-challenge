# Code Review Assistant

A single-page web app that reviews a pasted code snippet and returns:
- **One positive note** (always included)
- **Up to three improvements** (only the ones that are actually applicable — if the snippet is already solid, you may get zero)

The frontend is a single static HTML page; the backend is a small Flask API that calls the Gemini API. No Docker, no build step, no Node.js — just Python.

## Prerequisites

- Python 3.8 or newer
- pip
- A free Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey) (no credit card required)

## Setup

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

   If `pip` isn't found (common on macOS with Homebrew Python), use `pip3` instead:

   ```bash
   pip3 install -r requirements.txt
   ```

2. Set your Gemini API key:

   Copy `.env.example` to `.env` and fill in your key:
   ```bash
   cp .env.example .env
   ```

   ```
   GEMINI_API_KEY=your_key_here
   ```

   (`.env` is gitignored — the app loads it automatically on startup via `python-dotenv`.)

3. Start the server:

   ```bash
   python app.py
   ```

4. Open your browser to **http://localhost:8000**

That's it — the same server serves both the frontend and the API, so there's nothing else to configure.

## Usage

Paste a code snippet into the textarea and click **Review Code**. The word counter shows the current word limit (default 200 words, pulled from the backend) and the button disables automatically if you go over it or leave the box empty.

## Configuration

- **Word limit**: change `WORD_LIMIT` in `app.py`. The frontend reads this value from `GET /config` automatically, so there's only one place to edit.
- **Model**: change `MODEL_NAME` in `app.py` if you want to use a different Gemini model.
- **Port**: the app runs on port `8000` by default (chosen to avoid conflicting with macOS AirPlay Receiver, which often occupies port 5000). Change the `app.run(port=8000, ...)` call in `app.py` if needed.

## Project structure

```
app.py               # Flask backend: serves the frontend + /config and /review APIs
requirements.txt      # flask, google-genai
static/index.html      # single-page frontend (HTML/CSS/vanilla JS, no build step)
.env.example           # documents the GEMINI_API_KEY variable name
```

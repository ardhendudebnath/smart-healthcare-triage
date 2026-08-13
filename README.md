# smart-healthcare-triage

Symptom-based healthcare triage assistant — NLP + rule-based urgency classification, evolving toward a deep learning model.

Describe symptoms in plain English, Hindi or Bengali; get back an urgency level
(`emergency`, `urgent_care` or `self_care`, plus `unknown` when nothing is
recognised), which helpline to call, which kind of specialist to see, and a
directory of local departments with live open/closed badges.

> **This is a prototype, not medical advice.** It does not diagnose. Every
> result carries a disclaimer and, where relevant, an instruction to call 112.
> Do not use it as the basis for a real clinical decision.

---

## Requirements

- **Python 3.11** — what the project is developed and tested against.
- No Node toolchain and no build step. The frontend is plain HTML, CSS and JS
  served as static files, so there is nothing to compile.

## Setup

Run these from the repository root.

**1. Create the virtual environment.** `smt/` is the name the `.gitignore`
already expects:

```bash
python -m venv smt
```

**2. Install dependencies.** This also pulls the spaCy English model
(`en_core_web_sm`), which is pinned by URL in `requirements.txt`, so no separate
`spacy download` step is needed. `pytest` is not a runtime dependency and is
listed separately here:

```bash
smt/Scripts/python.exe -m pip install -r backend/requirements.txt pytest
```

On macOS or Linux the interpreter is `smt/bin/python` instead of
`smt/Scripts/python.exe`. Every command below follows the same substitution.

## Running

The app is two processes. Start each in its own terminal.

**Backend** (FastAPI on port 8000):

```bash
smt/Scripts/python.exe -m uvicorn main:app --app-dir backend --port 8000 --reload
```

**Frontend** (static file server on port 5500):

```bash
smt/Scripts/python.exe -m http.server 5500 --directory frontend
```

Then open <http://localhost:5500>.

**The backend port matters.** `frontend/app.js` hardcodes
`const API = "http://127.0.0.1:8000"`, so the backend has to be on 8000 or the
frontend cannot reach it. The frontend port is free to change — the API allows
all CORS origins.

`--reload` restarts the backend when a `.py` file changes. It does **not** watch
`.env`, so restart by hand after editing that. The frontend is static: just
refresh the browser.

## Tests

```bash
smt/Scripts/python.exe -m pytest backend
```

75 tests, covering symptom extraction (including negation, typo tolerance and
the three-language vocabulary), urgency rules, age and duration escalation,
opening-hours logic, safety overrides and the API endpoints.

## Optional: Gemini extraction

The app extracts symptoms offline with spaCy by default, and that path is what
the tests exercise. Gemini can be layered on top for free-text that the
vocabulary does not cover.

Copy the template and paste a key from [Google AI Studio](https://aistudio.google.com):

```bash
cp backend/.env.example backend/.env
```

`backend/.env` is git-ignored, so the key never reaches GitHub. Leaving
`GEMINI_API_KEY` blank is fine and fully supported — the app skips the call and
uses offline extraction.

Worth knowing: when a key **is** set but the API is slow or failing, each triage
request waits out a 6-second budget (`WAIT_BUDGET_SECONDS` in
`backend/llm_extract.py`) before falling back. Results are identical either way,
so blank the key if you want instant responses for a demo.

## Optional: a real doctor directory

With no `doctors.json`, the app serves obviously-fake placeholder entries with
unusable phone numbers (`+91 00000 000NN`) and a visible warning badge. That is
deliberate: a realistic-looking number in a triage app could send someone having
a heart attack to a dead line.

To supply real contacts, copy a template to `backend/doctors.json` and edit it:

```bash
cp backend/doctors.example.json backend/doctors.json
```

`doctors.json` is git-ignored, so private contact details stay out of version
control. `doctors.agartala.json` is a filled-in directory for Agartala that can
be copied instead.

Validate the file before relying on it. The runtime skips malformed entries
silently with only a log line, which is right for a live service and wrong for
the person filling the file in; this reports every one instead:

```bash
smt/Scripts/python.exe backend/check_doctors.py
```

It resolves `doctors.json` relative to `backend/`, so run it from anywhere. Pass
another filename to check that instead. Warnings ("no coordinates", "no phone
number") still exit 0 — only errors, the things that drop an entry or mislead a
patient, exit 1.

## Project layout

```
backend/     FastAPI app, triage logic, symptom vocabulary, translations, tests
frontend/    Three-tab UI: symptom checker, symptom guide, doctor directory
smt/         Virtual environment (git-ignored, created during setup)
```

Key backend modules: `main.py` (API), `nlp_utils.py` (extraction), `symptoms.py`
(79-symptom vocabulary), `context.py` (age and duration escalation), `safety.py`
(red-flag overrides), `hours.py` (open/closed logic), `doctors.py` (directory),
`i18n.py` (English, Hindi, Bengali).

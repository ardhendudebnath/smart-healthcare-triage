# smart-healthcare-triage

Symptom-based healthcare triage assistant — NLP + rule-based urgency classification, evolving toward a deep learning model.

Describe symptoms in plain English, Hindi or Bengali; get back an urgency level
(`emergency`, `urgent_care` or `self_care`, plus `unknown` when nothing is
recognised), which helpline to call, which kind of specialist to see, and a
directory of local departments with live open/closed badges.

- **Works offline.** The app, the symptom guide and the doctor directory are
  cached, so it opens and stays useful with no signal. Fresh triage needs a
  connection and says so — it never replays an old answer.
- **Asks follow-up questions.** Two or three targeted questions can move a
  headache from routine to emergency. Answers can only ever escalate.
- **Records every decision.** Each result is stamped with the exact ruleset and
  vocabulary that produced it, and written to an append-only audit trail.
- **Hands off to a clinician.** A structured summary endpoint gives the doctor
  who sees the patient next the words they actually wrote and what graded them.
- **Three languages throughout**, including the offline extraction path.
- **Installable, and animated where it helps.** View Transitions carry the eye
  to a verdict that changed; reduced-motion preferences turn them off entirely.

> **This is a prototype, not medical advice.** It does not diagnose. Every
> result carries a disclaimer and, where relevant, an instruction to call 112.
> Do not use it as the basis for a real clinical decision.
>
> The urgency rules and the follow-up questions are built from commonly
> published warning signs and **have not been reviewed by a clinician**. The
> audit trail exists to make that review possible; it is not a substitute for
> it, and no amount of engineering here changes that.

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

122 tests, covering symptom extraction (including negation, typo tolerance and
the three-language vocabulary), urgency rules, age and duration escalation,
opening-hours logic, safety overrides, version stamping, the audit trail, the
follow-up questions and the API endpoints.

Two of them are load-bearing rather than routine, and are worth knowing about
before changing anything they cover:

- `test_no_answer_can_ever_lower_a_grade` checks every combination of follow-up
  answers against every starting grade. A single rule with a de-escalating
  effect would be easy to add and dangerous to ship.
- `test_every_phrase_finds_its_own_symptom` walks all 487 phrases in the
  vocabulary and asserts each one still extracts the symptom that owns it,
  catching phrases made unreachable by a lemma clash.

## API

| Method | Path | What it does |
| --- | --- | --- |
| `POST` | `/triage` | Grade a description. Returns urgency, contacts, specialities, version stamps, an `event_id` and any follow-up questions. |
| `POST` | `/triage/{event_id}/followup` | Re-grade with follow-up answers folded in. |
| `GET` | `/triage/{event_id}/summary` | Structured clinical handoff for the next doctor. |
| `GET` | `/version` | Which app, ruleset and vocabulary are serving. |
| `GET` | `/audit/stats` | Aggregate counts. No free text, no individuals. |
| `GET` | `/audit/unrecognised` | Inputs the vocabulary could not read. |
| `GET` | `/symptoms` `/specialties` `/doctors` `/languages` | Reference data, per language. |

## Offline

The service worker caches the shell, the symptom vocabulary, the specialities
and the doctor directory. Open the app with no signal and the emergency
numbers, the symptom guide and the directory all still work.

The rule throughout is that **cached information is fine and cached judgement is
not**. `POST /triage` is never cached and never falls back. Replaying an earlier
answer against new symptoms would let someone read a stale grade as a verdict on
what they just typed, so offline triage fails loudly and points at 112 instead.

The 112 button needs none of this — `tel:` links are handled by the dialer and
work with no network, no cache and no service worker at all.

### Caching repairs itself

Install runs once. If it fails — a flaky connection, a captive portal, a server
restarted mid-request — the worker still activates and the caches stay empty,
which used to mean offline support was off permanently with nothing to say so.
The app looks healthy right up until the network goes away and it will not load
at all.

That failure lands hardest on the person the feature exists for: someone whose
first visit happens on a bad connection is the most likely to need the app
offline later. So caching re-runs on activate and whenever the page reports the
network is back, rather than being a one-shot. `clients.claim()` runs last and
outside the error handling, because a caching problem must never cost the worker
control of the app.

### Deploying a change to the frontend

Bump **both** together, or returning browsers keep running the old app:

- `?v=` on the stylesheet and script in `frontend/index.html` (currently `v=4`)
- `CACHE_VERSION` in `frontend/sw.js` (currently `triage-v4`) and the matching
  `?v=` in `SHELL_ASSETS` — the browser requests `app.js?v=4`, so precaching a
  bare `app.js` would store a URL nothing ever asks for

This is not housekeeping. A stale cache means a user running last month's triage
rules against this month's interface, with nothing on screen to suggest
anything is wrong.

## Interface

No framework and no build step; everything below is native browser capability.

**View Transitions** animate tab switches and re-graded results. The transition
earns its place on the second render rather than the first: answering a
follow-up can move a verdict from routine to emergency, and a badge that
silently swaps colour is easy to miss. The card morphs, and the badge morphs
separately and slightly slower so the colour change is the last thing to move. A
first render animates nothing — there is no previous state, and an entrance
flourish in front of an urgency grade is a delay dressed as polish.

**Reduced motion** is checked in JavaScript, not only in CSS.
`startViewTransition` is never called and the update is instant, because
honouring the preference by animating anyway and hiding the result is not
honouring it. The CSS override remains as a second line of defence.

**The result panel** leads with a tinted band carrying the urgency colour, so
the verdict separates from its supporting detail at a glance. Urgency is always
carried by a word and an icon as well as a colour — roughly one man in twelve
cannot reliably tell red from green, and "how urgent is this" is the question
they came to ask.

**Performance.** `content-visibility` on the symptom guide, which renders all 79
symptoms and is most of the page's DOM. Container queries on doctor cards, which
appear inside a result and in the full directory at different widths, so a card
adapts to its column rather than guessing from the viewport.

**Print** is a supported output, not an afterthought: the point of saving a
result is handing it to a doctor. The screen layout insets the result's children
so the header band can run full width, and the print block resets both that and
the colour wash — a tint behind black text is the first thing to go wrong on a
mono printer.

## Traceability and the audit trail

Every graded result carries a version stamp:

```json
"versions": { "app": "0.5.0", "ruleset": "4bd97f2ed034", "vocabulary": "92b8de396605" }
```

The ruleset and vocabulary values are **content hashes, not hand-typed numbers**.
A version someone has to remember to bump is wrong the moment they forget, and
it fails silently — the log keeps saying `v3` while `v3` quietly means three
different things. They are separate from each other because "we started
recognising that phrase" and "we changed how we grade it" have different
consequences.

Each decision is written to `backend/audit.db` (SQLite, created automatically)
with the stamps that produced it. The log is append-only: no update, no per-row
delete. `audit.purge_before(days)` is the single exception and removes whole
date ranges to honour a retention policy — data protection, not revision.

A failed write never blocks a result. An app that stops giving urgency advice
because a disk filled up has failed at the only thing that matters.

### This database is health data

It contains free text about people's symptoms. It is git-ignored along with its
WAL sidecars, and it should live on an encrypted disk with `purge_before` on a
schedule. Those are deployment decisions the code cannot make for you.

What is deliberately **not** stored: no name, no phone number, no IP address,
nothing identifying. Exact age is reduced to a band (`73` becomes `65_79`) since
the rules only use the band. Crisis disclosures are counted but their text is
withheld — knowing the path fired is what safety review needs, and keeping a
verbatim record of someone saying they want to hurt themselves is a much heavier
thing to hold.

### The most useful query in the project

```bash
curl http://127.0.0.1:8000/audit/unrecognised
```

Every row is a real person who described a real problem in words the
79-symptom vocabulary does not contain. It is a direct instruction about which
phrase to add next — and, later, the labelled training set if the extraction
step is ever replaced by a model.

## Follow-up questions

"I have a headache" says almost nothing. One that built over a day is ordinary;
one that hit full force in seconds is a possible bleed. `/triage` returns up to
three questions that separate such cases, and `/triage/{id}/followup` re-grades
with the answers.

Four rules govern them, and they matter more than the question list:

1. **Answers can only escalate.** This is what makes them safe to answer
   carelessly. Chest pain is graded emergency deliberately — over-triaging most
   people because the cost of missing a cardiac case is not comparable — and a
   "no" must never undo that. It means "no new information", not "less urgent
   than we thought".
2. **Nothing is asked once the result is emergency or crisis.** That person
   needs an ambulance or a counsellor, not a questionnaire.
3. **Answers are optional.** The first result is a real result.
4. **Where an answer maps onto a known symptom it adds that symptom** and lets
   `knowledge_graph.py` re-grade, rather than deciding urgency separately. One
   graded path through the app instead of two that can disagree.

Refinements are recorded as new audit events rather than overwriting the
original — both are true, and keeping only the second would hide the escalation
that is the point of asking.

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
frontend/    Three-tab UI, service worker, PWA manifest
smt/         Virtual environment (git-ignored, created during setup)
```

Backend modules, roughly in the order a request meets them:

| Module | Role |
| --- | --- |
| `main.py` | The API. Layers the steps below in a fixed order. |
| `safety.py` | Crisis and plain-language emergency overrides. Runs first. |
| `nlp_utils.py` | Extraction: lemmatisation, fuzzy matching, negation. |
| `llm_extract.py` | Optional Gemini extraction, with offline fallback. |
| `symptoms.py` | The 79-symptom, 487-phrase vocabulary. |
| `phrases_indic.py` | Hindi and Bengali red flags for the offline path. |
| `knowledge_graph.py` | The urgency rules. Deterministic on purpose. |
| `context.py` | Age and duration. Can only escalate. |
| `followup.py` | The questions that sharpen a result. Can only escalate. |
| `version.py` | Content-hashed ruleset and vocabulary stamps. |
| `audit.py` | Append-only record of every decision. |
| `hours.py` | Open-now logic for the directory. |
| `doctors.py` | The directory, with placeholder fallback. |
| `i18n.py` | English, Hindi, Bengali. No user-facing text in the frontend. |

| Frontend file | Role |
| --- | --- |
| `index.html` | Structure only. Every string carries `data-i18n` and is filled from the backend. |
| `styles.css` | Design tokens, both themes, view-transition choreography, print. |
| `app.js` | All behaviour. No framework, no bundler, no dependencies. |
| `sw.js` | Offline caching, and the rule that judgement is never cached. |
| `manifest.json` | Installable as an app; icons are inline SVG data URIs. |

### Two deliberate architectural choices

**No framework and no build step**, and that is not an oversight. A Node
toolchain is one more thing that can break five minutes before a demonstration,
and the app is three tabs of mostly static content. Everything the interface
does — view transitions, container queries, `content-visibility`, offline —
is native browser capability, so there is nothing to install and nothing to
compile. If the project grows several more stateful screens, or more people
start working on it, Vite with a small runtime is the honest next step; until
one of those is true, adopting a framework would trade a working decision for
fashion.

**Deterministic rules rather than a learned model.** Every urgency decision is
reproducible, testable and explainable line by line to a clinician, which a
model could not offer. The place machine learning genuinely belongs here is
extraction — turning free text into symptom names — where errors stay
recoverable because the rules still decide urgency, and where
`/audit/unrecognised` is already collecting the training data.

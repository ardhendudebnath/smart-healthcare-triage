/* Smart Healthcare Triage — frontend behaviour.
 *
 * No framework and no build step: the backend is Python, and adding a Node
 * toolchain here would buy nothing visual while giving a demo one more thing to
 * break.
 *
 * One rule throughout: every value that came from the API is written with
 * textContent, never innerHTML. Symptom labels and doctor names are data, and
 * doctors.json is a file a user edits by hand — treating any of it as markup
 * would turn a typo into script execution.
 */

const API = "http://127.0.0.1:8000";

/* Urgency presentation. Each level gets a word and an icon as well as a colour,
 * so the result does not depend on colour vision alone. The words come from the
 * backend string table; only the colours and icons live here. */
const LEVELS = {
  emergency:   { color: "var(--emergency)", tint: "var(--emergency-tint)", icon: "🚑" },
  urgent_care: { color: "var(--urgent)",    tint: "var(--urgent-tint)",    icon: "⏱" },
  self_care:   { color: "var(--routine)",   tint: "var(--routine-tint)",   icon: "🗓" },
  unknown:     { color: "var(--unknown)",   tint: "var(--unknown-tint)",   icon: "❔" },
  crisis:      { color: "var(--crisis)",    tint: "var(--crisis-tint)",    icon: "💬" },
};

/* Example prompts per language. These are input, not interface text — they have
 * to be in the language the user will actually type, so they cannot be
 * translations of each other and are not served from the string table. */
const EXAMPLES = {
  en: [
    "I've had a fever and a cough for three days",
    "chest pain and I feel sick",
    "my knee is swollen and I can't put weight on it",
    "burning when I pee",
    "worst headache of my life with a stiff neck",
  ],
  hi: [
    "तीन दिन से बुखार और खाँसी है",
    "सीने में दर्द हो रहा है और जी मिचला रहा है",
    "घुटना सूज गया है",
    "पेशाब में जलन हो रही है",
    "बहुत तेज़ सिरदर्द और गर्दन अकड़ी हुई है",
  ],
  bn: [
    "তিন দিন ধরে জ্বর আর কাশি",
    "বুকে ব্যথা হচ্ছে আর গা গোলাচ্ছে",
    "হাঁটু ফুলে গেছে",
    "প্রস্রাবে জ্বালা করছে",
    "খুব তীব্র মাথাব্যথা আর ঘাড় শক্ত",
  ],
};

/* The interface string table for the active language. Populated before anything
 * renders; the inline English in index.html is what shows until it arrives. */
let strings = {};
let currentLang = "en";

/** A string from the table, falling back to whatever the HTML already had. */
function t(key, fallback) {
  return strings[key] || fallback || key;
}

const RED_FLAG_WEIGHT = 3;

const $ = (id) => document.getElementById(id);

/* -------------------------------------------------------------- utilities */

/** Digits only, so "+91 98765 43210" becomes a dialable href.
 *  A number written as "102 / 108" means two alternatives; take the first. */
function dialable(number) {
  if (!number) return "";
  return String(number).split("/")[0].replace(/[^\d+]/g, "");
}

/** wa.me needs the country code and no punctuation at all, not even the plus.
 *  An optional prefilled message saves the patient retyping their symptoms into
 *  a chat window they have already described once. */
function whatsappLink(number, prefill) {
  const digits = dialable(number).replace(/\D/g, "");
  if (!digits) return "";
  const base = `https://wa.me/${digits}`;
  return prefill ? `${base}?text=${encodeURIComponent(prefill)}` : base;
}

/* The most recent triage result, kept so the doctor cards can quote it. */
let lastResult = null;

/** The message a WhatsApp button opens with.
 *
 *  Deliberately factual and short: symptoms, how long, what the app concluded,
 *  and an explicit note that a machine produced it. A doctor's assistant reading
 *  this needs to know immediately that it is not a clinician's assessment. */
function whatsappPrefill() {
  if (!lastResult) return "";

  const lines = [t("wa_greeting")];

  const symptoms = (lastResult.symptom_details || []).map((s) => s.label);
  if (symptoms.length) lines.push(`${t("wa_symptoms")}: ${symptoms.join(", ")}.`);

  const duration = $("duration");
  if (duration.value) {
    lines.push(`${t("wa_duration")}: ${duration.options[duration.selectedIndex].text}.`);
  }

  const age = $("age").value.trim();
  if (age) lines.push(`${t("wa_age")}: ${age}.`);

  lines.push(`${t("wa_result")}: ${levelLabel(lastResult.urgency_level)}.`);
  lines.push(t("wa_footer"));

  return lines.join("\n");
}

function levelLabel(level) {
  return t(`level_${level}`, level);
}

/* ------------------------------------------------------- location & distance */

/* The patient's coordinates. Held in memory only — never sent to the backend,
 * never written to storage, never put in a URL. Distance is computed here so a
 * request for a cardiologist is not also a disclosure of where the person
 * asking lives. That is why the backend serves doctor coordinates rather than
 * accepting the patient's. */
let userPosition = null;

const EARTH_RADIUS_KM = 6371;

/** Great-circle distance in km. Straight-line, not driving distance — good
 *  enough to rank a directory, and it needs no routing service or API key. */
function distanceKm(a, b) {
  const toRad = (deg) => (deg * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(h));
}

/** Distance from the patient to a doctor, or null when either end is unknown. */
function doctorDistance(doctor) {
  if (!userPosition || doctor.lat === null || doctor.lng === null) return null;
  return distanceKm(userPosition, { lat: doctor.lat, lng: doctor.lng });
}

function formatDistance(km) {
  if (km === null) return "";
  return km < 1
    ? t("distance_m").replace("{distance}", String(Math.round(km * 1000)))
    : t("distance_km").replace("{distance}", km.toFixed(km < 10 ? 1 : 0));
}

/** Availability badge text from the backend's status key plus its parameters. */
function availabilityText(availability) {
  if (!availability) return { label: t("status_hours_unknown"), open: false, detail: "" };

  const label = t(`status_${availability.status}`, availability.status);
  const params = availability.params || {};
  let detail = "";
  if (params.until) detail = t("until_label").replace("{until}", params.until);
  else if (params.opens) detail = t("opens_label").replace("{opens}", params.opens);

  return { label, open: Boolean(availability.open), detail };
}

/** Open now first, then nearest, then whatever order the directory gave.
 *
 *  Open-before-near on purpose: the nearest clinic is no use at 2am if it is
 *  shut, and a patient acting on a triage result needs somewhere that will
 *  actually answer. Doctors with no coordinates sort after those with them
 *  rather than being hidden — a missing location is a gap in the directory, not
 *  a reason to withhold a phone number. */
function sortForPatient(list) {
  return [...list].sort((a, b) => {
    const openA = a.availability && a.availability.open ? 0 : 1;
    const openB = b.availability && b.availability.open ? 0 : 1;
    if (openA !== openB) return openA - openB;

    const distA = doctorDistance(a);
    const distB = doctorDistance(b);
    if (distA === null && distB === null) return 0;
    if (distA === null) return 1;
    if (distB === null) return -1;
    return distA - distB;
  });
}

/** Ask the browser for the patient's position, then re-render both lists. */
function findNearMe(button) {
  const note = $("location-note");

  if (!navigator.geolocation) {
    note.textContent = t("location_error");
    show(note, true);
    return;
  }

  const original = button.textContent;
  button.disabled = true;
  button.textContent = t("btn_locating");

  const done = () => {
    button.disabled = false;
    button.textContent = original;
  };

  navigator.geolocation.getCurrentPosition(
    (position) => {
      userPosition = {
        lat: position.coords.latitude,
        lng: position.coords.longitude,
      };
      note.textContent = t("sorted_open_nearest");
      show(note, true);
      done();
      renderDoctors();
      if (lastResult) renderResultDoctors();
    },
    (error) => {
      // PERMISSION_DENIED is a choice, not a fault — say so plainly and carry
      // on without distance rather than nagging.
      note.textContent =
        error.code === error.PERMISSION_DENIED
          ? t("location_denied")
          : t("location_error");
      show(note, true);
      done();
    },
    { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }
  );
}

$("find-near-me").addEventListener("click", (e) => findNearMe(e.currentTarget));
$("find-near-me-directory").addEventListener("click", (e) => findNearMe(e.currentTarget));

function initials(name) {
  const words = String(name || "")
    .replace(/^Dr\.?\s+/i, "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (!words.length) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

/** Stable colour per name, so a doctor's avatar does not change between loads. */
function avatarColor(name) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (hash * 31 + name.charCodeAt(i)) % 360;
  }
  return `hsl(${hash} 52% 42%)`;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function show(node, visible) {
  node.hidden = !visible;
}

/* ------------------------------------------------------------------- tabs */

const TABS = [
  { tab: "tab-check", panel: "panel-check" },
  { tab: "tab-guide", panel: "panel-guide" },
  { tab: "tab-doctors", panel: "panel-doctors" },
];

function selectTab(tabId) {
  TABS.forEach(({ tab, panel }) => {
    const isActive = tab === tabId;
    $(tab).classList.toggle("is-active", isActive);
    $(tab).setAttribute("aria-selected", String(isActive));
    show($(panel), isActive);
  });
}

TABS.forEach(({ tab }) => $(tab).addEventListener("click", () => selectTab(tab)));

/* --------------------------------------------------------------- examples */

function renderExamples() {
  const container = $("examples");
  container.textContent = "";
  (EXAMPLES[currentLang] || EXAMPLES.en).forEach((text) => {
    const chip = el("button", "example-chip", text);
    chip.type = "button";
    chip.addEventListener("click", () => {
      $("message").value = text;
      $("message").focus();
    });
    container.appendChild(chip);
  });
}

/* ---------------------------------------------------------------- triage */

function renderSymptoms(details) {
  const list = $("symptoms-list");
  list.textContent = "";

  if (!details.length) {
    show($("symptoms-empty"), true);
    return;
  }
  show($("symptoms-empty"), false);

  details.forEach((detail) => {
    const item = el("li", "symptom-item");
    item.appendChild(el("div", "symptom-item__label", detail.label));
    if (detail.description) {
      item.appendChild(el("div", "symptom-item__desc", detail.description));
    }
    list.appendChild(item);
  });
}

function renderContacts(contacts) {
  const container = $("contacts");
  container.textContent = "";

  (contacts || []).forEach((contact) => {
    const card = el("div", "contact-card");
    card.appendChild(el("div", "contact-card__name", contact.name));

    const link = el("a", "contact-card__number", contact.number);
    link.href = `tel:${dialable(contact.number)}`;
    card.appendChild(link);

    if (contact.note) card.appendChild(el("div", "contact-card__note", contact.note));
    container.appendChild(card);
  });
}

function renderSpecialties(specialties) {
  const container = $("specialties");
  container.textContent = "";

  (specialties || []).forEach((specialty) => {
    const card = el("div", "specialty-card");
    card.appendChild(el("span", "specialty-card__icon", specialty.icon));

    const body = el("div");
    body.appendChild(el("div", "specialty-card__name", specialty.name));
    body.appendChild(el("div", "specialty-card__focus", specialty.focus));
    card.appendChild(body);

    container.appendChild(card);
  });
}

function renderContextNotes(notes) {
  const list = $("result-context");
  list.textContent = "";
  (notes || []).forEach((note) => list.appendChild(el("li", null, note)));
  show(list, Boolean(notes && notes.length));
}

function renderResult(data) {
  lastResult = data;
  const result = $("result");
  const level = LEVELS[data.urgency_level] || LEVELS.unknown;

  result.style.setProperty("--level", level.color);
  result.style.setProperty("--level-tint", level.tint);

  $("result-badge").textContent = `${level.icon} ${levelLabel(data.urgency_level)}`;
  $("result-message").textContent = data.message;

  $("result-reason").textContent = data.reason || "";
  show($("result-reason"), Boolean(data.reason));

  $("result-safety").textContent = data.safety_note || "";
  show($("result-safety"), Boolean(data.safety_note));

  renderContextNotes(data.context_notes);

  // Printed copies are handed to a doctor, so stamp when it was produced and
  // what it is. An undated automated result is worse than useless to a clinician.
  $("print-stamp").textContent = `${new Date().toLocaleString()} — ${t("print_stamp")}`;

  // A crisis result is not a symptom analysis. Showing "what we understood:
  // nothing" underneath it would be both useless and unkind.
  const isCrisis = data.urgency_level === "crisis";
  show($("symptoms-section"), !isCrisis);
  if (!isCrisis) renderSymptoms(data.symptom_details || []);

  renderContacts(data.contacts);
  renderSpecialties(data.recommended_specialties);

  // A crisis result must not turn into a directory browse. The person needs the
  // counselling number in front of them, not a shortlist to pick from.
  if (isCrisis) {
    show($("result-doctors-section"), false);
  } else {
    renderResultDoctors();
  }

  // Jump straight to the first suggested speciality in the directory.
  const first = (data.recommended_specialties || [])[0];
  const jump = $("jump-to-doctors");
  show(jump, Boolean(first));
  jump.onclick = first
    ? () => {
        selectTab("tab-doctors");
        filterDoctors(first.id);
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    : null;

  $("disclaimer").textContent = data.disclaimer || "";
  show(result, true);
}

async function submitTriage() {
  const message = $("message").value.trim();
  if (!message) {
    $("message").focus();
    return;
  }

  const button = $("submit");
  button.disabled = true;
  button.textContent = t("btn_checking");
  show($("error"), false);
  show($("result"), false);

  const age = $("age").value.trim();

  try {
    const response = await fetch(`${API}/triage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        // Both optional; the backend ignores anything it cannot parse.
        age: age === "" ? null : Number(age),
        duration: $("duration").value || null,
        lang: currentLang,
      }),
    });
    if (!response.ok) throw new Error(`Server returned ${response.status}`);
    renderResult(await response.json());
  } catch (err) {
    // The emergency number in the header still works with the server down, and
    // that matters more than the error text.
    $("error").textContent = t("error_server");
    show($("error"), true);
  } finally {
    button.disabled = false;
    button.textContent = t("btn_check");
  }
}

$("submit").addEventListener("click", submitTriage);

// Ctrl/Cmd+Enter submits, which is the convention for a multi-line box.
$("message").addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") submitTriage();
});

$("clear").addEventListener("click", () => {
  $("message").value = "";
  $("age").value = "";
  $("duration").value = "";
  lastResult = null;
  show($("result"), false);
  show($("error"), false);
  $("message").focus();
});

// Browsers offer "Save as PDF" from their own print dialog, so one button covers
// both saving and printing without this app storing any health data itself.
$("print-result").addEventListener("click", () => window.print());

/* -------------------------------------------------------- symptom guide */

let symptomGroups = [];

function renderSymptomGuide(filter) {
  const container = $("symptom-groups");
  container.textContent = "";

  const needle = filter.trim().toLowerCase();
  let shown = 0;

  symptomGroups.forEach((group) => {
    const matches = group.symptoms.filter(
      (symptom) =>
        !needle ||
        symptom.label.toLowerCase().includes(needle) ||
        symptom.description.toLowerCase().includes(needle) ||
        group.label.toLowerCase().includes(needle)
    );
    if (!matches.length) return;

    shown += matches.length;

    const card = el("section", "system-card");
    const title = el("h3", "system-card__title", group.label + " ");
    title.appendChild(el("span", "system-card__count", `${matches.length}`));
    card.appendChild(title);

    matches.forEach((symptom) => {
      const entry = el("div", "symptom-entry");
      const label = el("div", "symptom-entry__label", symptom.label);
      if (symptom.weight >= RED_FLAG_WEIGHT) {
        label.appendChild(el("span", "flag", t("red_flag")));
      }
      entry.appendChild(label);
      entry.appendChild(el("div", "symptom-entry__desc", symptom.description));
      card.appendChild(entry);
    });

    container.appendChild(card);
  });

  show($("symptom-no-results"), shown === 0);
  $("symptom-count").textContent = needle
    ? `${shown} ${t("symptoms_matching")}`
    : `${shown} ${t("symptoms_recognised")}`;
}

function renderDurationOptions(durations) {
  const select = $("duration");
  const previous = select.value;
  select.textContent = "";

  const notSure = document.createElement("option");
  notSure.value = "";
  notSure.textContent = t("duration_not_sure");
  select.appendChild(notSure);

  (durations || []).forEach((duration) => {
    const option = document.createElement("option");
    option.value = duration.id;
    option.textContent = duration.label;
    select.appendChild(option);
  });

  // Keep whatever the user had chosen across a language switch.
  select.value = previous;
}

async function loadSymptoms() {
  try {
    const response = await fetch(`${API}/symptoms?lang=${encodeURIComponent(currentLang)}`);
    if (!response.ok) throw new Error(String(response.status));
    const data = await response.json();
    symptomGroups = data.systems || [];
    renderSymptomGuide($("symptom-search").value || "");
    renderDurationOptions(data.durations);
  } catch {
    $("symptom-count").textContent = t("error_symptoms");
  }
}

$("symptom-search").addEventListener("input", (event) =>
  renderSymptomGuide(event.target.value)
);

/* ------------------------------------------------------ doctor directory */

let allDoctors = [];
let allSpecialties = [];
let activeSpecialty = "all";

function doctorCard(doctor) {
  const card = el("article", "doctor-card");
  if (doctor.is_placeholder) card.classList.add("doctor-card--placeholder");

  if (doctor.is_placeholder) {
    card.appendChild(el("span", "placeholder-tag", t("sample_entry")));
  }

  const top = el("div", "doctor-card__top");

  // A real photo if one is configured, initials otherwise. Never a broken image.
  if (doctor.photo) {
    const img = document.createElement("img");
    img.className = "avatar";
    img.src = doctor.photo;
    img.alt = "";
    img.addEventListener("error", () => img.replaceWith(initialsAvatar(doctor.name)));
    top.appendChild(img);
  } else {
    top.appendChild(initialsAvatar(doctor.name));
  }

  const heading = el("div");
  heading.appendChild(el("div", "doctor-card__name", doctor.name));
  if (doctor.qualification) {
    heading.appendChild(el("div", "doctor-card__qual", doctor.qualification));
  }
  const specialty = allSpecialties.find((s) => s.id === doctor.specialty);
  if (specialty) {
    heading.appendChild(el("div", "doctor-card__specialty", specialty.name));
  }
  top.appendChild(heading);
  card.appendChild(top);

  // Open/closed and how far, side by side — the two things that decide whether
  // this doctor is worth calling right now.
  const badges = el("div", "doctor-card__badges");

  const availability = availabilityText(doctor.availability);
  const statusBadge = el(
    "span",
    `status-badge ${availability.open ? "status-badge--open" : "status-badge--closed"}`,
    availability.label
  );
  badges.appendChild(statusBadge);
  if (availability.detail) {
    badges.appendChild(el("span", "badge-detail", availability.detail));
  }

  const distance = doctorDistance(doctor);
  if (distance !== null) {
    badges.appendChild(el("span", "distance-badge", formatDistance(distance)));
  } else if (userPosition && doctor.lat === null) {
    badges.appendChild(el("span", "badge-detail", t("location_missing")));
  }

  card.appendChild(badges);

  const meta = el("ul", "doctor-card__meta");
  const rows = [
    [t("doctor_hospital"), doctor.hospital],
    [t("doctor_city"), doctor.city],
    [t("doctor_hours"), doctor.timings],
    [t("doctor_speaks"), (doctor.languages || []).join(", ")],
    [t("doctor_assistant"), doctor.assistant_name],
  ];
  rows.forEach(([key, value]) => {
    if (!value) return;
    const row = el("li");
    row.appendChild(el("span", "k", key));
    row.appendChild(el("span", "v", value));
    meta.appendChild(row);
  });
  if (meta.children.length) card.appendChild(meta);

  const actions = el("div", "doctor-card__actions");

  if (doctor.phone) {
    const call = el("a", "btn btn--primary btn--small", t("btn_call"));
    call.href = `tel:${dialable(doctor.phone)}`;
    actions.appendChild(call);
  }
  if (doctor.whatsapp && whatsappLink(doctor.whatsapp)) {
    const prefill = whatsappPrefill();
    const chat = el(
      "a",
      "btn btn--ghost btn--small",
      prefill ? t("btn_whatsapp_result") : t("btn_whatsapp")
    );
    // Built at click time, not at render time: the cards are drawn once but the
    // user may run a triage afterwards, and a stale link would send an empty
    // message or last week's symptoms.
    chat.href = whatsappLink(doctor.whatsapp, prefill);
    chat.target = "_blank";
    chat.rel = "noopener noreferrer";
    chat.addEventListener("click", () => {
      chat.href = whatsappLink(doctor.whatsapp, whatsappPrefill());
    });
    actions.appendChild(chat);
  }
  if (doctor.assistant_phone) {
    const assistant = el("a", "btn btn--ghost btn--small", t("btn_call_assistant"));
    assistant.href = `tel:${dialable(doctor.assistant_phone)}`;
    actions.appendChild(assistant);
  }
  if (actions.children.length) card.appendChild(actions);

  return card;
}

function initialsAvatar(name) {
  const avatar = el("div", "avatar", initials(name));
  avatar.style.setProperty("--avatar-bg", avatarColor(String(name || "")));
  avatar.setAttribute("aria-hidden", "true");
  return avatar;
}

function renderDoctors() {
  const grid = $("doctor-grid");
  grid.textContent = "";

  const listed = sortForPatient(
    activeSpecialty === "all"
      ? allDoctors
      : allDoctors.filter((d) => d.specialty === activeSpecialty)
  );

  listed.forEach((doctor) => grid.appendChild(doctorCard(doctor)));
  show($("doctor-empty"), listed.length === 0);
}

/* How many doctors to show inside the result. Enough to choose from, few enough
 * that the answer to "who do I call" is still a decision and not a list. */
const RESULT_DOCTOR_LIMIT = 3;

/** The doctor block inside the triage result, for the recommended speciality. */
function renderResultDoctors() {
  const section = $("result-doctors-section");
  const grid = $("result-doctors");
  grid.textContent = "";

  const first = (lastResult && lastResult.recommended_specialties) || [];
  if (!first.length || !allDoctors.length) {
    show(section, false);
    return;
  }

  const specialtyId = first[0].id;
  const matching = sortForPatient(
    allDoctors.filter((d) => d.specialty === specialtyId)
  ).slice(0, RESULT_DOCTOR_LIMIT);

  if (!matching.length) {
    show(section, false);
    return;
  }

  matching.forEach((doctor) => grid.appendChild(doctorCard(doctor)));
  show(section, true);

  // "See all" jumps to the directory already filtered to this speciality.
  $("see-all-doctors").onclick = () => {
    selectTab("tab-doctors");
    filterDoctors(specialtyId);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
}

function filterDoctors(specialtyId) {
  activeSpecialty = specialtyId;
  document.querySelectorAll(".filter-chip").forEach((chip) => {
    chip.classList.toggle("is-active", chip.dataset.specialty === specialtyId);
    chip.setAttribute("aria-pressed", String(chip.dataset.specialty === specialtyId));
  });
  renderDoctors();
}

function renderFilters(counts) {
  const container = $("specialty-filters");
  container.textContent = "";

  const makeChip = (id, label, count) => {
    const chip = el("button", "filter-chip");
    chip.type = "button";
    chip.dataset.specialty = id;
    chip.appendChild(el("span", null, label));
    chip.appendChild(el("span", "filter-chip__count", String(count)));
    chip.addEventListener("click", () => filterDoctors(id));
    return chip;
  };

  container.appendChild(makeChip("all", t("filter_all"), allDoctors.length));
  allSpecialties.forEach((specialty) => {
    const count = counts[specialty.id] || 0;
    if (!count) return;
    container.appendChild(
      makeChip(specialty.id, `${specialty.icon} ${specialty.name}`, count)
    );
  });

  filterDoctors(activeSpecialty);
}

async function loadDirectory() {
  try {
    const lang = encodeURIComponent(currentLang);
    const [specialtyRes, doctorRes] = await Promise.all([
      fetch(`${API}/specialties?lang=${lang}`),
      fetch(`${API}/doctors?lang=${lang}`),
    ]);
    if (!specialtyRes.ok || !doctorRes.ok) throw new Error("directory unavailable");

    const specialtyData = await specialtyRes.json();
    const doctorData = await doctorRes.json();

    allSpecialties = specialtyData.specialties || [];
    allDoctors = doctorData.doctors || [];

    show($("placeholder-banner"), Boolean(doctorData.using_placeholders));
    renderFilters(specialtyData.counts || {});

    if (!$("disclaimer").textContent) {
      $("disclaimer").textContent = doctorData.disclaimer || "";
    }
  } catch {
    $("doctor-empty").textContent = t("error_directory");
    show($("doctor-empty"), true);
  }
}

/* -------------------------------------------------------------- language */

/** Write the string table into every element tagged with data-i18n. */
function applyStrings() {
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const value = strings[node.dataset.i18n];
    if (value) node.textContent = value;
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    const value = strings[node.dataset.i18nPlaceholder];
    if (value) node.placeholder = value;
  });

  // Tells the browser which language the page is in, so a screen reader picks
  // the right pronunciation rules for Devanagari and Bengali.
  document.documentElement.lang = currentLang;

  renderExamples();

  // Anything already on screen was rendered in the previous language.
  if (lastResult) renderResult(lastResult);
}

function renderLanguagePicker(languages) {
  const select = $("language");
  select.textContent = "";
  languages.forEach((language) => {
    const option = document.createElement("option");
    option.value = language.id;
    option.textContent = language.native;
    select.appendChild(option);
  });
  select.value = currentLang;
}

async function setLanguage(lang, { reloadData = true } = {}) {
  try {
    const response = await fetch(`${API}/languages?lang=${encodeURIComponent(lang)}`);
    if (!response.ok) throw new Error(String(response.status));
    const data = await response.json();

    currentLang = data.current;
    strings = data.strings || {};
    renderLanguagePicker(data.languages || []);
    applyStrings();

    // Remember the choice so the app opens in the same language next time.
    try {
      localStorage.setItem("triage-lang", currentLang);
    } catch {
      // Private browsing blocks localStorage. Not being able to remember the
      // language is not a reason to fail.
    }

    if (reloadData) {
      await Promise.all([loadSymptoms(), loadDirectory()]);
    }
  } catch (err) {
    // Do not fail silently here. If the string table cannot be fetched, nothing
    // on the page renders at all, and swallowing the error leaves a blank app
    // with no clue why — which is exactly what happened the first time this ran
    // against a server that predated the /languages endpoint.
    console.error("Could not load language strings:", err);
    $("error").textContent = t("error_server");
    show($("error"), true);
  }
}

$("language").addEventListener("change", (event) => setLanguage(event.target.value));

/* ------------------------------------------------------------------ init */

function storedLanguage() {
  try {
    return localStorage.getItem("triage-lang") || "en";
  } catch {
    return "en";
  }
}

setLanguage(storedLanguage());

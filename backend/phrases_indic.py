"""Hindi and Bengali phrases for the offline extraction path.

Why this is deliberately small
------------------------------
When Gemini is reachable it reads Hindi and Bengali directly and this file is
never consulted. This exists for the case that actually matters: the LLM is
down, rate-limited or unconfigured, and someone is typing in Hindi or Bengali
about an emergency.

Full non-English coverage offline is not achievable here. spaCy's English model
cannot lemmatise Devanagari or Bengali script, so none of the machinery in
nlp_utils.py -- lemma matching, dependency-based negation scope, fuzzy typo
tolerance -- transfers. What is left is literal substring matching, which is
crude enough that a large vocabulary would produce constant false positives.

So the offline Indic path covers red flags only: the symptoms where being
recognised is the difference between an ambulance and a shrug. Everything else
in Hindi or Bengali needs the LLM, and degrades to "unknown" without it -- which
tells the user to rephrase rather than pretending to have understood.

Latin-script transliteration is included alongside the native scripts because a
great many Indian users type Hindi and Bengali on a QWERTY keyboard.

⚠️  Same review caveat as translations_hi.py and translations_bn.py.
"""

from typing import Dict, List

# Substring matching only, so phrases must be distinctive enough that they
# cannot appear inside an unrelated word. Short ambiguous words are excluded on
# purpose -- "dard" (pain) alone would match almost any complaint.
RED_FLAG_PHRASES: Dict[str, List[str]] = {
    "chest_pain": [
        # Hindi
        "सीने में दर्द", "छाती में दर्द", "सीने में जकड़न",
        "seene mein dard", "chhati mein dard", "seene me dard",
        # Bengali
        "বুকে ব্যথা", "বুকে যন্ত্রণা", "বুক ধরে আসছে",
        "buke betha", "buke byatha",
    ],
    "difficulty_breathing": [
        "साँस लेने में तकलीफ", "सांस लेने में तकलीफ", "साँस नहीं आ रही",
        "सांस फूल रही", "दम घुट रहा",
        "saans lene mein takleef", "saans nahi aa rahi", "dam ghut raha",
        "শ্বাস নিতে কষ্ট", "শ্বাস নিতে পারছি না", "দম বন্ধ হয়ে আসছে",
        "sowas nite kosto", "dom bondho",
    ],
    "one_sided_weakness": [
        "एक तरफ कमजोरी", "मुँह टेढ़ा", "मुंह टेढ़ा", "हाथ नहीं उठ रहा",
        "shareer ke ek taraf", "haath nahi uth raha",
        "একদিক অবশ", "মুখ বেঁকে গেছে", "হাত নাড়াতে পারছি না",
        "ek dik obosh", "mukh beke gache",
    ],
    "slurred_speech": [
        "बोली लड़खड़ा", "बोल नहीं पा रहा", "जबान लड़खड़ा",
        "bol nahi pa raha", "boli ladkhada",
        "কথা জড়িয়ে যাচ্ছে", "কথা বলতে পারছে না",
        "kotha joriye", "kotha bolte parche na",
    ],
    "seizure_symptom": [
        "दौरा पड़ा", "मिर्गी का दौरा", "झटके आ रहे",
        "daura pada", "jhatke aa rahe",
        "খিঁচুনি", "খিচুনি হচ্ছে",
        "khichuni",
    ],
    "vomiting_blood": [
        "उल्टी में खून", "खून की उल्टी",
        "ulti mein khoon", "khoon ki ulti",
        "বমিতে রক্ত", "রক্ত বমি",
        "bomite rokto", "rokto bomi",
    ],
    "coughing_blood": [
        "खांसी में खून", "खाँसी में खून", "बलगम में खून",
        "khansi mein khoon", "khansi me khun",
        "কাশিতে রক্ত", "কফে রক্ত",
        "kashite rokto",
    ],
    "unable_to_urinate": [
        "पेशाब नहीं आ रहा", "पेशाब नहीं हो रहा",
        "peshab nahi aa raha", "peshab nahi ho raha",
        "প্রস্রাব হচ্ছে না", "প্রস্রাব বন্ধ",
        "prosrab hocche na",
    ],
    "neck_stiffness": [
        "गर्दन अकड़", "गर्दन में अकड़न", "गर्दन नहीं मुड़",
        "gardan akad", "gardan nahi mud",
        "ঘাড় শক্ত", "ঘাড় নাড়াতে পারছি না",
        "ghar shokto", "ghad shokto",
    ],
    "confusion": [
        "होश में नहीं", "बहकी बातें", "कुछ समझ नहीं आ रहा",
        "hosh mein nahi", "behki baatein",
        "বিভ্রান্ত", "আবোল তাবোল বকছে", "চিনতে পারছে না",
        "abol tabol",
    ],
    "allergic_reaction": [
        "चेहरा सूज", "होंठ सूज", "गला बंद हो रहा", "जीभ सूज",
        "chehra sooj", "gala band ho raha",
        "মুখ ফুলে গেছে", "ঠোঁট ফুলে", "গলা বন্ধ হয়ে আসছে",
        "mukh fule gache", "gola bondho",
    ],
    "child_lethargy": [
        "बच्चा सुस्त", "बच्चा ढीला", "बच्चा जाग नहीं रहा",
        "baccha sust", "baccha jaag nahi raha",
        "বাচ্চা নেতিয়ে", "বাচ্চা জাগছে না",
        "baccha netiye",
    ],
    "child_not_feeding": [
        "बच्चा दूध नहीं पी रहा", "बच्चा कुछ नहीं खा रहा",
        "baccha doodh nahi pi raha",
        "বাচ্চা দুধ খাচ্ছে না", "বাচ্চা কিছু খাচ্ছে না",
        "baccha dudh khacche na",
    ],
    "pregnancy_bleeding": [
        "गर्भावस्था में खून", "प्रेगनेंसी में ब्लीडिंग", "पेट में बच्चा है और खून",
        "pregnancy mein bleeding",
        "গর্ভাবস্থায় রক্তপাত", "পেটে বাচ্চা আছে রক্ত যাচ্ছে",
        "gorbhabosthay roktopat",
    ],
    "fever": [
        # Not a red flag alone, but it is the single most common complaint in
        # both languages and it combines with the red flags above.
        "बुखार", "बुख़ार", "ज्वर",
        "bukhar", "tez bukhar",
        "জ্বর",
        "jor hoyeche", "jwor hoyeche",
    ],
    "cough": [
        # Included for the same reason as fever, and because the three-week
        # cough rule in context.py is the most useful duration rule there is.
        "खांसी", "खाँसी",
        "khansi",
        "কাশি",
        "kashi hocche",
    ],
    "abdominal_pain": [
        "पेट में दर्द", "पेट दर्द",
        "pet mein dard", "pet dard",
        "পেটে ব্যথা", "পেট ব্যথা",
        "pete betha", "pete byatha",
    ],
    "headache": [
        "सिर दर्द", "सिरदर्द", "सर दर्द",
        "sir dard", "sar dard",
        "মাথা ব্যথা", "মাথাব্যথা",
        "matha betha", "matha byatha",
    ],
    "vomiting": [
        "उल्टी हो रही", "उल्टी आ रही",
        "ulti ho rahi",
        "বমি হচ্ছে", "বমি করছে",
        "bomi hocche",
    ],
    "diarrhea": [
        "दस्त लग", "पतले दस्त", "लूज मोशन",
        "dast lag", "loose motion",
        "পাতলা পায়খানা", "ডায়রিয়া",
        "patla paykhana",
    ],
}

# Suicide and self-harm, in Hindi and Bengali.
#
# This is the most important entry in this file. The crisis path is the one
# place where failing to understand someone is worst, and until these existed a
# person writing "আমি মরে যেতে চাই" got a shrug -- the English CRISIS_PHRASES in
# safety.py cannot match a word of it. Kept deliberately broad: a false positive
# shows a counselling number to someone who did not need it.
CRISIS_PHRASES_INDIC = [
    # Hindi. Stems rather than full clauses, for the same verb-agreement reason
    # documented on EMERGENCY_OVERRIDE_INDIC below.
    "मरना चाह", "जान दे दू", "जान देना चाह",
    "आत्महत्या", "खुदकुशी", "जीना नहीं चाह",
    "खुद को नुकसान", "मर जाऊ", "खत्म कर दू",
    "marna chah", "jaan de", "atmahatya", "khudkushi",
    "jeena nahi chah", "mar jau",
    # Hindi, indirect. Same reasoning as the English list in safety.py: most
    # disclosure is not the explicit word.
    "जीने का मन नहीं", "जीने की इच्छा नहीं", "अब नहीं जीना",
    "सब खत्म कर", "थक गया हूँ जीने से",
    "jine ka man nahi", "ab nahi jeena",
    # Bengali
    "মরে যেতে চাই", "মরতে চাই", "আত্মহত্যা", "বেঁচে থাকতে চাই না",
    "নিজেকে শেষ করে", "নিজের ক্ষতি", "আত্মঘাতী",
    "more jete chai", "morte chai", "atmohotya", "beche thakte chai na",
    # Bengali, other verb forms of "do not want to live". Bengali has several
    # and the list held only one: "আমি আর বাঁচতে চাই না" -- as ordinary a
    # sentence as any here -- was scored as no recognised symptom at all.
    "বাঁচতে চাই না", "বাঁচতে ইচ্ছে করছে না", "আর বাঁচব না",
    "কোনও মানে নেই বেঁচে",
    "bachte chai na", "ar bachbo na",
]

# Plain-language emergencies in Hindi and Bengali, mirroring the English
# EMERGENCY_OVERRIDE_PHRASES in safety.py. Category names match exactly so the
# two tables can be checked the same way.
#
# Phrases are cut back to the invariant stem rather than a full clause. Hindi
# and Bengali verbs agree with gender and number, so "बेहोश हो गया", "हो गई" and
# "हो गए" are all the same statement -- listing conjugations means missing the
# one nobody thought of, which is how "पापा बेहोश हो गए हैं" slipped through a
# table that had two of the three forms. Anchoring on "बेहोश" catches all of
# them. These words are distinctive enough that the looser match is safe.
EMERGENCY_OVERRIDE_INDIC = {
    "unresponsive": [
        "बेहोश", "होश नहीं", "जवाब नहीं दे", "उठ नहीं रहा", "उठ नहीं रही",
        "behosh", "hosh nahi", "jawab nahi de",
        "অজ্ঞান", "সাড়া দিচ্ছে না", "সাড়া নেই", "জ্ঞান ফিরছে না",
        "oggan", "sara dicche na",
    ],
    "not_breathing": [
        "साँस नहीं", "सांस नहीं", "साँस रुक", "सांस रुक", "दम घुट",
        "saans nahi", "saans ruk",
        "শ্বাস নিচ্ছে না", "শ্বাস বন্ধ", "দম আটকে",
        "sowas nicche na", "dom atke",
    ],
    "cardiac_or_stroke": [
        "दिल का दौरा", "हार्ट अटैक", "लकवा",
        "dil ka daura", "heart attack", "lakwa",
        "হার্ট অ্যাটাক", "স্ট্রোক", "পক্ষাঘাত",
    ],
    "seizure": [
        "दौरा पड़", "मिर्गी",
        "daura pad", "mirgi",
        "খিঁচুনি", "খিচুনি",
        "khichuni",
    ],
    "severe_bleeding": [
        "बहुत खून", "खून रुक नहीं", "खून बह रहा",
        "khoon ruk nahi", "bahut khoon",
        "অনেক রক্ত", "রক্ত বন্ধ হচ্ছে না",
        "onek rokto",
    ],
    "poisoning": [
        "जहर खा", "ज़हर खा", "गोलियां खा", "गोलियाँ खा",
        "zahar kha", "goliyan kha",
        "বিষ খে", "অনেক ওষুধ খে",
        "bish khe",
    ],
}


def check_crisis_indic(text: str) -> bool:
    """True if the text mentions suicide or self-harm in Hindi or Bengali."""
    if not text:
        return False
    lowered = text.lower()
    return any(phrase.lower() in lowered for phrase in CRISIS_PHRASES_INDIC)


def check_emergency_indic(text: str):
    """The category name if the text describes an obvious emergency, else None."""
    if not text:
        return None
    lowered = text.lower()
    for category, phrases in EMERGENCY_OVERRIDE_INDIC.items():
        if any(phrase.lower() in lowered for phrase in phrases):
            return category
    return None

# Denials. Substring matching cannot do dependency-based negation scope, so this
# is limited to the whole message reading as a denial of a specific symptom --
# the common "no fever" case, not the general problem.
NEGATION_MARKERS = ["नहीं है", "नही है", "nahi hai", "নেই", "হয়নি", "nei"]


def extract_indic(text: str) -> List[str]:
    """Red-flag symptoms mentioned in Hindi or Bengali.

    Returns [] for English text, which costs one pass over a short list and
    keeps the caller free of language detection.
    """
    if not text:
        return []

    lowered = text.lower()
    found = set()

    for symptom, phrases in RED_FLAG_PHRASES.items():
        for phrase in phrases:
            position = lowered.find(phrase.lower())
            if position == -1:
                continue
            # Crude negation check: a denial marker immediately after the phrase.
            tail = lowered[position + len(phrase) : position + len(phrase) + 12]
            if any(marker in tail for marker in NEGATION_MARKERS):
                continue
            found.add(symptom)
            break

    return sorted(found)

"""
gmail_scanner.py  –  Gmail OAuth2 integration + deep email parsing
Detects: applications, rejections, OA/assessments, referrals, interviews, offers
Extracts: dates, links, platforms, durations, deadlines, referred-by names
LLM: Uses Groq (free, no credit card) for smart classification when API key is set.
     Set env var GROQ_API_KEY or add key to data/settings via the app.
"""

import os
import re
import json
import time as _time
import base64
from datetime import datetime, timedelta

try:
    import urllib.request
    import urllib.error
    _URLLIB_OK = True
except ImportError:
    _URLLIB_OK = False

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False

import database as db

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# ──────────────────────────────────────────────────────────────────────────────
#  GROQ LLM  (free tier – sign up at console.groq.com, no credit card needed)
# ──────────────────────────────────────────────────────────────────────────────

# Groq free tier — llama-3.1-8b-instant: 30 RPM, 6K TPM, 14,400 RPD
# Our prompt ≈ 700 tokens + preview ≈ 200 tokens = ~900 tokens/call
# At 6K TPM that's ~6 calls/min safely → 1 call every 12s to stay clear
_GROQ_LAST_CALL       = 0.0
_GROQ_MIN_INTERVAL    = 12.0   # seconds between calls
_GROQ_CONSECUTIVE_429 = 0
_GROQ_MAX_PREVIEW     = 600    # chars of email to send — keeps tokens low

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.1-8b-instant"   # 14,400 RPD free — best for bulk scanning

GROQ_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

def _get_groq_key():
    """Return Groq API key from env var or database settings."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        try:
            key = (db.get_setting("groq_api_key") or "").strip()
        except Exception:
            pass
    return key


def llm_classify(subject: str, body: str):
    """
    Ask Groq LLaMA to classify a job-related email.
    Returns dict with keys: is_job_email, classification, company, stage, summary
    or None if LLM is unavailable / key not set.
    Respects Groq free tier rate limits with automatic backoff on 429.
    """
    global _GROQ_LAST_CALL, _GROQ_CONSECUTIVE_429

    api_key = _get_groq_key()
    if not api_key:
        return None

    # ── Rate limit: enforce minimum gap between calls ──────────────────
    elapsed = _time.monotonic() - _GROQ_LAST_CALL
    if elapsed < _GROQ_MIN_INTERVAL:
        _time.sleep(_GROQ_MIN_INTERVAL - elapsed)

    # Keep preview short — llama-3.1-8b-instant has only 6K TPM on free tier
    preview = (subject + "\n" + body)[:_GROQ_MAX_PREVIEW]

    prompt = (
        "Classify this job application email. Reply ONLY with JSON, no extra text.\n"
        "Email:\n" + preview + "\n\n"
        "JSON format:\n"
        '{"is_job_email":true/false,'
        '"classification":"application_sent"|"rejected"|"moving_forward"|"interview"|"oa"|"offer"|"unknown",'
        '"company":"<real company name or empty>",'
        '"stage":"<e.g. Applied, Rejected, OA Received, Interview Scheduled, Offer Received>",'
        '"summary":"<one sentence what this means for the job seeker>"}\n\n'
        "Rules: is_job_email=false if unrelated to job applications. "
        "rejected=not moving forward. moving_forward=progressing without specifying how. "
        "Extract real company name (e.g. Google not greenhouse.io)."
    )

    payload = json.dumps({
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 150,
    }).encode("utf-8")

    hdrs = dict(GROQ_HEADERS)
    hdrs["Authorization"] = "Bearer " + api_key

    # ── Retry up to 3 times with exponential backoff on 429 ───────────
    for attempt in range(3):
        req = urllib.request.Request(
            GROQ_API_URL, data=payload, headers=hdrs, method="POST"
        )
        _GROQ_LAST_CALL = _time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            _GROQ_CONSECUTIVE_429 = 0
            raw = data["choices"][0]["message"]["content"].strip()
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            result = json.loads(raw)
            for k in ("is_job_email", "classification", "company", "stage", "summary"):
                if k not in result:
                    return None
            return result
        except urllib.error.HTTPError as e:
            if e.code == 429:
                _GROQ_CONSECUTIVE_429 += 1
                retry_after = e.headers.get("retry-after", None)
                wait = float(retry_after) if retry_after else (5 * (2 ** attempt))
                print(f"[Groq] 429 rate limit (attempt {attempt+1}/3), waiting {wait:.0f}s…")
                _time.sleep(wait)
                continue
            print(f"[Groq] HTTP {e.code}: {e.reason}")
            return None
        except urllib.error.URLError as e:
            print(f"[Groq] Network error: {e.reason}")
            return None
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[Groq] Parse error: {e}")
            return None
        except Exception as e:
            print(f"[Groq] Unexpected error: {e}")
            return None

    print("[Groq] Gave up after 3 rate-limit retries — falling back to keyword classifier.")
    return None




def test_groq_connection():
    """
    Quick test — call this to verify the API key works.
    Returns (ok: bool, message: str)
    """
    key = _get_groq_key()
    if not key:
        return False, "No Groq API key set. Add it in ⚙ Settings."
    if not key.startswith("gsk_"):
        return False, f"Key doesn't look right (should start with gsk_). Got: {key[:8]}..."

    payload = json.dumps({
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": "Reply with the word OK and nothing else."}],
        "temperature": 0.0,
        "max_tokens": 5,
    }).encode("utf-8")

    headers = dict(GROQ_HEADERS)
    headers["Authorization"] = "Bearer " + key

    req = urllib.request.Request(
        GROQ_API_URL,
        data=payload,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        reply = data["choices"][0]["message"]["content"].strip()
        return True, f"Groq connected ✅  Model replied: \"{reply}\""
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="ignore")[:200]
        return False, f"HTTP {e.code} — {body_text}"
    except urllib.error.URLError as e:
        return False, f"Network error: {e.reason}"
    except Exception as e:
        return False, f"Unexpected error: {e}"



# ──────────────────────────────────────────────────────────────────────────────
#  KEYWORD BANKS
# ──────────────────────────────────────────────────────────────────────────────

APPLICATION_SENT = [
    # Standard confirmations
    "thank you for applying", "thanks for applying",
    "thank you for your application", "thanks for your application",
    "application received", "we received your application",
    "application submitted", "your application has been submitted",
    "we have received your application", "application confirmation",
    "successfully applied", "successfully submitted your application",
    "your application has been received",
    # Interest / CV sent
    "thank you for your interest", "thanks for your interest",
    "your resume has been received", "your cv has been received",
    "your cv was sent", "your cv has been sent",
    "your application was sent", "your application has been sent",
    # Review / waiting
    "we'll be in touch", "we will be in touch",
    "application is under review", "we will review your application",
    "we will be reviewing your application",
    "we are reviewing your application",
    "your application is being reviewed",
    # Invitation / prompt to apply
    "time to apply for the", "apply for the role", "apply for this role",
    "application for the role", "applied to", "you applied for",
    # Courtesy acknowledgements
    "thank you for taking the time", "thank you for taking your time",
    "thank you for your time",
]

REJECTION = [
    "unfortunately", "we regret to inform", "we regret that",
    "not moving forward", "we will not be moving", "will not be proceeding",
    "not selected", "not a fit", "not the right fit",
    "decided to move forward with other candidates",
    "move forward with other candidates",
    "moving forward with other candidates",
    "proceed with other candidates",
    "proceeding with other candidates",
    "with other candidate",          # catches "with other candidate" and "with other candidates"
    "with other candidates",
    "decided to pursue other candidates", "pursue other applicants",
    "mover forward with other",
    "moving forward with other",
    "move forward with other",
    "position has been filled", "no longer considering your application",
    "not be proceeding with your application",
    "other candidates whose experience more closely",
    "we have decided not to proceed", "we won't be moving forward",
    "not shortlisted", "unsuccessful in your application",
    "we are unable to offer", "we cannot offer you",
    "your application was not successful",
    "after careful consideration",
    "after careful review",
    "we have decided to move in a different direction",
    "we will not be moving forward with your application",
    "we have chosen to move forward with another candidate",
    "we are moving forward with other applicants",
    "chosen another candidate", "selected another candidate",
    "gone with another candidate",
]

ACCEPTANCE_NEXT_STEP = [
    "pleased to inform", "excited to inform", "happy to inform",
    "delighted to offer", "offer of employment", "job offer",
    "we would like to offer", "we are pleased to offer",
    "congratulations", "moving you forward", "moving forward with you",
    "selected for the next", "progressing to the next",
    "next round", "next stage", "next step",
]

INTERVIEW_KEYWORDS = [
    "interview invitation", "schedule an interview", "schedule your interview",
    "would like to invite you for an interview", "invite you to interview",
    "interview slot", "interview time", "please confirm your availability",
    "technical interview", "hr interview", "panel interview",
    "video interview", "phone interview", "virtual interview",
    "hiring manager", "recruiter call", "screening call",
    "zoom link", "teams link", "google meet link",
    "calendar invite", "calendly",
]

# OA / Assessment — very broad to catch all variants
OA_KEYWORDS = [
    "online assessment", "online test", "online evaluation",
    "coding challenge", "coding test", "coding assessment",
    "technical assessment", "technical test", "technical challenge",
    "take-home assignment", "take-home test", "take home test",
    "preliminary test", "preliminary assessment",
    "aptitude test", "aptitude assessment",
    "psychometric test", "cognitive assessment",
    "complete the following assessment", "complete the assessment",
    "complete the test", "please complete the",
    "skill assessment", "skills test",
    "hackerrank", "codility", "hirevue", "mettl",
    "mercer | mettl", "shl assessment", "shl online",
    "testgorilla", "indeed assessments", "pymetrics",
    "codesignal", "coderbyte", "criteria corp",
    "assessments.hirevue", "app.codesignal",
    "link to the test", "link to the assessment",
    "assessment link", "test link",
    "you have been invited to", "invited to complete",
    "please use the following link",
]

REFERRAL_KEYWORDS = [
    "referred by", "referred you", "referral",
    "recommended you", "recommended by",
    "your referral", "internal referral",
    "employee referral", "referred through",
    "referred via", "mentioned your name",
    "put you forward", "passed along your details",
    "spoke highly of you",
]

# ──────────────────────────────────────────────────────────────────────────────
#  KNOWN OA PLATFORMS (for logo display / labelling)
# ──────────────────────────────────────────────────────────────────────────────

OA_PLATFORM_PATTERNS = {
    "HackerRank":   [r"hackerrank\.com", r"hackerrank"],
    "Codility":     [r"codility\.com", r"codility"],
    "HireVue":      [r"hirevue\.com", r"hirevue"],
    "Mettl":        [r"mettl\.com", r"mercer.*mettl", r"mettl"],
    "SHL":          [r"shl\.com", r"shl online", r"shlonline"],
    "TestGorilla":  [r"testgorilla\.com"],
    "CodeSignal":   [r"codesignal\.com", r"app\.codesignal"],
    "Coderbyte":    [r"coderbyte\.com"],
    "Pymetrics":    [r"pymetrics\.com"],
    "Indeed":       [r"indeed\.com/assessments", r"indeed assessments"],
    "Criteria":     [r"criteria\.com", r"criteriacorp"],
    "Vervoe":       [r"vervoe\.com"],
    "Talview":      [r"talview\.com"],
    "Karat":        [r"karat\.com"],
    "Greenhouse":   [r"greenhouse\.io"],
    "Workday":      [r"myworkday\.com"],
    "Lever":        [r"jobs\.lever\.co"],
}

MONTH_MAP = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}

# ──────────────────────────────────────────────────────────────────────────────
#  EXTRACTION HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def extract_links(text):
    """Extract all URLs from text, return list of unique URLs."""
    pattern = r'https?://[^\s\'"<>\]\[)]+(?:[^\s\'"<>\]\[).!?,;:])'
    raw = re.findall(pattern, text)
    # Clean trailing punctuation
    cleaned = []
    for url in raw:
        url = url.rstrip(".,;:!?)")
        if len(url) > 10 and url not in cleaned:
            cleaned.append(url)
    return cleaned


def classify_link(url):
    """Categorise a URL as assessment / interview / job / other."""
    url_lower = url.lower()
    for platform, patterns in OA_PLATFORM_PATTERNS.items():
        for p in patterns:
            if re.search(p, url_lower):
                return ("assessment", platform)
    interview_hosts = ["zoom.us", "teams.microsoft.com", "meet.google.com",
                       "calendly.com", "cal.com", "whereby.com", "webex.com"]
    for host in interview_hosts:
        if host in url_lower:
            return ("interview", host.split(".")[0].title())
    job_hosts = ["greenhouse.io", "lever.co", "workday.com", "taleo.net",
                 "jobs.smartrecruiters.com", "linkedin.com/jobs", "indeed.com/viewjob"]
    for host in job_hosts:
        if host in url_lower:
            return ("job_portal", host.split(".")[0].title())
    return ("other", "")


def extract_dates_from_text(text):
    """
    Extract dates from text. Returns list of dicts:
      { 'date': 'dd-mm-yyyy', 'context': '...surrounding text...' }
    """
    found = []
    text_lower = text.lower()

    # Helper: search around match for context
    def get_context(match_start, window=60):
        start = max(0, match_start - window)
        end = min(len(text), match_start + window)
        return text[start:end].replace("\n", " ").strip()

    # Pattern 1: numeric  dd/mm/yyyy  dd-mm-yyyy  dd.mm.yyyy
    for m in re.finditer(r'\b(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2,4})\b', text_lower):
        try:
            a, b, c = m.groups()
            year = int(c) if len(str(c)) == 4 else 2000 + int(c)
            day, mon = int(a), int(b)
            if mon > 12:
                day, mon = mon, day  # swap if month > 12
            dt = datetime(year, mon, day)
            found.append({"date": dt.strftime("%d-%m-%Y"), "context": get_context(m.start())})
        except ValueError:
            pass

    # Pattern 2: yyyy-mm-dd (ISO)
    for m in re.finditer(r'\b(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})\b', text_lower):
        try:
            y, mo, d = m.groups()
            dt = datetime(int(y), int(mo), int(d))
            found.append({"date": dt.strftime("%d-%m-%Y"), "context": get_context(m.start())})
        except ValueError:
            pass

    # Pattern 3: "12 January 2025"  "12th January, 2025"
    for m in re.finditer(
        r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s,]+(\d{4})\b',
        text_lower
    ):
        try:
            day, mon_str, year = m.groups()
            mon = MONTH_MAP[mon_str[:3]]
            dt = datetime(int(year), int(mon), int(day))
            found.append({"date": dt.strftime("%d-%m-%Y"), "context": get_context(m.start())})
        except (ValueError, KeyError):
            pass

    # Pattern 4: "January 12, 2025"  "January 12th 2025"
    for m in re.finditer(
        r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})(?:st|nd|rd|th)?[\s,]+(\d{4})\b',
        text_lower
    ):
        try:
            mon_str, day, year = m.groups()
            mon = MONTH_MAP[mon_str[:3]]
            dt = datetime(int(year), int(mon), int(day))
            found.append({"date": dt.strftime("%d-%m-%Y"), "context": get_context(m.start())})
        except (ValueError, KeyError):
            pass

    # Deduplicate by date value, keep first occurrence
    seen = set()
    deduped = []
    for item in found:
        if item["date"] not in seen:
            seen.add(item["date"])
            deduped.append(item)

    # Filter: only dates within ±90 days from today (skip old irrelevant dates)
    now = datetime.now()
    relevant = []
    for item in deduped:
        try:
            dt = datetime.strptime(item["date"], "%d-%m-%Y")
            if dt >= now - timedelta(days=90):
                relevant.append(item)
        except ValueError:
            pass

    return relevant


def extract_oa_duration(text):
    """Extract time duration for OA e.g. '90 minutes', '2 hours'."""
    patterns = [
        r'(\d+)\s*(?:minute|min)s?',
        r'(\d+)\s*(?:hour|hr)s?',
        r'(\d+)\s*(?:hour|hr)s?\s*(?:and\s*)?(\d+)\s*(?:minute|min)s?',
    ]
    text_lower = text.lower()
    for p in patterns:
        m = re.search(p, text_lower)
        if m:
            return m.group(0).strip()
    return ""


def detect_oa_platform(text):
    """Return platform name if a known OA platform is mentioned."""
    text_lower = text.lower()
    for platform, patterns in OA_PLATFORM_PATTERNS.items():
        for p in patterns:
            if re.search(p, text_lower):
                return platform
    return ""


def extract_referral_person(text):
    """Try to extract who referred the candidate."""
    patterns = [
        r"referred by ([A-Z][a-z]+(?: [A-Z][a-z]+)?)",
        r"referred you[,\s]+([A-Z][a-z]+(?: [A-Z][a-z]+)?)",
        r"recommended by ([A-Z][a-z]+(?: [A-Z][a-z]+)?)",
        r"([A-Z][a-z]+(?: [A-Z][a-z]+)?)\s+referred you",
        r"([A-Z][a-z]+(?: [A-Z][a-z]+)?)\s+(?:has\s+)?recommended you",
        r"on behalf of ([A-Z][a-z]+(?: [A-Z][a-z]+)?)",
        r"passed on your (?:details|cv|resume).*?([A-Z][a-z]+(?: [A-Z][a-z]+)?)",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            name = m.group(1).strip()
            if len(name) > 2:
                return name
    return ""


def keyword_check(text, keywords):
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


# ──────────────────────────────────────────────────────────────────────────────
#  MAIN CLASSIFIER
# ──────────────────────────────────────────────────────────────────────────────

def classify_email(subject, body):
    """
    Full classification of an email.
    Returns dict:
      type, stage, important_dates (str), 
      oa_platform, oa_link, oa_deadline, oa_duration, oa_details,
      interview_link, interview_date, interview_details,
      referred_by, referral_date,
      all_links (list), all_dates (list of dicts), raw_details
    """
    combined = subject + "\n" + body
    combined_lower = combined.lower()

    result = {
        "type": "unknown",
        "stage": None,
        "important_dates": "",
        "oa_platform": "",
        "oa_link": "",
        "oa_deadline": "",
        "oa_duration": "",
        "oa_details": "",
        "interview_link": "",
        "interview_date": "",
        "interview_details": "",
        "referred_by": "",
        "referral_date": "",
        "all_links": [],
        "all_dates": [],
        "raw_details": "",
    }

    # --- Extract all links ---
    all_links = extract_links(combined)
    result["all_links"] = all_links

    # Categorise links
    assessment_links = []
    interview_links = []
    for link in all_links:
        kind, platform = classify_link(link)
        if kind == "assessment":
            assessment_links.append((link, platform))
        elif kind == "interview":
            interview_links.append((link, platform))

    # --- Extract all dates ---
    all_dates = extract_dates_from_text(combined)
    result["all_dates"] = all_dates
    date_strings = [d["date"] for d in all_dates]
    result["important_dates"] = ", ".join(date_strings)

    # --- Referral detection ---
    if keyword_check(combined, REFERRAL_KEYWORDS):
        result["type"] = "referral"
        result["stage"] = "Referred"
        referred = extract_referral_person(combined)
        result["referred_by"] = referred
        if date_strings:
            result["referral_date"] = date_strings[0]

    # --- OA / Assessment detection (check before acceptance to avoid misclassification) ---
    if keyword_check(combined, OA_KEYWORDS):
        result["type"] = "oa"
        result["stage"] = "OA Received"

        platform = detect_oa_platform(combined)
        result["oa_platform"] = platform

        if assessment_links:
            result["oa_link"] = assessment_links[0][0]
            if not platform:
                result["oa_platform"] = assessment_links[0][1]
        elif all_links:
            # Pick the most likely assessment link (non-unsubscribe, non-social)
            skip_patterns = ["unsubscribe", "linkedin", "twitter", "facebook",
                             "instagram", "privacy", "terms", "help", "support"]
            for lnk in all_links:
                if not any(s in lnk.lower() for s in skip_patterns):
                    result["oa_link"] = lnk
                    break

        duration = extract_oa_duration(combined)
        result["oa_duration"] = duration

        # OA deadline = first date found
        if date_strings:
            result["oa_deadline"] = date_strings[0]

        # Build human-readable OA details summary
        details_parts = []
        if platform:
            details_parts.append(f"Platform: {platform}")
        if duration:
            details_parts.append(f"Duration: {duration}")
        if date_strings:
            details_parts.append(f"Deadline/Date: {date_strings[0]}")

        # Try to extract assessment purpose/description (first sentence mentioning test)
        purpose_patterns = [
            r'(?:complete|take|finish|submit)\s+(?:the\s+)?(?:following\s+)?([^.]{10,120}(?:test|assessment|challenge|task|assignment)[^.]{0,80})\.',
            r'(?:assessment|test|challenge)\s+(?:covers?|includes?|focuses?|tests?)\s+([^.]{10,150})\.',
            r'(?:you will be|you\'ll be)\s+(?:asked|required|expected)\s+([^.]{10,150})\.',
        ]
        for p in purpose_patterns:
            m = re.search(p, combined, re.IGNORECASE)
            if m:
                details_parts.append(f"Details: {m.group(0).strip()[:200]}")
                break

        result["oa_details"] = " | ".join(details_parts)
        result["raw_details"] = body[:1000]

    # --- Interview detection ---
    if keyword_check(combined, INTERVIEW_KEYWORDS):
        if result["type"] not in ("oa", "referral"):
            result["type"] = "interview"

        # Determine interview stage
        if any(k in combined_lower for k in ["final interview", "last round", "final round"]):
            result["stage"] = "Stage 3 - Final Interview"
        elif any(k in combined_lower for k in ["second interview", "2nd interview", "second round", "2nd round"]):
            result["stage"] = "Stage 2 - Interview"
        elif any(k in combined_lower for k in ["hr interview", "hr screen", "hr call", "recruiter call"]):
            result["stage"] = "Stage 2 - HR Interview"
        else:
            result["stage"] = "Stage 1 - Interview"

        if interview_links:
            result["interview_link"] = interview_links[0][0]
        elif all_links and not result["oa_link"]:
            for lnk in all_links:
                if not any(s in lnk.lower() for s in ["unsubscribe", "linkedin.com/in/",
                                                        "twitter", "facebook", "privacy"]):
                    result["interview_link"] = lnk
                    break

        if date_strings:
            result["interview_date"] = date_strings[0]

        # Interview details summary
        int_details = []
        if result["stage"]:
            int_details.append(result["stage"])
        if date_strings:
            int_details.append(f"Date: {date_strings[0]}")
        if result["interview_link"]:
            int_details.append(f"Link: {result['interview_link']}")
        result["interview_details"] = " | ".join(int_details)

    # --- Rejection ---
    # Be careful: "unfortunately" alone can be a false positive.
    # Require at least one strong rejection signal OR multiple weak ones.
    rejection_hits = [kw for kw in REJECTION if kw in combined_lower]
    is_rejection = False
    if len(rejection_hits) >= 2:
        is_rejection = True
    elif len(rejection_hits) == 1:
        # Single hit: only flag as rejection if it's a strong/unambiguous phrase
        strong_rejection = [
            "not moving forward", "we will not be moving", "will not be proceeding",
            "not selected", "decided to move forward with other candidates",
            "move forward with other candidates", "moving forward with other candidates",
            "proceed with other candidates", "proceeding with other candidates",
            "decided to pursue other candidates", "pursue other applicants",
            "mover forward with other", "position has been filled",
            "no longer considering your application",
            "not be proceeding with your application",
            "we have decided not to proceed", "we won't be moving forward",
            "not shortlisted", "unsuccessful in your application",
            "we are unable to offer", "we cannot offer you",
            "your application was not successful",
            "we will not be moving forward with your application",
            "we have chosen to move forward with another candidate",
            "we are moving forward with other applicants",
        ]
        if rejection_hits[0] in strong_rejection:
            is_rejection = True

    if is_rejection:
        result["type"] = "rejected"
        result["stage"] = "Rejected"
        return result  # Rejection overrides everything

    # --- Offer ---
    if keyword_check(combined, ACCEPTANCE_NEXT_STEP):
        if "offer" in combined_lower or "pleased to offer" in combined_lower:
            result["type"] = "offer"
            result["stage"] = "Offer Received"
        elif result["type"] == "unknown":
            result["type"] = "accepted"
            result["stage"] = "Moving Forward"

    # --- Application sent confirmation ---
    if result["type"] == "unknown" and keyword_check(combined, APPLICATION_SENT):
        result["type"] = "application_sent"
        result["stage"] = "Applied - Waiting"

    # If we already have a known type but no stage set, assign a sensible default
    if result["type"] == "application_sent" and not result["stage"]:
        result["stage"] = "Applied - Waiting"

    return result


def extract_company_from_email(sender_full, subject, body):
    """
    Extract company name from the full 'From' header, domain, subject, or body.

    sender_full is the raw From header value, e.g.:
      'Google Careers <no-reply@google.com>'
      'jobs@barclays.com'
      'Talent Team at Amazon <recruiting@amazon.jobs>'
      'no-reply@greenhouse.io'  ← ATS, need to use subject/body
    """
    ATS_DOMAINS = {
        "greenhouse", "lever", "taleo", "jobvite", "smartrecruiters",
        "bamboohr", "icims", "myworkday", "workday", "ashby", "dover",
        "rippling", "comeet", "recruitee", "joinhandshake", "handshake",
        "hirevue", "hackerrank", "codility", "codesignal", "testgorilla",
        "mettl", "workable", "jazz", "breezy", "manatal", "pinpoint",
        "recruiting", "careers", "jobs", "apply", "notifications",
        "noreply", "no-reply", "donotreply",
        "gmail", "yahoo", "outlook", "hotmail", "live", "icloud",
        "mail", "email", "support", "hello", "info", "contact",
        "talentreef", "successfactors", "oracle", "sap", "cornerstoneondemand",
        "kenexa", "silkroad", "lumesse", "brassring", "peoplefluent",
    }

    # Words that alone are not a company name
    NOISE_WORDS = {
        "careers", "career", "talent", "team", "recruiting", "recruitment",
        "hr", "human", "resources", "jobs", "hiring", "apply", "noreply",
        "no", "reply", "do", "not", "notifications", "alerts", "the",
        "group", "limited", "inc", "llc", "ltd", "plc",
    }

    # Prefixes to strip from display names
    STRIP_PREFIX = re.compile(
        r'^(?:careers?\s+(?:at|@|for|with)\s+|'
        r'talent\s+(?:team\s+)?(?:at|@|for|with)?\s*|'
        r'recruiting\s+(?:at|@|for|with)?\s*|'
        r'jobs?\s+(?:at|@|for|with)\s+|'
        r'hr\s+(?:at|@|for|with)\s+|'
        r'hiring\s+(?:at|@|for|with)\s+|'
        r'from\s+(?:the\s+)?|'
        r'on\s+behalf\s+of\s+|'
        r'the\s+)',
        re.IGNORECASE
    )

    # Suffixes to strip from display names
    STRIP_SUFFIX = re.compile(
        r'[\s,.\-–|]*(careers?|talent|team|recruiting|recruitment|'
        r'hr|jobs?|hiring|notifications?|alerts?|no[\-\s]?reply|'
        r'do[\-\s]not[\-\s]reply)\s*$',
        re.IGNORECASE
    )

    def clean_candidate(name):
        name = STRIP_PREFIX.sub("", name).strip()
        name = STRIP_SUFFIX.sub("", name).strip(" -–|,.")
        # Remove any remaining noise-only words
        words = name.split()
        meaningful = [w for w in words if w.lower() not in NOISE_WORDS]
        result = " ".join(meaningful).strip()
        return result if 1 < len(result) < 55 else ""

    company = ""

    # ── Step 1: Display name from "Display Name <email>" ─────────────────────
    display_match = re.match(r'^"?([^"<\n]+?)"?\s*<', sender_full.strip())
    if display_match:
        raw_display = display_match.group(1).strip()
        candidate = clean_candidate(raw_display)
        if candidate and candidate.lower() not in NOISE_WORDS:
            company = candidate

    # ── Step 2: Check if display name IS the email (no angle brackets) ────────
    # e.g. sender_full = "jobs@barclays.com"
    if not company and "<" not in sender_full:
        # bare email address — extract domain
        pass  # falls through to Step 3

    # ── Step 3: Email domain (skip ATS/generic domains) ──────────────────────
    if not company:
        domain_m = re.search(r"@([\w\-]+(?:\.[\w\-]+)*)", sender_full.lower())
        if domain_m:
            full_domain = domain_m.group(1)
            parts = full_domain.split(".")
            # Walk left-to-right, skip TLD and ATS parts
            for part in parts[:-1]:
                if part not in ATS_DOMAINS and len(part) > 2:
                    # Convert hyphenated domain parts e.g. "jp-morgan" → "Jp Morgan"
                    company = part.replace("-", " ").title()
                    break

    # ── Step 4: Subject line patterns ────────────────────────────────────────
    if not company or company.lower() in ("unknown", "unknown company"):
        subject_pats = [
            r"(?:application|applying|role|position|opportunity)\s+(?:at|to|with|@)\s+([\w\s&\-\.]+?)(?:\s*[-–|,\(]|$)",
            r"(?:your|re:|fw:)\s+[\w\s\-/]+?\s+(?:application|role)\s+(?:at|with|to)\s+([\w\s&\-\.]+?)(?:\s*[-–|,]|$)",
            r"^([\w\s&\-\.]+?)\s*[-–|:]\s*(?:application|job|role|position|opportunity)",
            r"(?:welcome to|thank you for applying to|thanks for applying to)\s+([\w\s&\-\.]+?)(?:\s*[!,\.]|$)",
            r"(?:from|by)\s+([\w\s&\-\.]+?)\s+(?:talent|hr|team|recruiting)",
        ]
        for p in subject_pats:
            m = re.search(p, subject, re.IGNORECASE)
            if m:
                candidate = clean_candidate(m.group(1).strip())
                if candidate and 2 < len(candidate) < 55:
                    company = candidate
                    break

    # ── Step 5: First 400 chars of body ──────────────────────────────────────
    if not company or company.lower() in ("unknown", "unknown company"):
        body_pats = [
            r"(?:application|applying|applied)\s+(?:at|to|with|for a role at|for a position at)\s+([\w\s&\-\.]+?)(?:\s*[,.\n!]|$)",
            r"(?:welcome to|you applied to|thank you for applying to|thanks for applying to)\s+([\w\s&\-\.]+?)(?:\s*[!,.\n]|$)",
            r"(?:the\s+)?(?:hiring|recruitment|talent)\s+team\s+(?:at|@|from)\s+([\w\s&\-\.]+?)(?:\s*[,.\n]|$)",
            r"(?:from|regards|sincerely)[,\s]+(?:the\s+)?(?:[\w\s]+?\s+)?(?:team|hr)\s+(?:at|@|from)\s+([\w\s&\-\.]+?)(?:\s*[,.\n]|$)",
        ]
        for p in body_pats:
            m = re.search(p, body[:600], re.IGNORECASE)
            if m:
                candidate = clean_candidate(m.group(1).strip())
                if candidate and 2 < len(candidate) < 55:
                    company = candidate
                    break

    return company or "Unknown Company"



def extract_role_from_subject(subject):
    """Pull job role from email subject."""
    patterns = [
        r"(?:application|applying|position|role|job|opportunity)\s+(?:for|as|:|-)?\s*[\"']?([\w\s\-/&,]+?)[\"']?\s*(?:at|\bat\b|$|[-–|]|\()",
        r"(?:your|re:)\s+([\w\s\-/]+?)\s+(?:application|role)",
        r"((?:senior\s+|junior\s+|lead\s+|principal\s+|staff\s+)?(?:software|data|product|frontend|backend|fullstack|full.stack|devops|cloud|ml|ai|machine\s+learning|deep\s+learning|business|marketing|sales|finance|operations|hr|human\s+resources|ux|ui|design|research|analyst|engineer|developer|scientist|manager|director|architect|consultant|associate|intern|graduate)[^\n\-|,]{0,60})",
    ]
    for p in patterns:
        m = re.search(p, subject, re.IGNORECASE)
        if m:
            role = m.group(1).strip()
            if 3 < len(role) < 90:
                return role.title()
    return "Unknown Role"


def gmail_message_url(message_id: str, account_email: str = "") -> str:
    """
    Build a direct Gmail web URL for a specific message.
    Opens the exact email in the browser.
    account_email is used to pick the right Google account slot (u/0, u/1, etc.)
    — we default to u/0 since we can't know the slot without extra lookup.
    """
    if not message_id:
        return ""
    # Gmail URL format: https://mail.google.com/mail/u/0/#all/<message_id>
    return f"https://mail.google.com/mail/u/0/#all/{message_id}"


    """Pull job role from email subject."""
    patterns = [
        r"(?:application|applying|position|role|job|opportunity)\s+(?:for|as|:|-)?\s*[\"']?([\w\s\-/&,]+?)[\"']?\s*(?:at|\bat\b|$|[-–|]|\()",
        r"(?:your|re:)\s+([\w\s\-/]+?)\s+(?:application|role)",
        r"((?:senior\s+|junior\s+|lead\s+|principal\s+|staff\s+)?(?:software|data|product|frontend|backend|fullstack|full.stack|devops|cloud|ml|ai|machine\s+learning|deep\s+learning|business|marketing|sales|finance|operations|hr|human\s+resources|ux|ui|design|research|analyst|engineer|developer|scientist|manager|director|architect|consultant|associate|intern|graduate)[^\n\-|,]{0,60})",
    ]
    for p in patterns:
        m = re.search(p, subject, re.IGNORECASE)
        if m:
            role = m.group(1).strip()
            if 3 < len(role) < 90:
                return role.title()
    return "Unknown Role"


# ──────────────────────────────────────────────────────────────────────────────
#  AUTH & GMAIL API
# ──────────────────────────────────────────────────────────────────────────────

def get_token_path(account_email):
    safe = account_email.replace("@", "_at_").replace(".", "_")
    return os.path.join(TOKEN_DIR, f"token_{safe}.json")


def get_credentials(account_email, credentials_path):
    if not GOOGLE_LIBS_AVAILABLE:
        raise ImportError(
            "Google libraries not installed.\n"
            "Run: pip install google-auth google-auth-oauthlib "
            "google-auth-httplib2 google-api-python-client"
        )
    token_path = get_token_path(account_email)
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
    return creds


def get_email_body(payload):
    """Recursively extract plain-text body from Gmail message payload."""
    body = ""
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                data = part["body"].get("data", "")
                if data:
                    body += base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            elif "parts" in part:
                body += get_email_body(part)
    else:
        data = payload.get("body", {}).get("data", "")
        if data:
            body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    return body


# ──────────────────────────────────────────────────────────────────────────────
#  MAIN SCAN FUNCTION
# ──────────────────────────────────────────────────────────────────────────────

def scan_account(account_email, credentials_path, days_back=7, progress_callback=None):
    """
    Scan one Gmail account.
    Returns (new_applications, updates_found).
    """
    if not GOOGLE_LIBS_AVAILABLE:
        raise ImportError("Google libraries not installed.")

    creds = get_credentials(account_email, credentials_path)
    service = build("gmail", "v1", credentials=creds)

    new_apps = 0
    updates = 0
    emails_scanned = 0
    seen_msg_ids = set()

    after_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y/%m/%d")

    search_queries = [
        f"subject:(application OR applied OR interview OR assessment OR offer OR rejected OR hiring OR recruiter OR referral OR referred OR test OR challenge OR \"thank you\") after:{after_date}",
        f"from:(noreply OR no-reply OR careers OR jobs OR recruiting OR hr OR talent OR assessment OR test) after:{after_date}",
        f"(hackerrank OR codility OR hirevue OR mettl OR codesignal OR testgorilla OR coderbyte) after:{after_date}",
        f"(\"your cv was sent\" OR \"your application was sent\" OR \"thank you for your interest\" OR \"we will review your application\" OR \"time to apply\" OR \"thank you for applying\" OR \"thank you for your application\") after:{after_date}",
        f"(\"proceed with other candidates\" OR \"moving forward with other\" OR \"unfortunately\" OR \"thank you for taking\" OR \"thank you for your time\") after:{after_date}",
    ]

    for query in search_queries:
        try:
            results = service.users().messages().list(
                userId="me", q=query, maxResults=150
            ).execute()
        except Exception as e:
            if progress_callback:
                progress_callback(f"Query failed: {str(e)[:60]}")
            continue

        messages = results.get("messages", [])
        for msg_ref in messages:
            msg_id = msg_ref["id"]
            if msg_id in seen_msg_ids:
                continue
            seen_msg_ids.add(msg_id)
            emails_scanned += 1

            if progress_callback:
                progress_callback(f"Reading email {emails_scanned}…")

            try:
                msg = service.users().messages().get(
                    userId="me", id=msg_id, format="full"
                ).execute()
            except Exception:
                continue

            headers = {h["name"].lower(): h["value"]
                       for h in msg["payload"].get("headers", [])}
            subject  = headers.get("subject", "")
            sender   = headers.get("from", "")
            thread_id = msg.get("threadId", "")
            snippet  = msg.get("snippet", "")

            body = get_email_body(msg["payload"])

            sender_email_m = re.search(r"<(.+?)>", sender)
            sender_email   = sender_email_m.group(1) if sender_email_m else sender

            internal_date = int(msg.get("internalDate", 0)) / 1000
            email_date = (datetime.fromtimestamp(internal_date).strftime("%d-%m-%Y")
                          if internal_date else datetime.now().strftime("%d-%m-%Y"))

            # ── Rule-based classification ───────────────────────────────
            clf = classify_email(subject, body)

            # ── LLM classification (Groq, free tier) — enhances/overrides rules ──
            llm = llm_classify(subject, body)
            if llm and llm.get("is_job_email") is False:
                # LLM says this is NOT a job email — skip entirely
                continue

            if llm:
                # Map LLM classification to our internal type/stage
                llm_type_map = {
                    "application_sent": "application_sent",
                    "rejected":         "rejected",
                    "moving_forward":   "accepted",
                    "interview":        "interview",
                    "oa":               "oa",
                    "offer":            "offer",
                }
                llm_stage_map = {
                    "application_sent": "Applied - Waiting",
                    "rejected":         "Rejected",
                    "moving_forward":   "Moving Forward",
                    "interview":        clf["stage"] or "Stage 1 - Interview",
                    "oa":               "OA Received",
                    "offer":            "Offer Received",
                }
                llm_cls = llm.get("classification", "unknown")
                if llm_cls != "unknown":
                    clf["type"]  = llm_type_map.get(llm_cls, clf["type"])
                    clf["stage"] = llm.get("stage") or llm_stage_map.get(llm_cls, clf["stage"])
                # Append LLM summary to raw_details
                if llm.get("summary"):
                    clf["raw_details"] = f"[AI] {llm['summary']}\n\n" + clf.get("raw_details", "")
                if progress_callback and llm_cls != "unknown":
                    progress_callback(f"  → LLM: {llm_cls} | {llm.get('company','')}")

            # Serialise links for storage
            links_str = "\n".join(clf["all_links"][:10])
            dates_str = ", ".join([d["date"] for d in clf["all_dates"]])

            # ── Company name: LLM first, then header/domain/body ───────
            llm_company = (llm or {}).get("company", "").strip()
            # Pass full 'sender' header (display name + email) for best extraction
            company_from_header = extract_company_from_email(sender, subject, body)
            # Prefer LLM result if it looks like a real name (not empty/unknown)
            resolved_company = (
                llm_company if llm_company and llm_company.lower() not in ("", "unknown", "unknown company")
                else company_from_header
            )

            existing_job_id = db.thread_id_exists(thread_id)

            if existing_job_id:
                # ── Update existing record ──────────────────────────────
                status_map = {
                    "rejected":          "Rejected",
                    "offer":             "Offer Received",
                    "accepted":          "In Progress",
                    "oa":                "In Progress",
                    "interview":         "In Progress",
                    "application_sent":  "Applied",
                    "referral":          "Applied",
                    "moving_forward":    "In Progress",
                }
                stage_map = {
                    "rejected":         "Rejected",
                    "offer":            "Offer Received",
                    "accepted":         "Moving Forward",
                    "application_sent": "Applied - Waiting",
                }
                new_status = status_map.get(clf["type"])
                new_stage  = clf["stage"] or stage_map.get(clf["type"])

                db.update_job_status(
                    existing_job_id,
                    status=new_status,
                    stage=new_stage,
                    important_dates=clf["important_dates"] or None,
                    oa_platform=clf["oa_platform"] or None,
                    oa_link=clf["oa_link"] or None,
                    oa_deadline=clf["oa_deadline"] or None,
                    oa_duration=clf["oa_duration"] or None,
                    oa_details=clf["oa_details"] or None,
                    interview_link=clf["interview_link"] or None,
                    interview_date=clf["interview_date"] or None,
                    interview_details=clf["interview_details"] or None,
                    referred_by=clf["referred_by"] or None,
                    referral_date=clf["referral_date"] or None,
                )
                db.add_email_event(
                    existing_job_id,
                    event_type=clf["type"],
                    subject=subject,
                    snippet=snippet[:400],
                    message_id=msg_id,
                    event_date=email_date,
                    extracted_links=links_str,
                    extracted_dates=dates_str,
                    raw_details=clf["raw_details"][:800],
                    sender_full=sender,
                    body_text=body[:8000],
                )
                updates += 1

            elif clf["type"] in ("application_sent", "referral"):
                # ── New application ─────────────────────────────────────
                role = extract_role_from_subject(subject)
                job_id = db.add_job(
                    company=resolved_company,
                    role=role,
                    gmail_account=account_email,
                    applied_date=email_date,
                    thread_id=thread_id,
                    email_subject=subject,
                    referred_by=clf["referred_by"],
                    referral_date=clf["referral_date"],
                )
                db.add_email_event(
                    job_id,
                    event_type=clf["type"],
                    subject=subject,
                    snippet=snippet[:400],
                    message_id=msg_id,
                    event_date=email_date,
                    extracted_links=links_str,
                    extracted_dates=dates_str,
                    raw_details=clf["raw_details"][:800],
                    sender_full=sender,
                    body_text=body[:8000],
                )
                if clf["important_dates"]:
                    db.update_job_status(job_id, important_dates=clf["important_dates"])
                new_apps += 1

            elif clf["type"] in ("oa", "interview", "offer", "accepted"):
                # ── Unmatched OA / interview / offer / moving forward — create new entry ──
                role = extract_role_from_subject(subject)

                job_id = db.add_job(
                    company=resolved_company,
                    role=role,
                    gmail_account=account_email,
                    applied_date=email_date,
                    thread_id=thread_id,
                    email_subject=subject,
                )
                db.update_job_status(
                    job_id,
                    stage=clf["stage"],
                    status="In Progress" if clf["type"] not in ("offer",) else "Offer Received",
                    important_dates=clf["important_dates"] or None,
                    oa_platform=clf["oa_platform"] or None,
                    oa_link=clf["oa_link"] or None,
                    oa_deadline=clf["oa_deadline"] or None,
                    oa_duration=clf["oa_duration"] or None,
                    oa_details=clf["oa_details"] or None,
                    interview_link=clf["interview_link"] or None,
                    interview_date=clf["interview_date"] or None,
                    interview_details=clf["interview_details"] or None,
                )
                db.add_email_event(
                    job_id,
                    event_type=clf["type"],
                    subject=subject,
                    snippet=snippet[:400],
                    message_id=msg_id,
                    event_date=email_date,
                    extracted_links=links_str,
                    extracted_dates=dates_str,
                    raw_details=clf["raw_details"][:800],
                    sender_full=sender,
                    body_text=body[:8000],
                )
                new_apps += 1

    db.log_scan(account_email, emails_scanned, new_apps, updates)
    return new_apps, updates


def revoke_token(account_email):
    token_path = get_token_path(account_email)
    if os.path.exists(token_path):
        os.remove(token_path)
        return True
    return False
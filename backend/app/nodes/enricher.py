"""
Node 3 — Email Enricher
========================
Waterfall (free → free → paid):
  1. Check if RapidAPI Local Business Data already returned an email (free, already done)
  2. Website scrape (BeautifulSoup, completely free) — also collects WhatsApp links
  3. RapidAPI Email Finder (rapidapi.com/theCele/api/email-finder7)

A lead is kept if it can be reached at all — email, phone or WhatsApp. Many
agents (especially in Israel) list no email anywhere but answer WhatsApp, and
dropping them threw away ~80% of what Maps returned. Email leads sort first,
so the result cap never cuts one in favour of a phone-only lead.
"""
import os, re, logging, asyncio
from urllib.parse import urljoin, urlparse, unquote
import httpx
from bs4 import BeautifulSoup
from app.agents.state import LeadState
from app import cache

logger = logging.getLogger(__name__)

RAPIDAPI_KEY  = os.getenv("RAPIDAPI_KEY", "")
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,24}")
DECISION_KWS  = {"owner", "ceo", "founder", "president", "director", "manager"}
GENERIC_PFX   = {"info", "contact", "hello", "support", "admin", "noreply",
                  "no-reply", "sales", "office", "team", "enquiries"}
# Mailboxes that exist on the site but aren't where a sales pitch gets read.
NON_SALES_PFX = {"billing", "invoice", "invoices", "accounting", "jobs", "careers",
                 "hr", "privacy", "legal", "webmaster", "postmaster", "abuse"}
# A bot-looking UA gets 403s from many small-business hosts and WAFs.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Link href/text fragments (en/he/ar) that point at a page likely to list
# contact details. Contact pages are tried before about pages.
_CONTACT_HINTS = ("contact", "צור-קשר", "צור קשר", "קשר", "اتصل", "تواصل")
_ABOUT_HINTS   = ("about", "אודות", "من نحن")
_MAX_EXTRA_PAGES = 3

# Listing portals / social profiles: not the business's own site, and they
# never expose an email — scraping them only costs time.
_NO_SCRAPE_HOSTS = ("facebook.com", "instagram.com", "linkedin.com", "tiktok.com",
                    "yad2.co.il", "madlan.co.il")
# Addresses that show up in page source but don't belong to the business
# (error trackers, site builders, template placeholders).
_JUNK_EMAIL_DOMAINS = ("sentry.io", "wixpress.com", "example.com", "domain.com",
                       "email.com", "yourdomain.com")

# Country → calling code, to turn a local "05x..." WhatsApp number into the
# international form wa.me needs. Unlisted countries keep the number as found.
_CALLING_CODES = {"il": "972", "us": "1", "ca": "1", "gb": "44", "ae": "971",
                  "jo": "962", "sa": "966", "eg": "20", "ps": "970"}

# Common real TLDs — used to sanity-check / trim regex matches. Without a
# space between adjacent HTML elements, "info@site.com" followed directly
# by "Service Areas" can get glued into "info@site.comservice" — the regex
# alone can't tell "com" from "comservice" since both are just letters.
# We fix the root cause (missing separator in get_text below) AND trim any
# survivors here as a second line of defense.
_COMMON_TLDS = [
    "com", "org", "net", "info", "biz", "co", "io", "us", "edu", "gov",
    "co.il", "org.il", "net.il", "gov.il", "ac.il", "il",
    "co.uk", "org.uk", "ca", "de", "fr", "eu",
]
# longest first so "co.il" is checked before the bare "il"/"co"
_COMMON_TLDS.sort(key=len, reverse=True)


def _clean_email(raw: str) -> str | None:
    """Trim a regex-captured email down to its real TLD if extra glued
    text made it past extraction, and reject anything that still doesn't
    look like a sane domain/TLD combination."""
    raw = raw.strip().lower()
    if "@" not in raw:
        return None
    local, _, domain = raw.rpartition("@")
    if not local or not domain:
        return None

    # Try each known TLD as a suffix match, trimming anything glued after it.
    # rfind (not find) so a domain like "info.commerce.com" keeps its real
    # ending instead of being cut at the "com" inside "commerce".
    for tld in _COMMON_TLDS:
        marker = f".{tld}"
        idx = domain.rfind(marker)
        if idx != -1:
            domain = domain[: idx + len(marker)]
            return f"{local}@{domain}"

    # Unknown TLD — fall back to whatever the regex found (better to keep
    # an unusual-but-real TLD than to silently drop the lead), but reject
    # obviously excessive matches (a real TLD is never this long).
    tld_part = domain.rsplit(".", 1)[-1]
    if len(tld_part) > 24:
        return None
    return raw


# ── Layer 1: already in RapidAPI response ─────────────────────────────────────
# (handled in maps_scraper — if primary_email is already set it's kept; the
#  site scrape below then only adds a WhatsApp number)


# ── Layer 2: website scrape ───────────────────────────────────────────────────

def _whatsapp_number(href: str) -> str:
    """Digits of the number in a wa.me / api.whatsapp.com link, or ''."""
    h = unquote(href).lower()
    if "wa.me/" in h:
        digits = re.sub(r"\D", "", h.split("wa.me/", 1)[1].split("?")[0])
    elif "whatsapp" in h and "phone=" in h:
        digits = re.sub(r"\D", "", h.split("phone=", 1)[1].split("&")[0])
    else:
        return ""
    return digits if 8 <= len(digits) <= 15 else ""


def _add_email(found: dict, raw: str, landing: bool, mailto: bool) -> None:
    email = _clean_email(raw)
    if not email or email.endswith((".png", ".jpg", ".css")):
        return
    if email.split("@")[1].endswith(_JUNK_EMAIL_DOMAINS):
        return
    seen = found.setdefault(email, {"landing": False, "mailto": False})
    seen["landing"] |= landing
    seen["mailto"]  |= mailto


def _collect(soup: BeautifulSoup, out: dict, landing: bool) -> None:
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().startswith("mailto:"):
            _add_email(out["emails"], unquote(href[7:]).split("?")[0], landing, mailto=True)
        else:
            n = _whatsapp_number(href)
            if n and n not in out["whatsapp"]:
                out["whatsapp"].append(n)
    # separator=" " is critical: without it, BeautifulSoup joins
    # text from adjacent elements with NO space (e.g. a phone
    # number span right before an email span), so the email
    # regex below would otherwise capture "2105551234info@x.com"
    # or "info@x.comVisitOurOffice" as one glued string.
    for m in EMAIL_RE.finditer(soup.get_text(separator=" ")):
        _add_email(out["emails"], m.group(), landing, mailto=False)


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _contact_links(soup: BeautifulSoup, base: str) -> list[str]:
    """Same-site links that look like contact pages, then about pages."""
    contact, about = [], []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "#", "javascript:")):
            continue
        # unquote: sites link the same page both %-encoded and in Hebrew letters
        full = unquote(urljoin(base, href).split("#")[0])
        if _host(full) != _host(base) or full.rstrip("/") == unquote(base).rstrip("/"):
            continue
        hay = f"{full} {a.get_text(' ', strip=True)}".lower()
        bucket = (contact if any(k in hay for k in _CONTACT_HINTS)
                  else about if any(k in hay for k in _ABOUT_HINTS) else None)
        if bucket is not None and full not in contact and full not in about:
            bucket.append(full)
    return contact + about


async def _get_soup(c: httpx.AsyncClient, url: str) -> tuple[str, BeautifulSoup | None]:
    r = await c.get(url, headers={"User-Agent": UA})
    if r.status_code >= 400 or "text/html" not in r.headers.get("content-type", ""):
        return str(r.url), None
    # Bot-check interstitials (SiteGround answers 202 + a tiny captcha redirect page)
    if r.status_code == 202 or (len(r.text) < 3000 and "captcha" in r.text.lower()):
        return str(r.url), None
    return str(r.url), BeautifulSoup(r.text, "lxml")


async def _scrape_site(url: str) -> dict:
    """
    Emails and WhatsApp numbers from a business's site.
    Returns {"emails": {email: {"landing": bool, "mailto": bool}}, "whatsapp": [digits],
             "failed": bool}  — failed = the site itself couldn't be loaded (down,
    blocked, captcha), so the empty result shouldn't be cached.
    "landing" marks emails on the exact page Maps linked — often a branch page
    of a franchise, where the branch's own address beats the head office's.
    """
    out: dict = {"emails": {}, "whatsapp": [], "failed": False}
    if not url:
        return out
    if not url.startswith("http"):
        url = f"https://{url}"
    if _host(url).endswith(_NO_SCRAPE_HOSTS):
        return out

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
        # Maps often lists a bare http:// URL for a site that only serves https.
        other = url.replace("http://", "https://", 1) if url.startswith("http://") else None
        base, soup = url, None
        for candidate in filter(None, (url, other)):
            try:
                base, soup = await _get_soup(c, candidate)
                break
            except httpx.HTTPError:
                continue
        if soup is None:
            out["failed"] = True
            return out
        _collect(soup, out, landing=True)

        pages = _contact_links(soup, base) or [urljoin(base, "/contact"), urljoin(base, "/about")]
        for page in pages[:_MAX_EXTRA_PAGES]:
            try:
                _, s = await _get_soup(c, page)
            except httpx.HTTPError:
                continue
            if s is not None:
                _collect(s, out, landing=False)
    return out


# ── Layer 3: RapidAPI Email Finder ────────────────────────────────────────────

async def _rapidapi_email_finder(domain: str, company: str) -> list[dict]:
    """
    RapidAPI Email Finder by theCele
    https://rapidapi.com/theCele/api/email-finder7
    """
    if not RAPIDAPI_KEY or not domain:
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                "https://email-finder7.p.rapidapi.com/find",
                params={"domain": domain, "company": company},
                headers={
                    "X-RapidAPI-Key":  RAPIDAPI_KEY,
                    "X-RapidAPI-Host": "email-finder7.p.rapidapi.com",
                },
            )
            if r.status_code == 200:
                data = r.json()
                emails = data.get("emails", []) or []
                return [{"value": e if isinstance(e, str) else e.get("value",""),
                         "position": e.get("position","") if isinstance(e, dict) else "",
                         "confidence": e.get("confidence", 70) if isinstance(e, dict) else 70}
                        for e in emails if e]
    except Exception as e:
        logger.warning(f"[enricher] RapidAPI email finder failed for {domain}: {e}")
    return []


# ── Helpers ───────────────────────────────────────────────────────────────────

def _email_score(email: str, position: str = "", landing: bool = False,
                 mailto: bool = False, city: str = "") -> int:
    pfx = email.split("@")[0].lower()
    s = 50
    if any(k in pfx      for k in DECISION_KWS): s += 30
    if any(k in position.lower() for k in DECISION_KWS): s += 20
    if pfx in GENERIC_PFX: s -= 30
    if pfx in NON_SALES_PFX: s -= 40
    # A franchise branch page lists the branch's address next to the head
    # office's footer ones — prefer the branch (matches the city / the page Maps linked).
    if city and city in pfx: s += 20
    if landing: s += 10
    if mailto:  s += 5
    return max(0, min(100, s))


def _intl_whatsapp(digits: str, country: str) -> str:
    code = _CALLING_CODES.get(country, "")
    if code and digits.startswith("0"):
        return code + digits[1:]
    # Sites often write the code and keep the trunk 0: wa.me/9720501234567
    for c in set(_CALLING_CODES.values()):
        if digits.startswith(c + "0") and len(digits) > len(c) + 9:
            return c + digits[len(c) + 1:]
    return digits


def _domain(website: str) -> str:
    if not website:
        return ""
    if not website.startswith("http"):
        website = f"https://{website}"
    try:
        return urlparse(website).netloc.lstrip("www.")
    except Exception:
        return ""


async def _enrich_one(biz: dict, city: str = "", country: str = "") -> dict:
    # Demo records already have emails
    if biz.get("source") == "demo" and biz.get("primary_email"):
        return biz

    site   = biz.get("website", "")
    domain = _domain(site)
    pool: list[dict] = []

    # Layer 1: website scrape (free) — run even when RapidAPI already gave an
    # email, since it's also the only source of WhatsApp numbers.
    scraped = await _scrape_site(site) if site else {"emails": {}, "whatsapp": [], "failed": False}
    whatsapp = _intl_whatsapp(scraped["whatsapp"][0], country) if scraped["whatsapp"] else ""

    # Layer 0: already have email from RapidAPI maps response
    if biz.get("primary_email"):
        return {**biz, "whatsapp": whatsapp, "enriched": True}
    if scraped["failed"]:
        biz = {**biz, "_scrape_failed": True}

    for e, seen in scraped["emails"].items():
        pool.append({"value": e, "position": "", "confidence": 60, "src": "scrape", **seen})

    # Layer 2: RapidAPI email finder (free tier)
    if not pool and domain:
        results = await _rapidapi_email_finder(domain, biz.get("name", ""))
        for r in results:
            pool.append({**r, "src": "rapidapi_email_finder"})

    if not pool:
        return {**biz, "whatsapp": whatsapp, "enriched": bool(whatsapp)}

    scored = sorted(pool, key=lambda e: _email_score(
        e["value"], e.get("position", ""), e.get("landing", False), e.get("mailto", False), city,
    ), reverse=True)
    best   = scored[0]
    owner  = f"{best.get('first_name','')} {best.get('last_name','')}".strip()

    return {
        **biz,
        "emails":         [e["value"] for e in scored if e.get("value")],
        "primary_email":  best["value"],
        "owner_name":     owner or biz.get("owner_name", ""),
        "owner_position": best.get("position", ""),
        "whatsapp":       whatsapp,
        "enriched":       True,
    }


async def _run_all(businesses: list[dict], city: str = "", country: str = "") -> tuple[list[dict], list[str]]:
    sem = asyncio.Semaphore(10)
    errors: list[str] = []

    async def safe(b: dict) -> dict:
        async with sem:
            try:
                return await _enrich_one(b, city, country)
            except Exception as e:
                errors.append(f"{b.get('name','?')}: {e}")
                return b

    results = await asyncio.gather(*[safe(b) for b in businesses])
    return list(results), errors


def enrich_websites_node(state: LeadState) -> LeadState:
    businesses = state.get("raw_businesses", [])
    logger.info(f"[enricher] {len(businesses)} businesses to enrich")

    # "Nahariya, Israel" → "nahariya", matched against email prefixes like nahariya@brand.co.il
    city = re.sub(r"[^a-z]", "", state.get("location", "").split(",")[0].lower())
    country = state.get("country_code", "")
    # Businesses scraped within PLACE_TTL reuse their stored contacts — no site visit.
    places = cache.get_places(businesses)
    hits, todo = [], []
    for b in businesses:
        contact = cache.cached_group(places.get(cache.place_key(b)), "contact", cache.PLACE_TTL)
        (hits if contact is not None else todo).append({**b, **contact} if contact else b)

    fresh, errors = asyncio.run(_run_all(todo, city, country))
    cache.save_group([b for b in fresh if not b.pop("_scrape_failed", False)],
                     "contact", cache.CONTACT_FIELDS)
    enriched = hits + fresh
    logger.info(f"[enricher] {len(hits)} from cache, {len(fresh)} scraped")
    reachable = [b for b in enriched
                 if b.get("primary_email") or b.get("phone") or b.get("whatsapp")]
    # Email first, then WhatsApp, then phone-only — the cap below keeps the best.
    reachable.sort(key=lambda b: (not b.get("primary_email"), not b.get("whatsapp")))

    n_email = sum(1 for b in reachable if b.get("primary_email"))
    n_wa    = sum(1 for b in reachable if b.get("whatsapp"))
    logger.info(f"[enricher] {len(reachable)}/{len(enriched)} reachable — "
                f"{n_email} with email, {n_wa} with WhatsApp")
    # Cap here, not at scrape time: unreachable businesses are dropped above,
    # and everything downstream (email verification) costs an API call per lead.
    reachable = reachable[:state.get("max_results", 100)]
    return {**state, "enriched_leads": reachable, "enrichment_errors": errors}

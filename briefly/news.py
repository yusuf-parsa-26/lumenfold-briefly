"""News discovery and selection, independent of the desktop interface.

The publisher allowlist is an editorial filter, not an article fact-check.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from functools import lru_cache
from html import unescape
import os
import re
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from defusedxml import ElementTree
import requests


UTC = timezone.utc
PER_TOPIC = 5
MAX_AGE_DAYS = 30
MAX_TOPIC_LENGTH = 160
TIMEOUT = (4, 10)
MAX_RESPONSE_BYTES = 5_000_000
PUBLISHERS = {
    "reuters.com": "Reuters", "apnews.com": "Associated Press",
    "bbc.com": "BBC News", "bbc.co.uk": "BBC News",
    "theguardian.com": "The Guardian", "npr.org": "NPR", "pbs.org": "PBS",
    "aljazeera.com": "Al Jazeera", "dw.com": "DW", "france24.com": "France 24",
    "cnn.com": "CNN", "ft.com": "Financial Times", "bloomberg.com": "Bloomberg",
    "cnbc.com": "CNBC", "nature.com": "Nature", "sciencenews.org": "Science News",
    "arstechnica.com": "Ars Technica", "techcrunch.com": "TechCrunch",
    "wired.com": "WIRED", "time.com": "TIME",
    "thedailystar.net": "The Daily Star", "tbsnews.net": "The Business Standard",
}
ALIASES = {
    "ai": ("artificial intelligence", "machine learning", "AI"),
    "artificial intelligence": ("artificial intelligence", "machine learning", "AI"),
    "technology": ("technology", "tech", "software", "artificial intelligence", "cybersecurity"),
    "climate": ("climate", "global warming", "emissions", "renewable energy"),
    "climate change": ("climate change", "global warming", "climate", "emissions"),
    "space": ("space", "NASA", "astronaut", "rocket", "satellite"),
    "space exploration": ("space exploration", "NASA", "astronaut", "rocket", "space mission"),
    "science": ("science", "scientist", "research", "discovery"),
    "business": ("business", "economy", "company", "market", "trade"),
    "finance": ("finance", "financial", "economy", "bank", "market"),
    "health": ("health", "medical", "medicine", "disease", "hospital"),
    "sports": ("sport", "sports", "football", "cricket", "tennis", "basketball"),
    "football": ("football", "soccer"),
    "politics": ("politics", "political", "election", "parliament", "government"),
}
STOPWORDS = {"the", "a", "an", "in", "on", "of", "and", "for", "to", "about", "news", "latest"}
QUERY_FILLER = STOPWORDS | {"me", "please", "show", "find", "give", "tell", "updates", "articles", "stories", "with", "from"}
WORD_PATTERN = re.compile(r"(?<!\w)\.[^\W_]+|[^\W_]+(?:[+#]{1,2})?", re.UNICODE)
# Word relationships improve freely entered phrases; they do not restrict what
# the user may enter. Unlisted words are searched literally with plural handling.
WORD_VARIANTS = {
    "economy": ("economy", "economic", "economics", "GDP", "trade", "finance", "financial", "bank", "banks", "lender", "lenders", "income", "incomes"),
    "electric": ("electric", "electrical", "EV", "EVs"),
    "vehicle": ("vehicle", "vehicles", "car", "cars", "automobile", "automobiles", "EV", "EVs"),
    "computing": ("computing", "computer", "computers", "computation", "computational"),
    "healthcare": ("healthcare", "medical", "medicine", "health", "hospital", "hospitals", "treatment", "diagnostic"),
}


class NewsError(Exception):
    """A user-safe error without request URLs or credentials."""


class SearchCancelled(Exception):
    pass


def clean_text(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]*>", " ", value or ""))).strip()


@lru_cache(maxsize=2048)
def tokens(text: str) -> frozenset[str]:
    return frozenset(word for word in WORD_PATTERN.findall(text.casefold()) if word not in STOPWORDS)


@lru_cache(maxsize=2048)
def topic_words(topic: str) -> tuple[str, ...]:
    """Meaningful, literal terms from any typed topic, not a category catalogue."""
    words = tuple(dict.fromkeys(WORD_PATTERN.findall(topic.casefold())))
    return tuple(word for word in words if word not in QUERY_FILLER) or words


def singular(word: str) -> str:
    # Conservative plural handling keeps entities, acronyms, and short names intact.
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith("s") and not word.endswith(("ss", "us", "is", "ics")):
        return word[:-1]
    return word


@lru_cache(maxsize=2048)
def word_forms(word: str) -> tuple[str, ...]:
    base = singular(word)
    return tuple(dict.fromkeys((word, base, *(value.casefold() for value in WORD_VARIANTS.get(base, ())))))


def validate_topics(topics: list[str]) -> tuple[str, str, str]:
    cleaned = tuple(re.sub(r"\s+", " ", topic).strip() for topic in topics)
    if len(cleaned) != 3 or any(not topic for topic in cleaned):
        raise ValueError("Enter all three topics to build your briefing.")
    if any(len(topic) > MAX_TOPIC_LENGTH for topic in cleaned):
        raise ValueError(f"Keep each topic under {MAX_TOPIC_LENGTH + 1} characters.")
    if len({topic.casefold() for topic in cleaned}) != 3:
        raise ValueError("Choose three different topics for a more varied briefing.")
    if any(not topic_words(topic) for topic in cleaned):
        raise ValueError("Type a topic containing at least one letter or number in each box.")
    return cleaned


def publisher_for(url: str) -> str | None:
    if not isinstance(url, str):
        return None
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {"https", "http"} or parsed.username or parsed.password:
            return None
        host = (parsed.hostname or "").lower().rstrip(".")
        return next((name for domain, name in PUBLISHERS.items()
                     if host == domain or host.endswith("." + domain)), None)
    except ValueError:
        return None


def safe_article_url(url: str, via_google: bool = False) -> bool:
    if not isinstance(url, str):
        return False
    try:
        if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in url):
            return False
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in {None, 443}:
            return False
        if via_google:
            return parsed.hostname == "news.google.com" and parsed.path.startswith("/rss/articles/")
        return publisher_for(url) is not None
    except ValueError:
        return False


@lru_cache(maxsize=2048)
def canonical_url(url: str) -> str:
    parsed = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parsed.query)
             if not key.lower().startswith("utm_") and key not in {"gclid", "fbclid", "oc"}]
    return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip("/"), urlencode(query), ""))


def parse_date(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
        except (ValueError, TypeError, OverflowError):
            return None
    if date.tzinfo is None:
        date = date.replace(tzinfo=UTC)
    return date.astimezone(UTC)


@dataclass(frozen=True)
class Article:
    title: str
    url: str
    publisher: str
    description: str = ""
    published: datetime | None = None
    via_google: bool = False


@dataclass
class Briefing:
    topics: tuple[str, str, str]
    articles: dict[str, list[Article]]
    notices: list[str] = field(default_factory=list)
    providers: tuple[str, ...] = ()
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def count(self) -> int:
        return sum(len(items) for items in self.articles.values())


@lru_cache(maxsize=4096)
def relevance(article: Article, topic: str) -> float:
    """Require visible matches to the meaningful terms in a freely typed topic."""
    title = article.title.casefold()
    body = (article.title + " " + article.description).casefold()
    title_tokens, body_tokens = tokens(title), tokens(body)
    phrases = ALIASES.get(topic.casefold(), (topic.casefold(),))
    best = 0.0
    for phrase in phrases:
        words = topic_words(phrase)
        if not words:
            continue
        coverage = sum(bool(set(word_forms(word)) & body_tokens) for word in words) / len(words)
        if coverage < 0.75:
            continue
        title_coverage = sum(bool(set(word_forms(word)) & title_tokens) for word in words) / len(words)
        exact = bool(re.search(r"(?<!\w)" + re.escape(phrase.casefold()) + r"(?!\w)", body))
        best = max(best, 3 * coverage + 3 * title_coverage + (2 if exact else 0))
    return best


def same_story(first: Article, second: Article) -> bool:
    if canonical_url(first.url) == canonical_url(second.url):
        return True
    first_words, second_words = tokens(first.title), tokens(second.title)
    if first_words == second_words:
        return True
    # Most pairs are unrelated. Avoid expensive text alignment unless most
    # headline words overlap; similar words alone do not imply the same story.
    union = first_words | second_words
    if not union or len(first_words & second_words) / len(union) < 0.65:
        return False
    a, b = " ".join(sorted(first_words)), " ".join(sorted(second_words))
    if len(a) <= 25 or len(b) <= 25:
        return False
    matcher = SequenceMatcher(None, a, b)
    return matcher.real_quick_ratio() > 0.90 and matcher.quick_ratio() > 0.90 and matcher.ratio() > 0.90


def is_article_headline(title: str) -> bool:
    """Exclude obvious section/landing pages occasionally indexed as RSS items."""
    normalized = re.sub(r"\s+", " ", title).strip().casefold()
    if len(tokens(normalized)) < 2 or normalized in {
        "latest world news", "latest business news", "latest technology news",
        "breaking news, latest news and videos", "world news - breaking international news",
    }:
        return False
    if normalized.count(",") >= 3 and re.search(r"\bnews\s*$", normalized):
        return False
    if re.match(r"^about\b.*\([a-z0-9.:-]+\)$", normalized):
        return False
    return True


def select_articles(candidates: list[Article], topics: tuple[str, ...],
                    now: datetime | None = None) -> dict[str, list[Article]]:
    """Cover every topic, avoiding duplicate stories and favoring source variety."""
    now = now or datetime.now(UTC)
    valid: list[Article] = []
    for article in candidates:
        if not is_article_headline(article.title) or article.title == "[Removed]" or not safe_article_url(article.url, article.via_google):
            continue
        if article.publisher not in PUBLISHERS.values():
            continue
        if not article.via_google and publisher_for(article.url) != article.publisher:
            continue
        if not article.published or not now - timedelta(days=MAX_AGE_DAYS) <= article.published <= now + timedelta(hours=1):
            continue
        if not any(same_story(article, seen) for seen in valid):
            valid.append(article)
    selected: dict[str, list[Article]] = {topic: [] for topic in topics}
    # valid is already globally deduplicated, so membership needs no further
    # fuzzy comparisons during the fifteen selection rounds.
    used: set[Article] = set()
    for _ in range(PER_TOPIC):
        for topic in topics:
            eligible = [a for a in valid if relevance(a, topic) > 0 and a not in used]
            if not eligible:
                continue

            def score(article: Article) -> float:
                age = max(0, (now - article.published).total_seconds() / 86400)
                repeats = sum(a.publisher == article.publisher for a in selected[topic])
                return relevance(article, topic) + 1.25 / (1 + age / 3) - repeats * 0.8

            chosen = max(eligible, key=score)
            selected[topic].append(chosen)
            used.add(chosen)
    return selected


def search_terms(topic: str, *, title_only: bool = False) -> str:
    # Keep every meaningful user term, without requiring one exact phrase or
    # interpreting user text as provider syntax. Singular/plural alternatives
    # handle headlines such as "electric vehicle" for "electric vehicles".
    phrases = ALIASES.get(topic.casefold(), (topic,))
    queries = []
    for phrase in phrases:
        groups = []
        for word in topic_words(phrase):
            forms = word_forms(word)
            alternatives = " OR ".join(("intitle:" if title_only else "") + f'"{form}"' for form in forms)
            groups.append(f"({alternatives})" if len(forms) > 1 else alternatives)
        if groups:
            query = " AND ".join(groups)
            queries.append(f"({query})" if len(groups) > 1 else query)
    return " OR ".join(queries)


def google_search_terms(topic: str) -> str:
    """RSS search works best with simple keywords, not nested API expressions."""
    return " ".join(f'"{word}"' if word in {"or", "and", "not"} or not word.isalnum() else word
                    for word in topic_words(topic))


def parse_google_feed(data: bytes) -> list[Article]:
    root = ElementTree.fromstring(data)
    if root.tag != "rss":
        raise NewsError("The news service returned an unreadable feed. Try again shortly.")
    language = root.findtext("channel/language", "")
    if language and not language.lower().startswith("en"):
        return []
    articles = []
    for item in root.findall("channel/item"):
        source = item.find("source")
        if source is None:
            continue
        publisher = publisher_for(source.get("url", ""))
        url = (item.findtext("link") or "").strip()
        if not publisher or not safe_article_url(url, via_google=True):
            continue
        title = clean_text(item.findtext("title"))
        suffix = " - " + clean_text(source.text)
        if title.endswith(suffix):
            title = title[:-len(suffix)].strip()
        # RSS descriptions mostly repeat the headline; don't invent a summary.
        articles.append(Article(title, url, publisher, published=parse_date(item.findtext("pubDate")), via_google=True))
    return articles


class NewsService:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key if api_key is not None else os.getenv("NEWSAPI_KEY", "").strip()

    @staticmethod
    def _get(url: str, *, params: dict, headers: dict | None = None) -> requests.Response:
        try:
            response = requests.get(
                url, params=params,
                headers={"User-Agent": "Briefly/1.0 (desktop news reader)", **(headers or {})},
                timeout=TIMEOUT, stream=True, allow_redirects=False,
            )
            try:
                if response.status_code == 429:
                    raise NewsError("The news service is busy or its request limit was reached. Try again later.")
                if response.status_code in {401, 403}:
                    raise NewsError("The news service denied this request. Check your API key or try again later.")
                # A redirect could forward the optional API key to another host.
                if 300 <= response.status_code < 400 or not response.ok:
                    raise NewsError("The news service is temporarily unavailable. Try again shortly.")
                chunks = []
                size = 0
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    size += len(chunk)
                    if size > MAX_RESPONSE_BYTES:
                        raise NewsError("The news service returned an unexpectedly large response.")
                    chunks.append(chunk)
                response._content = b"".join(chunks)
                return response
            finally:
                response.close()
        except requests.RequestException:
            raise NewsError("Could not reach the news service. Check your internet connection and try again.") from None

    def _google(self, topic: str, *, domain: str | None = None) -> list[Article]:
        # Filter source URLs after retrieval. A long OR list of domains in the
        # query can drown out custom terms and crowd out specialist coverage.
        query = google_search_terms(topic)
        if domain:
            query += " site:" + domain
        query += f" when:{MAX_AGE_DAYS}d"
        response = self._get("https://news.google.com/rss/search", params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
        try:
            return parse_google_feed(response.content)
        except NewsError:
            raise
        except Exception:
            raise NewsError("The news service returned an unreadable feed. Try again shortly.") from None

    def _newsapi(self, topic: str) -> list[Article]:
        response = self._get("https://newsapi.org/v2/everything", params={
            "q": search_terms(topic), "language": "en", "domains": ",".join(PUBLISHERS),
            "sortBy": "relevancy", "pageSize": 100,
            "from": (datetime.now(UTC) - timedelta(days=29)).date().isoformat(),
        }, headers={"X-Api-Key": self.api_key})
        try:
            payload = response.json()
        except ValueError:
            raise NewsError("The news service returned an unreadable response.") from None
        if not isinstance(payload, dict) or payload.get("status") != "ok" or not isinstance(payload.get("articles"), list):
            raise NewsError("NewsAPI could not complete the search. Check your key and plan.")
        articles = []
        for item in payload["articles"]:
            if not isinstance(item, dict):
                continue
            url = item.get("url") or ""
            publisher = publisher_for(url)
            if publisher:
                articles.append(Article(clean_text(item.get("title")), url, publisher,
                                        clean_text(item.get("description")), parse_date(item.get("publishedAt"))))
        return articles

    def fetch(self, topics: list[str], progress: Callable[[int, str], None] | None = None,
              cancelled: Callable[[], bool] | None = None) -> Briefing:
        validated = validate_topics(topics)
        cancelled = cancelled or (lambda: False)
        candidates: list[Article] = []
        notices: list[str] = []
        providers: set[str] = set()

        def fetch_topic(topic: str) -> tuple[list[Article], str, str | None]:
            if cancelled():
                raise SearchCancelled()
            if self.api_key:
                try:
                    primary = self._newsapi(topic)
                    if len(select_articles(primary, (topic,))[topic]) >= PER_TOPIC:
                        return primary, "NewsAPI", None
                    if cancelled():
                        raise SearchCancelled()
                    try:
                        extra = self._google(topic)
                        return primary + extra, "NewsAPI + Google News", None
                    except NewsError:
                        return primary, "NewsAPI", "Additional discovery was unavailable; showing the results found by NewsAPI."
                except NewsError:
                    if cancelled():
                        raise SearchCancelled()
                    return self._google(topic), "Google News", "NewsAPI was unavailable; this briefing uses Google News discovery."
            found = self._google(topic)
            supplemental_failed = False
            for domain in ("reuters.com", "bbc.com", "theguardian.com", "cnbc.com", "nature.com"):
                if len(select_articles(found, (topic,))[topic]) >= PER_TOPIC:
                    break
                if cancelled():
                    raise SearchCancelled()
                try:
                    found.extend(self._google(topic, domain=domain))
                except NewsError:
                    supplemental_failed = True
            notice = "Additional publisher discovery was unavailable; showing the suitable results found." if supplemental_failed else None
            return found, "Google News", notice

        errors: list[str] = []
        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="briefly-fetch") as pool:
            futures = {pool.submit(fetch_topic, topic): topic for topic in validated}
            for index, future in enumerate(as_completed(futures), 1):
                if cancelled():
                    raise SearchCancelled()
                topic = futures[future]
                try:
                    found, provider, notice = future.result()
                    candidates.extend(found)
                    providers.add(provider)
                    if notice and notice not in notices:
                        notices.append(notice)
                except NewsError as error:
                    errors.append(str(error))
                    notices.append(f"Search for {topic} could not finish. Refresh the briefing to try again.")
                if progress:
                    progress(index, topic)
        if cancelled():
            raise SearchCancelled()
        if not providers:
            raise NewsError(errors[0] if errors else "No news service is available. Try again shortly.")
        chosen = select_articles(candidates, validated)
        for topic, items in chosen.items():
            if len(items) < PER_TOPIC:
                notices.append(f"{topic}: found {len(items)} of 5 suitable, distinct articles in the past 30 days. Try a broader topic for more coverage.")
        return Briefing(validated, chosen, notices, tuple(sorted(providers)))

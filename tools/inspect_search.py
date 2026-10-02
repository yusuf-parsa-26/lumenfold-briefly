"""Read-only comparison of RSS query formats for discovery diagnostics."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import sys

from defusedxml import ElementTree

from briefly.news import NewsService, PUBLISHERS, parse_google_feed, search_terms, select_articles, topic_words


def main():
    topic = sys.argv[1] if len(sys.argv) > 1 else "Quantum computing"
    words = " ".join(topic_words(topic))
    domains = " OR ".join("site:" + domain for domain in PUBLISHERS)
    queries = {
        "plain": words,
        "phrase": '"' + words + '"',
        "structured": search_terms(topic),
        "headline": search_terms(topic, title_only=True),
        "trusted_plain": f"{words} ({domains})",
        "trusted_phrase": f'"{words}" ({domains})',
    }

    def inspect(item):
        name, query = item
        response = NewsService._get("https://news.google.com/rss/search", params={"q": query + " when:30d", "hl": "en-US", "gl": "US", "ceid": "US:en"})
        root = ElementTree.fromstring(response.content)
        sources = Counter(node.findtext("source", "missing") for node in root.findall("channel/item"))
        parsed = parse_google_feed(response.content)
        chosen = select_articles(parsed, (topic,))[topic]
        lines = [f"{name}: feed={sum(sources.values())}, established publishers={len(parsed)}, selected={len(chosen)}",
                 "  query=" + query, "  language=" + root.findtext("channel/language", "missing"), "  source counts=" + str(sources.most_common(6))]
        for article in parsed[:5]:
            lines.append(f"  {article.publisher}: {article.title} | date={article.published}")
        return "\n".join(lines)

    print("Current UTC:", datetime.now(timezone.utc), flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        for output in pool.map(inspect, queries.items()):
            print(output, flush=True)


if __name__ == "__main__":
    main()

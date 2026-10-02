"""Explicitly fictional headlines for repeatable tests and visual previews."""

from datetime import datetime, timedelta, timezone

from briefly.news import Article, Briefing


TOPICS = ("Artificial intelligence", "Climate", "Space")
EXAMPLE_STORIES = (
    (
        ("Example: Artificial intelligence enters a new chapter in medical research", "reuters.com", "Reuters"),
        ("Example: AI chip developers explore more efficient computing", "bbc.com", "BBC News"),
        ("Example: Schools weigh the role of machine learning in the classroom", "theguardian.com", "The Guardian"),
        ("Example: Artificial intelligence researchers discuss responsible development", "apnews.com", "Associated Press"),
        ("Example: Inside an open-source AI project's community", "arstechnica.com", "Ars Technica"),
    ),
    (
        ("Example: Climate researchers chart the changing rhythms of the ocean", "bbc.com", "BBC News"),
        ("Example: Renewable energy reshapes a community's electricity supply", "reuters.com", "Reuters"),
        ("Example: Cities consider greener transport to reduce emissions", "theguardian.com", "The Guardian"),
        ("Example: How a new generation studies global warming", "npr.org", "NPR"),
        ("Example: A climate summit brings new questions about adaptation", "apnews.com", "Associated Press"),
    ),
    (
        ("Example: NASA prepares instruments for a distant planetary mission", "reuters.com", "Reuters"),
        ("Example: Astronaut training opens a window on life in orbit", "bbc.com", "BBC News"),
        ("Example: A space telescope reveals a new view of distant galaxies", "sciencenews.org", "Science News"),
        ("Example: Rocket engineers test a reusable launch system", "arstechnica.com", "Ars Technica"),
        ("Example: A satellite mission tracks Earth's changing atmosphere", "apnews.com", "Associated Press"),
    ),
)


def example_briefing() -> Briefing:
    now = datetime.now(timezone.utc)
    groups = {}
    for topic_index, (topic, stories) in enumerate(zip(TOPICS, EXAMPLE_STORIES)):
        groups[topic] = [Article(title, f"https://{domain}/example/{topic_index}/{index}", source,
                                "Fictional preview text. Actual briefings show publisher descriptions when the news service supplies them.",
                                now - timedelta(hours=index * 10 + 2))
                         for index, (title, domain, source) in enumerate(stories)]
    return Briefing(TOPICS, groups, providers=("Preview fixtures — not live news",))

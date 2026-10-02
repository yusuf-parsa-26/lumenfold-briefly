from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from html import escape
from unittest import TestCase
from unittest.mock import Mock, patch

import requests

from briefly.news import (
    Article, MAX_TOPIC_LENGTH, NewsError, NewsService, SearchCancelled, canonical_url, clean_text, google_search_terms,
    is_article_headline, parse_date, parse_google_feed, publisher_for, relevance, safe_article_url,
    same_story, search_terms, select_articles, validate_topics,
)
from tests.fixtures import TOPICS, example_briefing


NOW = datetime.now(timezone.utc)


def article(title="AI researchers compare a new approach", url="https://www.bbc.com/news/test", publisher="BBC News", **kwargs):
    return Article(title, url, publisher, published=kwargs.pop("published", NOW), **kwargs)


class TopicsAndSourcesTests(TestCase):
    def test_exactly_three_distinct_topics(self):
        self.assertEqual(validate_topics([" AI ", " climate  change", "Space"]), ("AI", "climate change", "Space"))
        for topics in (["AI", "Space"], ["AI", "", "Space"], ["AI", "ai", "Space"], ["!!", "Climate", "Space"], ["a" * (MAX_TOPIC_LENGTH + 1), "Climate", "Space"]):
            with self.subTest(topics=topics), self.assertRaises(ValueError):
                validate_topics(topics)

    def test_source_hostname_not_substring(self):
        self.assertEqual(publisher_for("https://www.bbc.com/news/story"), "BBC News")
        for url in ("https://bbc.com.evil.example/story", "https://notbbc.com/story", "file:///bbc.com", "https://bbc.com@evil.example/", "https://evil.example/bbc.com"):
            self.assertIsNone(publisher_for(url))

    def test_only_supported_links(self):
        self.assertTrue(safe_article_url("https://news.google.com/rss/articles/abc", True))
        self.assertFalse(safe_article_url("https://news.google.com.evil.example/rss/articles/abc", True))
        self.assertFalse(safe_article_url("javascript:alert(1)"))
        self.assertFalse(safe_article_url("https://news.google.com/search", True))
        self.assertFalse(safe_article_url("http://www.bbc.com/news/story"))
        self.assertFalse(safe_article_url("https://www.bbc.com/news/story\n"))
        self.assertFalse(safe_article_url("https://www.bbc.com:8080/news/story"))
        self.assertFalse(safe_article_url("https://www.bbc.com:invalid/news/story"))

    def test_tracking_parameters_are_deduplicated(self):
        self.assertEqual(canonical_url("https://bbc.com/news/story/?utm_source=x&article=1#section"), "https://bbc.com/news/story?article=1")

    def test_malformed_metadata(self):
        self.assertEqual(clean_text("<p>A &amp; B</p>"), "A & B")
        self.assertEqual(clean_text(123), "")
        self.assertIsNone(parse_date("bad date"))
        self.assertIsNone(parse_date(123))
        self.assertEqual(parse_date("2026-10-01T10:00:00Z").tzinfo, timezone.utc)

    def test_query_input_is_quoted(self):
        self.assertEqual(search_terms('climate" OR site:evil.com'), '("climate" AND "or" AND "site" AND "evil" AND "com")')

    def test_topics_are_not_limited_to_presets(self):
        topics = ["Bangladesh economy", "Electric vehicles", "Quantum computing in healthcare"]
        self.assertEqual(validate_topics(topics), tuple(topics))
        self.assertEqual(validate_topics(["C++", "Beyoncé", "R"]), ("C++", "Beyoncé", "R"))
        self.assertEqual(validate_topics(["The Who", ".NET", "News"]), ("The Who", ".NET", "News"))

    def test_custom_query_uses_words_instead_of_one_exact_phrase(self):
        query = search_terms("news about Bangladesh economy")
        self.assertIn('"bangladesh" AND', query)
        self.assertIn('"economy"', query)
        self.assertNotIn('"bangladesh economy"', query)
        self.assertNotIn('"news"', query)
        self.assertEqual(search_terms("Antarctic penguins"), '("antarctic" AND ("penguins" OR "penguin"))')
        self.assertIn('"ev"', search_terms("Electric vehicles"))
        self.assertEqual(search_terms("C++ programming"), '("c++" AND "programming")')

    def test_rss_query_preserves_user_words_without_complex_syntax(self):
        self.assertEqual(google_search_terms("news about Quantum computing"), "quantum computing")
        self.assertEqual(google_search_terms("Bangladesh economy"), "bangladesh economy")
        self.assertEqual(google_search_terms("C++ programming"), '"c++" programming')
        self.assertEqual(google_search_terms("Cats OR dogs"), 'cats "or" dogs')


class RankingTests(TestCase):
    def test_plural_custom_topic_matches_singular_headline(self):
        self.assertGreater(relevance(article("A new electric vehicle enters production"), "Electric vehicles"), 0)

    def test_specific_topic_requires_visible_context(self):
        topic = "Quantum computing in healthcare"
        relevant = article("Quantum computers offer a new medical breakthrough")
        self.assertGreater(relevance(relevant, topic), 0)
        self.assertEqual(relevance(article("Quantum computing researchers announce a breakthrough"), topic), 0)
        selected = select_articles([relevant], (topic, "Electric vehicles", "Bangladesh economy"), now=NOW)
        self.assertEqual(selected[topic], [relevant])

    def test_custom_topic_requires_both_concepts(self):
        topic = "Electric vehicles"
        visible = article("Electric vehicle production grows")
        partial = article("Electric furnace production plans announced")
        self.assertGreater(relevance(visible, topic), relevance(partial, topic))
        self.assertEqual(relevance(partial, topic), 0)
        self.assertGreater(relevance(article("An EV sold every hundred seconds"), topic), 0)

    def test_provider_hit_without_visible_topic_match_is_rejected(self):
        unrelated = article("Refugees seek a safe place to stay")
        self.assertEqual(relevance(unrelated, "Bangladesh economy"), 0)
        self.assertEqual(relevance(article("Bangladesh dengue deaths rise"), "Bangladesh economy"), 0)

    def test_obvious_category_pages_are_not_articles(self):
        self.assertFalse(is_article_headline("Economy, Tech, AI, Work, Personal Finance, Market news"))
        self.assertFalse(is_article_headline("Latest technology news"))
        self.assertFalse(is_article_headline("About Quantum Computing Inc. (QUBT34.SA)"))
        self.assertTrue(is_article_headline("AI researchers discuss the future of technology"))
        category = article("Economy, Tech, AI, Work, Personal Finance, Market news")
        selected = select_articles([category], ("AI", "Climate", "Space"), now=NOW)
        self.assertEqual(sum(map(len, selected.values())), 0)

    def test_alias_and_word_boundaries(self):
        self.assertGreater(relevance(article("Machine learning changes medical research"), "AI"), 0)
        self.assertEqual(relevance(article("The chair said the train arrived"), "AI"), 0)
        self.assertEqual(relevance(article("A climate report"), "Climate change"), 8)  # explicit category alias
        self.assertEqual(relevance(article("The chip economy grows"), "Quantum computing"), 0)

    def test_five_per_topic_and_unique(self):
        candidates = [a for group in example_briefing().articles.values() for a in group]
        selected = select_articles(candidates, TOPICS)
        self.assertEqual([len(group) for group in selected.values()], [5, 5, 5])
        urls = [a.url for group in selected.values() for a in group]
        self.assertEqual(len(urls), len(set(urls)))

    def test_excludes_stale_future_unknown_and_unrelated(self):
        candidates = [article(), article("AI stale research", url="https://bbc.com/stale", published=NOW - timedelta(days=31)),
                      article("AI future research", url="https://bbc.com/future", published=NOW + timedelta(days=2)),
                      article("AI untrusted", url="https://unknown.example/ai"),
                      article("A completely unrelated cooking recipe", url="https://bbc.com/cooking"),
                      article("AI missing date", url="https://bbc.com/no-date", published=None),
                      article("AI forged source", url="https://bbc.com/forged", publisher="Reuters")]
        selected = select_articles(candidates, ("AI", "Climate", "Space"), now=NOW)
        self.assertEqual([len(group) for group in selected.values()], [1, 0, 0])

    def test_duplicate_titles_and_urls_removed(self):
        first = article()
        duplicate_link = article("AI alternative headline", url=first.url + "?utm_source=x")
        duplicate_title = article(first.title, url="https://reuters.com/same", publisher="Reuters")
        selected = select_articles([first, duplicate_link, duplicate_title], ("AI", "Climate", "Space"), now=NOW)
        self.assertEqual(len(selected["AI"]), 1)

    def test_near_duplicate_headlines_still_merge(self):
        first = article("Climate researchers reveal new measurements of ocean warming around the world")
        second = article("Climate researchers reveal new measurements of ocean warming across the world", url="https://reuters.com/climate", publisher="Reuters")
        self.assertTrue(same_story(first, second))
        different = article("Climate researchers evaluate a completely different project involving rainforests", url="https://bbc.com/forest")
        self.assertFalse(same_story(first, different))

    def test_overlapping_topics_do_not_repeat_article(self):
        selected = select_articles([article("AI technology researchers discuss climate")], ("AI", "Technology", "Climate"), now=NOW)
        self.assertEqual(sum(map(len, selected.values())), 1)

    def test_title_matches_rank_before_description_only(self):
        best = article("Quantum computing research reaches a milestone")
        other = article("Scientists discuss a new project", url="https://bbc.com/other", description="Quantum computing is the focus.")
        self.assertGreater(relevance(best, "Quantum computing"), relevance(other, "Quantum computing"))


class ProviderTests(TestCase):
    def test_three_arbitrary_topics_produce_five_articles_each(self):
        topics = ["Bangladesh economy", "Electric vehicles", "Quantum computing in healthcare"]
        headlines = (
            ("Bangladesh economy faces a new phase of reform", "Bangladesh lenders seek sustainable growth", "Bangladesh trade planners discuss new exports", "Bangladesh household incomes change", "Bangladesh prepares for an economic turning point"),
            ("Electric vehicle manufacturers prepare a new generation", "Electric vehicle charging reaches rural communities", "A quieter future for electric car transport", "Electric cars reshape factory investment", "EV drivers explore longer journeys with cleaner power"),
            ("Quantum computing offers new tools for healthcare", "Researchers explore healthcare with quantum computers", "Hospitals consider a quantum computing diagnostic frontier", "Quantum healthcare researchers study computational models of discovery", "Quantum computing research opens doors to treatment"),
        )
        publishers = (("reuters.com", "Reuters"), ("bbc.com", "BBC News"), ("theguardian.com", "The Guardian"), ("apnews.com", "Associated Press"), ("npr.org", "NPR"))

        def response_for_query(url, *, params, headers=None):
            index = next(i for i, word in enumerate(("bangladesh", "electric", "quantum")) if word in params["q"])
            items = []
            for item_index, (title, (domain, source)) in enumerate(zip(headlines[index], publishers)):
                items.append(f'<item><title>{escape(title)} - {source}</title><link>https://news.google.com/rss/articles/custom{index}_{item_index}</link><pubDate>{format_datetime(NOW)}</pubDate><source url="https://{domain}">{source}</source></item>')
            response = Mock()
            response.content = ('<rss><channel><language>en-US</language>' + ''.join(items) + '</channel></rss>').encode()
            return response

        service = NewsService(api_key="")
        with patch.object(service, "_get", side_effect=response_for_query) as get:
            result = service.fetch(topics)
        self.assertEqual(result.topics, tuple(topics))
        self.assertEqual([len(result.articles[topic]) for topic in topics], [5, 5, 5])
        self.assertEqual(result.count, 15)
        self.assertEqual(get.call_count, 3)
        for topic in topics:
            self.assertTrue(all(relevance(a, topic) > 0 for a in result.articles[topic]))

    def test_feed_filters_publishers_and_removes_suffix(self):
        data = b'''<rss><channel><language>en-US</language>
          <item><title>AI research advances - BBC News</title><link>https://news.google.com/rss/articles/a</link><pubDate>Thu, 01 Oct 2026 10:00:00 GMT</pubDate><source url="https://www.bbc.com">BBC News</source></item>
          <item><title>AI fake - BBC</title><link>https://news.google.com/rss/articles/b</link><source url="https://bbc.com.evil.example">BBC</source></item>
          <item><title>AI script</title><link>javascript:alert(1)</link><source url="https://bbc.com">BBC</source></item>
        </channel></rss>'''
        found = parse_google_feed(data)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].title, "AI research advances")
        self.assertTrue(found[0].via_google)
        self.assertEqual(found[0].description, "")

    def test_non_english_feed_is_rejected(self):
        self.assertEqual(parse_google_feed(b"<rss><channel><language>fr</language></channel></rss>"), [])

    def test_xml_entities_are_blocked(self):
        from defusedxml.common import DefusedXmlException
        with self.assertRaises(DefusedXmlException):
            parse_google_feed(b'<!DOCTYPE rss [<!ENTITY x "boom">]><rss><channel>&x;</channel></rss>')

    @patch("briefly.news.requests.get")
    def test_request_timeouts_and_safe_errors(self, get):
        get.side_effect = requests.ConnectionError("sensitive request details")
        with self.assertRaises(NewsError) as caught:
            NewsService._get("https://example.com", params={})
        self.assertNotIn("sensitive", str(caught.exception))
        self.assertEqual(get.call_args.kwargs["timeout"], (4, 10))
        self.assertFalse(get.call_args.kwargs["allow_redirects"])
        self.assertTrue(get.call_args.kwargs["stream"])

    @patch("briefly.news.requests.get")
    def test_redirect_does_not_forward_api_key(self, get):
        response = requests.Response()
        response.status_code = 302
        response.raw = Mock()
        response.headers["Location"] = "https://other.example/collect"
        response.iter_content = Mock()
        get.return_value = response
        with self.assertRaises(NewsError):
            NewsService._get("https://newsapi.org/v2/everything", params={}, headers={"X-Api-Key": "test-only-secret"})
        self.assertFalse(get.call_args.kwargs["allow_redirects"])
        response.iter_content.assert_not_called()

    @patch("briefly.news.requests.get")
    def test_response_size_is_limited_while_streaming(self, get):
        response = requests.Response()
        response.status_code = 200
        response.raw = Mock()
        response.iter_content = Mock(return_value=iter([b"x" * 3_000_000, b"y" * 2_000_001]))
        get.return_value = response
        with self.assertRaisesRegex(NewsError, "large response"):
            NewsService._get("https://news.google.com/rss/search", params={})
        response.iter_content.assert_called_once_with(chunk_size=64 * 1024)
        response.raw.close.assert_called_once()

    @patch("briefly.news.requests.get")
    def test_response_body_is_available_after_streaming(self, get):
        response = requests.Response()
        response.status_code = 200
        response.raw = Mock()
        response.iter_content = Mock(return_value=iter([b"<rss>", b"</rss>"]))
        get.return_value = response
        self.assertEqual(NewsService._get("https://news.google.com/rss/search", params={}).content, b"<rss></rss>")

    @patch("briefly.news.requests.get")
    def test_rate_limit(self, get):
        get.return_value.status_code = 429
        with self.assertRaisesRegex(NewsError, "limit"):
            NewsService._get("https://example.com", params={})

    def test_newsapi_english_domains_and_header(self):
        service = NewsService(api_key="test-only-secret")
        response = Mock()
        response.json.return_value = {"status": "ok", "articles": [{"title": "AI report", "url": "https://www.bbc.com/news/a", "publishedAt": NOW.isoformat()}]}
        with patch.object(service, "_get", return_value=response) as get:
            self.assertEqual(len(service._newsapi("AI")), 1)
            self.assertEqual(get.call_args.kwargs["params"]["language"], "en")
            self.assertIn("reuters.com", get.call_args.kwargs["params"]["domains"])
            self.assertNotIn("apiKey", get.call_args.kwargs["params"])
            self.assertEqual(get.call_args.kwargs["headers"]["X-Api-Key"], "test-only-secret")

    def test_invalid_api_falls_back(self):
        service = NewsService(api_key="bad-test-key")
        with patch.object(service, "_newsapi", side_effect=NewsError("Invalid key")), patch.object(service, "_google", return_value=[article()]):
            result = service.fetch(["AI", "Climate", "Space"])
        self.assertEqual(result.providers, ("Google News",))
        self.assertTrue(any("NewsAPI was unavailable" in text for text in result.notices))
        self.assertTrue(any("0 of 5" in text for text in result.notices))

    def test_duplicate_api_candidates_trigger_supplemental_discovery(self):
        service = NewsService(api_key="test-key")
        with patch.object(service, "_newsapi", return_value=[article()] * 6), patch.object(service, "_google", return_value=[]) as discovery:
            result = service.fetch(["AI", "Climate", "Space"])
        self.assertEqual(discovery.call_count, 3)
        self.assertEqual(result.count, 1)

    def test_partial_failure_preserves_other_topics(self):
        service = NewsService(api_key="")
        def discovery(topic, **kwargs):
            if topic == "Climate":
                raise NewsError("Temporary outage")
            return [article()]
        progress = []
        with patch.object(service, "_google", side_effect=discovery):
            result = service.fetch(["AI", "Climate", "Space"], lambda count, topic: progress.append(count))
        self.assertEqual(result.count, 1)
        self.assertEqual(len(progress), 3)
        self.assertTrue(any("Climate could not finish" in text for text in result.notices))

    def test_all_sources_failed_is_actionable(self):
        service = NewsService(api_key="")
        with patch.object(service, "_google", side_effect=NewsError("Check your internet connection")):
            with self.assertRaisesRegex(NewsError, "internet"):
                service.fetch(["AI", "Climate", "Space"])

    def test_cancelled_search(self):
        with self.assertRaises(SearchCancelled):
            NewsService(api_key="").fetch(["AI", "Climate", "Space"], cancelled=lambda: True)

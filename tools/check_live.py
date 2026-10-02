"""Read-only integration check against actual English news discovery."""

import argparse
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

from briefly.news import NewsService, NewsError, relevance, safe_article_url


def run_gui_check(topics):
    """Use the actual UI worker, capturing live results without saving preferences."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from briefly.app import BrieflyWindow, configure_application
    from briefly.storage import Store

    app = QApplication([])
    configure_application(app)
    with TemporaryDirectory() as directory:
        window = BrieflyWindow(NewsService(api_key=""), Store(Path(directory)))
        window.show()
        for field, topic in zip(window.inputs, topics):
            field.setFocus()
            QTest.keyClicks(field, topic)
        window.start_search()
        window.worker.progress.connect(lambda count, topic: print(f"Search {count}/3 finished: {topic}", flush=True))
        deadline = monotonic() + 60
        while window.worker and monotonic() < deadline:
            QTest.qWait(20)
        if window.worker:
            window.cancel_search()
            while window.worker:
                QTest.qWait(20)
            window.close()
            raise NewsError("The live interface check exceeded its time limit.")
        if not window.briefing:
            message = window.error.text()
            window.close()
            raise NewsError(message)
        QTest.qWait(300)
        output = Path(__file__).resolve().parents[1] / "artifacts"
        output.mkdir(exist_ok=True)
        window.grab().save(str(output / "live-briefing.png"))
        assert len(window.cards) == window.briefing.count
        assert not window.loading.isVisible()
        result = window.briefing
        window.close()
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui", action="store_true", help="Also exercise the Qt worker and capture the live result screen")
    parser.add_argument("--topics", nargs=3, default=["Technology", "Climate", "Business"], metavar="TOPIC", help="Three freely entered topics to verify")
    args = parser.parse_args()
    start = monotonic()
    try:
        briefing = run_gui_check(args.topics) if args.ui else NewsService(api_key="").fetch(args.topics)
    except NewsError as error:
        print(f"Live discovery failed: {error}")
        return 1
    print(f"Live discovery completed in {monotonic() - start:.1f}s")
    print("Provider:", ", ".join(briefing.providers))
    for topic, articles in briefing.articles.items():
        print(f"{topic}: {len(articles)}/5 articles")
        for article in articles:
            assert safe_article_url(article.url, article.via_google)
            assert relevance(article, topic) > 0
            print("  ", article.publisher, "|", article.title)
    for notice in briefing.notices:
        print("Notice:", notice)
    return 0 if all(len(items) == 5 for items in briefing.articles.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())

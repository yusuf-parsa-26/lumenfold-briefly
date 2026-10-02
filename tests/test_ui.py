import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from unittest import TestCase
from unittest.mock import patch

from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from briefly.app import BrieflyWindow, configure_application
from briefly.news import Briefing, NewsError, SearchCancelled
from briefly.storage import Store
from tests.fixtures import TOPICS, example_briefing


APP = QApplication.instance() or QApplication([])
APP.setQuitOnLastWindowClosed(False)
configure_application(APP)


def wait_until(predicate, timeout=3000):
    deadline = monotonic() + timeout / 1000
    while not predicate() and monotonic() < deadline:
        QTest.qWait(10)
    if not predicate():
        raise AssertionError("Qt operation did not complete within the test deadline")


class FakeService:
    def __init__(self, mode="success"):
        self.mode = mode

    def fetch(self, topics, progress=None, cancelled=None):
        # QTest.qWait would run Qt events in a worker; Event.wait is appropriate
        # for this simulated blocking network I/O instead.
        from threading import Event
        for index, topic in enumerate(topics, 1):
            Event().wait(0.035)
            if cancelled and cancelled():
                raise SearchCancelled()
            if progress:
                progress(index, topic)
        if self.mode == "error":
            raise NewsError("Check your internet connection and try again.")
        return example_briefing()


class InterfaceTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.store = Store(Path(self.temp.name))
        self.window = BrieflyWindow(FakeService(), self.store)
        self.window.show()
        QTest.qWait(30)

    def tearDown(self):
        if self.window.worker:
            self.window.cancel_search()
            wait_until(lambda: self.window.worker is None)
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()
        self.temp.cleanup()

    def fill_topics(self):
        for field, topic in zip(self.window.inputs, TOPICS):
            field.setText(topic)

    def populate(self):
        self.fill_topics()
        self.window.start_search()
        wait_until(lambda: self.window.worker is None)
        QTest.qWait(260)

    def test_requires_three_distinct_topics(self):
        self.assertFalse(self.window.build_button.isEnabled())
        self.window.inputs[0].setText("AI")
        self.window.inputs[1].setText("Climate")
        self.assertFalse(self.window.build_button.isEnabled())
        self.window.inputs[2].setText("ai")
        self.assertFalse(self.window.build_button.isEnabled())
        self.assertIn("different", self.window.form_hint.text())
        self.window.inputs[2].setText("Space")
        self.assertTrue(self.window.build_button.isEnabled())

    def test_no_suggestion_buttons_below_inputs(self):
        suggestions = [item for item in self.window.composer.findChildren(QPushButton) if item.objectName() == "suggestion"]
        self.assertEqual(suggestions, [])
        self.assertEqual(len(self.window.inputs), 3)

    def test_keyboard_topics_are_sent_to_search_and_shown_in_results(self):
        topics = ["Bangladesh economy", "Electric vehicles", "Quantum computing in healthcare"]
        groups = list(example_briefing().articles.values())
        service = self.window.service
        with patch.object(service, "fetch", return_value=Briefing(tuple(topics), dict(zip(topics, groups)), providers=("Test provider",))) as fetch:
            for field, text in zip(self.window.inputs, topics):
                QTest.mouseClick(field, Qt.MouseButton.LeftButton)
                QTest.keyClicks(field, text)
                self.assertEqual(field.text(), text)
                self.assertFalse(field.isReadOnly())
            self.assertTrue(self.window.build_button.isEnabled())
            QTest.keyClick(self.window.inputs[2], Qt.Key.Key_Return)
            wait_until(lambda: self.window.worker is None)
        self.assertEqual(fetch.call_args.args[0], topics)
        self.assertEqual(self.window.briefing.topics, tuple(topics))
        self.assertEqual(len(self.window.cards), 15)
        self.window.show_compose()
        first = self.window.inputs[0]
        QTest.mouseClick(first, Qt.MouseButton.LeftButton)
        QTest.keyClick(first, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClicks(first, "Manchester United")
        self.assertEqual(first.text(), "Manchester United")

    def test_worker_keeps_gui_responsive_and_shows_fifteen_cards(self):
        self.fill_topics()
        heartbeats = []
        timer = QTimer()
        timer.timeout.connect(lambda: heartbeats.append(1))
        timer.start(10)
        QTest.mouseClick(self.window.build_button, Qt.MouseButton.LeftButton)
        self.assertIsNotNone(self.window.worker)
        self.assertFalse(self.window.inputs[0].isEnabled())
        wait_until(lambda: self.window.worker is None)
        timer.stop()
        self.assertGreater(len(heartbeats), 2)
        self.assertEqual(len(self.window.cards), 15)
        self.assertEqual(self.window.view, "briefing")
        self.assertEqual(self.store.topics(), list(TOPICS))
        self.assertFalse(self.window.loading.isVisible())

    def test_topic_filter_and_all_topics(self):
        self.populate()
        self.window.filter_topic(TOPICS[1])
        self.assertEqual(len(self.window.cards), 5)
        self.window.filter_topic(None)
        self.assertEqual(len(self.window.cards), 15)

    def test_bookmark_persistence_and_removal(self):
        self.populate()
        QTest.mouseClick(self.window.cards[0].save_button, Qt.MouseButton.LeftButton)
        self.assertEqual(len(self.window.bookmarks), 1)
        self.assertEqual(len(Store(Path(self.temp.name)).bookmarks()), 1)
        self.window.show_saved()
        self.assertEqual(len(self.window.cards), 1)
        QTest.mouseClick(self.window.cards[0].save_button, Qt.MouseButton.LeftButton)
        QTest.qWait(20)
        self.assertEqual(len(self.window.bookmarks), 0)
        self.assertTrue(self.window.empty.isVisible())

    def test_error_is_readable_and_retry_succeeds(self):
        self.window.service = FakeService("error")
        self.fill_topics()
        self.window.start_search()
        wait_until(lambda: self.window.worker is None)
        self.assertTrue(self.window.error.isVisible())
        self.assertIn("internet", self.window.error.text())
        self.assertTrue(self.window.build_button.isEnabled())
        self.window.service = FakeService()
        self.window.start_search()
        wait_until(lambda: self.window.worker is None)
        self.assertEqual(len(self.window.cards), 15)
        self.assertFalse(self.window.error.isVisible())

    def test_failed_refresh_keeps_existing_briefing(self):
        self.populate()
        self.window.service = FakeService("error")
        self.window.refresh()
        wait_until(lambda: self.window.worker is None)
        self.assertEqual(len(self.window.cards), 15)
        self.assertTrue(self.window.error.isVisible())

    def test_cancel_does_not_replace_result(self):
        self.fill_topics()
        self.window.start_search()
        self.window.cancel_search()
        wait_until(lambda: self.window.worker is None)
        self.assertIsNone(self.window.briefing)
        self.assertTrue(self.window.inputs[0].isEnabled())
        self.assertTrue(self.window.empty.isVisible())

    def test_close_during_fetch_waits_safely(self):
        self.fill_topics()
        self.window.start_search()
        self.window.close()
        self.assertTrue(self.window._closing)
        wait_until(lambda: self.window.worker is None)
        self.assertFalse(self.window.isVisible())

    def test_minimum_window_does_not_overflow_horizontally(self):
        self.window.resize(1060, 760)
        QTest.qWait(30)
        self.assertLessEqual(self.window.scroll.widget().width(), self.window.scroll.viewport().width())
        self.populate()
        self.assertLessEqual(self.window.scroll.widget().width(), self.window.scroll.viewport().width())

    def test_article_opens_original_url(self):
        self.populate()
        with patch("briefly.app.QDesktopServices.openUrl", return_value=True) as open_url:
            self.window.cards[0].open_article()
        self.assertEqual(open_url.call_args.args[0].toString(), self.window.cards[0].article.url)

    def test_saved_topics_loaded_on_next_launch(self):
        self.populate()
        another = BrieflyWindow(FakeService(), Store(Path(self.temp.name)))
        self.assertEqual([field.text() for field in another.inputs], list(TOPICS))
        another.close()
        another.deleteLater()

    def test_corrupted_preferences_are_ignored(self):
        self.store.settings.setValue("topics", "bad json")
        self.store.settings.setValue("bookmarks", '{"unexpected": "object"}')
        self.assertEqual(self.store.topics(), [])
        self.assertEqual(self.store.bookmarks(), {})

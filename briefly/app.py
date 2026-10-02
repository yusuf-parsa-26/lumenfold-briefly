"""Briefly's PySide6 desktop application."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import os
import sys

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QThread, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QFontDatabase, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QDialog, QFrame, QGraphicsOpacityEffect,
    QHBoxLayout, QLineEdit, QMainWindow, QProgressBar, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from .news import Article, Briefing, MAX_TOPIC_LENGTH, NewsError, NewsService, PUBLISHERS, SearchCancelled, canonical_url, safe_article_url, validate_topics
from .storage import Store
from .style import STYLESHEET, TEAL, TOPIC_COLORS
from .widgets import BrandMark, Spinner, WorldArtwork, button, icon, label


def configure_application(app: QApplication):
    app.setApplicationName("Briefly")
    app.setOrganizationName("Briefly")
    app.setStyle("Fusion")
    # Qt's Windows offscreen plugin has no native font discovery. Load installed
    # fonts for faithful automated previews; ordinary desktop windows use the OS.
    if app.platformName() == "offscreen" and sys.platform == "win32":
        fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for name in ("segoeui.ttf", "segoeuib.ttf", "georgia.ttf", "georgiab.ttf"):
            path = fonts / name
            if path.exists():
                QFontDatabase.addApplicationFont(str(path))
    app.setFont(QFont("Segoe UI", 10))


def row(spacing: int = 12) -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    return layout


def column(spacing: int = 12) -> QVBoxLayout:
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    return layout


def frame(name: str, margins: tuple[int, int, int, int], spacing: int = 12):
    widget = QFrame()
    widget.setObjectName(name)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return widget, layout


def date_text(article: Article) -> str:
    if not article.published:
        return "Date unavailable"
    local = article.published.astimezone()
    age = max(0, (datetime.now(timezone.utc) - article.published).total_seconds())
    if age < 3600:
        return "Published recently"
    if age < 86400:
        hours = int(age // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    return local.strftime("%d %b %Y")


class NewsWorker(QThread):
    result = Signal(object)
    failure = Signal(str)
    progress = Signal(int, str)
    cancelled = Signal()

    def __init__(self, service: NewsService, topics: list[str], parent=None):
        super().__init__(parent)
        self.service, self.topics = service, topics

    def run(self):
        try:
            result = self.service.fetch(self.topics, self.progress.emit, self.isInterruptionRequested)
            if not self.isInterruptionRequested():
                self.result.emit(result)
            else:
                self.cancelled.emit()
        except SearchCancelled:
            self.cancelled.emit()
        except (NewsError, ValueError) as error:
            self.failure.emit(str(error))
        except Exception:
            # Provider exceptions can contain credentials; never show raw details.
            self.failure.emit("Something interrupted the search. Please try again.")


class ArticleCard(QFrame):
    save_requested = Signal(object, bool)
    open_failed = Signal(str)

    def __init__(self, article: Article, index: int, color: str, saved: bool, parent=None):
        super().__init__(parent)
        self.article = article
        self.setObjectName("article")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 20, 20, 18)
        layout.setSpacing(19)
        number = label(f"{index:02d}", "articleNumber")
        number.setFixedWidth(39)
        layout.addWidget(number, 0, Qt.AlignmentFlag.AlignTop)
        copy = column(10)
        meta = row(9)
        dot = label("●")
        dot.setStyleSheet(f"color: {color}; font-size: 10px;")
        meta.addWidget(dot)
        meta.addWidget(label(article.publisher.upper(), "articleSource"))
        meta.addWidget(label("·  " + date_text(article), "small"))
        meta.addStretch()
        copy.addLayout(meta)
        title = label(article.title, "articleTitle", True)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        copy.addWidget(title)
        if article.description:
            description = label(article.description[:380], "articleDescription", True)
            description.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            copy.addWidget(description)
        footer = row(14)
        read = button("Read article", "textLink", self.open_article)
        read.setIcon(icon("external", TEAL, 15))
        read.setAccessibleName(f"Read {article.title} from {article.publisher}")
        read.setToolTip("Opens the original article in your browser" + (" via Google News" if article.via_google else ""))
        footer.addWidget(read)
        footer.addWidget(label("via Google News" if article.via_google else "Publisher link", "small"))
        footer.addStretch()
        copy.addLayout(footer)
        layout.addLayout(copy, 1)
        self.save_button = button("", "save")
        self.save_button.setFixedSize(36, 36)
        self.save_button.setIcon(icon("bookmark", TEAL, 17))
        self.save_button.setCheckable(True)
        self.save_button.setChecked(saved)
        self.update_saved_accessibility()
        self.save_button.toggled.connect(self.save_toggled)
        layout.addWidget(self.save_button, 0, Qt.AlignmentFlag.AlignTop)

    def update_saved_accessibility(self):
        text = "Remove from reading list" if self.save_button.isChecked() else "Save to reading list"
        self.save_button.setToolTip(text)
        self.save_button.setAccessibleName(text + ": " + self.article.title)

    def save_toggled(self, checked: bool):
        self.update_saved_accessibility()
        self.save_requested.emit(self.article, checked)

    def open_article(self):
        if not safe_article_url(self.article.url, self.article.via_google):
            self.open_failed.emit("This article link is not safe to open.")
            return
        if not QDesktopServices.openUrl(QUrl(self.article.url)):
            self.open_failed.emit("Your browser could not open this article. Check your default browser settings.")


class BrieflyWindow(QMainWindow):
    def __init__(self, service: NewsService | None = None, store: Store | None = None):
        super().__init__()
        self.service = service or NewsService()
        self.store = store or Store()
        self.bookmarks = self.store.bookmarks()
        self.briefing: Briefing | None = None
        self.worker: NewsWorker | None = None
        self._closing = False
        self.view = "compose"
        self.selected_topic: str | None = None
        self.cards: list[ArticleCard] = []
        self._fade: QPropertyAnimation | None = None
        self._filters = QButtonGroup(self)
        self._filters.setExclusive(True)
        self.setWindowTitle("Briefly — your world, in focus")
        self.resize(1380, 940)
        self.setMinimumSize(1060, 760)
        self.setStyleSheet(STYLESHEET)
        root = QWidget()
        root.setObjectName("canvas")
        self.setCentralWidget(root)
        shell = row(0)
        root.setLayout(shell)
        shell.addWidget(self.build_sidebar())
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        shell.addWidget(self.scroll, 1)
        body = QWidget()
        body.setObjectName("scrollBody")
        self.scroll.setWidget(body)
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(40, 32, 40, 26)
        self.body_layout.setSpacing(22)
        self.build_header()
        self.build_hero()
        self.build_composer()
        self.build_loading()
        self.error = label("", "error", True)
        self.error.hide()
        self.body_layout.addWidget(self.error)
        self.build_result_header()
        self.notice = label("", "notice", True)
        self.notice.hide()
        self.body_layout.addWidget(self.notice)
        self.article_area = QWidget()
        self.article_layout = column(12)
        self.article_area.setLayout(self.article_layout)
        self.body_layout.addWidget(self.article_area)
        self.build_empty()
        self.build_footer()
        self.body_layout.addStretch(1)
        remembered = self.store.topics()
        for edit, text in zip(self.inputs, remembered):
            edit.setText(text)
        self.update_inputs()
        self.show_compose()
        self.update_reading_count()
        self.inputs[0].setFocus()
        shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        shortcut.activated.connect(self.start_search)
        refresh_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        refresh_shortcut.activated.connect(self.refresh)

    def build_sidebar(self) -> QFrame:
        side, layout = frame("sidebar", (22, 32, 22, 24), 10)
        side.setFixedWidth(230)
        brand = row(11)
        mark = BrandMark()
        brand.addWidget(mark)
        brand.addWidget(label("briefly.", "brand"))
        brand.addStretch()
        layout.addLayout(brand)
        layout.addWidget(label("A quieter way to catch up.", "brandTag"))
        layout.addSpacing(43)
        layout.addWidget(label("YOUR SPACE", "sideCaption"))
        layout.addSpacing(7)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_briefing = button("  Your briefing", "nav", self.show_briefing)
        self.nav_saved = button("  Reading list", "nav", self.show_saved)
        self.nav_topics = button("  Your topics", "nav", self.show_compose)
        for nav, kind in ((self.nav_briefing, "news"), (self.nav_saved, "bookmark"), (self.nav_topics, "sliders")):
            nav.setIcon(icon(kind, "#c8d6d5", 19))
            nav.setCheckable(True)
            self.nav_group.addButton(nav)
            layout.addWidget(nav)
        layout.addStretch()
        note, note_layout = frame("sideNote", (16, 19, 16, 18), 10)
        note_layout.addWidget(label("LESS NOISE.\nMORE PERSPECTIVE.", "sideCaption", True))
        note_layout.addWidget(label("Three interests.\nFive stories for each.\nA world worth understanding.", "sideText", True))
        layout.addWidget(note)
        layout.addSpacing(13)
        method = button("How we choose stories", "sideLink", self.show_method)
        method.setIcon(icon("external", "#dfc091", 13))
        layout.addWidget(method)
        layout.addWidget(label("Made for curious minds.   ·   v1.0", "sideSmall"))
        return side

    def build_header(self):
        header = row()
        text = column(5)
        text.addWidget(label("YOUR DAILY PERSPECTIVE", "eyebrow"))
        self.page_title = label("Make room for what matters.", "pageTitle")
        text.addWidget(self.page_title)
        header.addLayout(text, 1)
        right = column(8)
        right.addWidget(label(datetime.now().strftime("%A, %d %B %Y"), "date"), 0, Qt.AlignmentFlag.AlignRight)
        right.addWidget(label("●  English edition", "pill"), 0, Qt.AlignmentFlag.AlignRight)
        header.addLayout(right)
        self.body_layout.addLayout(header)

    def build_hero(self):
        self.hero = QFrame()
        self.hero.setObjectName("hero")
        layout = QHBoxLayout(self.hero)
        layout.setContentsMargins(30, 25, 23, 24)
        layout.setSpacing(18)
        text = column(13)
        text.addWidget(label("A BRIEFING THAT FEELS LIKE YOU", "heroEyebrow"))
        text.addWidget(label("A little curiosity.\nA clearer world.", "heroTitle"))
        text.addWidget(label("Follow what fascinates you. Find five relevant English\narticles for each topic, from established publishers.", "heroCopy", True))
        text.addSpacing(3)
        text.addWidget(label("3 topics   /   15 stories   /   Your perspective", "small"))
        layout.addLayout(text, 3)
        layout.addWidget(WorldArtwork(), 2)
        self.body_layout.addWidget(self.hero)

    def build_composer(self):
        self.composer, layout = frame("composer", (26, 23, 26, 23), 18)
        heading = row()
        heading.addWidget(label("What are you curious about?", "sectionTitle"))
        heading.addStretch()
        self.topic_count = label("0 OF 3", "eyebrow")
        heading.addWidget(self.topic_count)
        layout.addLayout(heading)
        layout.addWidget(label("Type any three topics you want to follow. Your own words will drive each search.", "muted", True))
        fields = row(15)
        self.inputs: list[QLineEdit] = []
        for index in range(3):
            box = column(9)
            caption = label(f"0{index + 1}   TOPIC {index + 1}", "fieldCaption")
            caption.setStyleSheet(f"color: {TOPIC_COLORS[index]};")
            box.addWidget(caption)
            edit = QLineEdit()
            edit.setMaxLength(MAX_TOPIC_LENGTH)
            edit.setPlaceholderText("Type any topic…")
            edit.setAccessibleName(f"Topic {index + 1}")
            edit.setClearButtonEnabled(True)
            edit.textChanged.connect(self.update_inputs)
            edit.returnPressed.connect(self.start_search)
            caption.setBuddy(edit)
            self.inputs.append(edit)
            box.addWidget(edit)
            fields.addLayout(box, 1)
        layout.addLayout(fields)
        footer = row(12)
        self.form_hint = label("A thoughtful read starts with your interests.", "small", True)
        footer.addWidget(self.form_hint, 1)
        self.build_button = button("Build my briefing  →", "primary", self.start_search)
        self.build_button.setMinimumWidth(205)
        self.build_button.setToolTip("Search all three topics · Ctrl+Enter")
        footer.addWidget(self.build_button)
        layout.addLayout(footer)
        self.body_layout.addWidget(self.composer)

    def build_loading(self):
        self.loading, layout = frame("composer", (25, 19, 25, 19), 13)
        heading = row(14)
        heading.addWidget(Spinner())
        message = column(4)
        message.addWidget(label("Finding your next good read…", "sectionTitle"))
        self.loading_text = label("Searching established publishers for your three topics.", "muted", True)
        message.addWidget(self.loading_text)
        heading.addLayout(message, 1)
        self.cancel_button = button("Cancel", "secondary", self.cancel_search)
        heading.addWidget(self.cancel_button)
        layout.addLayout(heading)
        self.progress = QProgressBar()
        self.progress.setRange(0, 3)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(5)
        layout.addWidget(self.progress)
        self.loading.hide()
        self.body_layout.addWidget(self.loading)

    def build_result_header(self):
        self.results_header = QWidget()
        layout = column(17)
        self.results_header.setLayout(layout)
        top = row()
        text = column(7)
        self.results_title = label("Your briefing", "sectionTitle")
        self.results_subtitle = label("", "muted", True)
        text.addWidget(self.results_title)
        text.addWidget(self.results_subtitle)
        top.addLayout(text, 1)
        self.edit_button = button("Edit topics", "secondary", self.show_compose)
        self.refresh_button = button("Refresh", "secondary", self.refresh)
        self.refresh_button.setIcon(icon("refresh", TEAL, 16))
        top.addWidget(self.edit_button)
        top.addWidget(self.refresh_button)
        layout.addLayout(top)
        self.filters_widget = QWidget()
        self.filters_layout = row(8)
        self.filters_widget.setLayout(self.filters_layout)
        layout.addWidget(self.filters_widget)
        self.results_header.hide()
        self.body_layout.addWidget(self.results_header)

    def build_empty(self):
        self.empty, layout = frame("empty", (30, 24, 30, 24), 12)
        heading = row(18)
        illustration = label("")
        illustration.setPixmap(icon("spark", "#b28a60", 34).pixmap(34, 34))
        illustration.setFixedWidth(34)
        heading.addWidget(illustration)
        text = column(7)
        self.empty_title = label("Your interests set the agenda.", "sectionTitle")
        self.empty_copy = label("Add your three topics above. We’ll bring together a concise briefing\nwith clear source labels, publication dates, and links to read more.", "muted", True)
        text.addWidget(self.empty_title)
        text.addWidget(self.empty_copy)
        heading.addLayout(text, 1)
        layout.addLayout(heading)
        self.body_layout.addWidget(self.empty)

    def build_footer(self):
        self.footer = QWidget()
        layout = column(10)
        self.footer.setLayout(layout)
        publishers = row(11)
        publishers.addWidget(label("SOURCES INCLUDE", "eyebrow"))
        for name in ("Reuters", "AP", "BBC News", "The Guardian", "NPR"):
            item = label(name)
            item.setStyleSheet("font-family: Georgia; font-size: 13px; color: #6d7c76;")
            publishers.addWidget(item)
        publishers.addStretch()
        layout.addLayout(publishers)
        self.provenance = label("Selected by topic relevance, recency, and publisher variety. Always read with perspective.", "small", True)
        layout.addWidget(self.provenance)
        self.body_layout.addWidget(self.footer)

    def update_inputs(self):
        if not hasattr(self, "build_button"):
            return
        topics = [edit.text() for edit in self.inputs]
        count = sum(bool(topic.strip()) for topic in topics)
        self.topic_count.setText(f"{count} OF 3")
        try:
            validate_topics(topics)
            valid, hint = True, "You’re all set. Let’s find something worth reading."
        except ValueError as error:
            valid = False
            hint = str(error) if count == 3 else "A thoughtful read starts with your interests."
        self.form_hint.setText(hint)
        self.build_button.setEnabled(valid and self.worker is None)
        if self.error.isVisible() and self.worker is None:
            self.error.hide()

    def show_compose(self):
        if self.worker:
            return
        self.view = "compose"
        self.nav_topics.setChecked(True)
        self.page_title.setText("Make room for what matters.")
        self.hero.show()
        self.composer.show()
        self.results_header.hide()
        self.notice.hide()
        self.article_area.hide()
        self.error.hide()
        self.empty_title.setText("Your interests set the agenda.")
        self.empty_copy.setText("Add your three topics above. We’ll bring together a concise briefing\nwith clear source labels, publication dates, and links to read more.")
        self.empty.show()
        self.footer.show()
        self.provenance.setText("Selected by topic relevance, recency, and publisher variety. Always read with perspective.")
        self.scroll.verticalScrollBar().setValue(0)

    def show_briefing(self):
        if self.worker:
            return
        if not self.briefing:
            self.show_compose()
            self.nav_briefing.setChecked(True)
            return
        self.view = "briefing"
        self.nav_briefing.setChecked(True)
        self.page_title.setText("Your world, in focus.")
        self.hero.hide()
        self.composer.hide()
        self.results_header.show()
        self.refresh_button.show()
        self.edit_button.show()
        self.filters_widget.show()
        self.results_title.setText("Your personal briefing")
        self.results_subtitle.setText(f"{self.briefing.count} stories  ·  3 topics  ·  Up to 5 for each  ·  English")
        self.notice.setText("\n".join(self.briefing.notices))
        self.notice.setVisible(bool(self.briefing.notices))
        self.error.hide()
        self.empty_title.setText("A little more curiosity might help.")
        self.empty_copy.setText("No suitable recent articles were found for these topics. Try broader English topic names, or refresh in a little while.")
        self.empty.setVisible(self.briefing.count == 0)
        self.article_area.setVisible(self.briefing.count > 0)
        self.footer.show()
        providers = " / ".join(self.briefing.providers)
        fetched = self.briefing.fetched_at.astimezone().strftime("%d %b, %H:%M")
        self.provenance.setText(f"Discovered through {providers}  ·  Updated {fetched}  ·  Past 30 days  ·  Ranked by relevance and recency")
        self.render_articles()

    def show_saved(self):
        if self.worker:
            return
        self.view = "saved"
        self.nav_saved.setChecked(True)
        self.page_title.setText("Good reads, kept close.")
        self.hero.hide()
        self.composer.hide()
        self.notice.hide()
        self.error.hide()
        self.results_header.show()
        self.results_title.setText("Your reading list")
        self.results_subtitle.setText(f"{len(self.bookmarks)} saved {'story' if len(self.bookmarks) == 1 else 'stories'}  ·  Ready when you are")
        self.refresh_button.hide()
        self.edit_button.hide()
        self.filters_widget.hide()
        self.empty_title.setText("A place for the stories you want to keep.")
        self.empty_copy.setText("Use the bookmark beside any article to save it here. Your reading list stays on this computer; reading the full article requires internet access.")
        self.empty.setVisible(not self.bookmarks)
        self.article_area.setVisible(bool(self.bookmarks))
        self.footer.hide()
        self.render_articles()
        self.scroll.verticalScrollBar().setValue(0)

    def rebuild_filters(self):
        while self.filters_layout.count():
            item = self.filters_layout.takeAt(0)
            if item.widget():
                self._filters.removeButton(item.widget())
                item.widget().deleteLater()
        entries = [(None, f"All topics  ·  {self.briefing.count}")]
        entries.extend((topic, f"{topic}  ·  {len(self.briefing.articles[topic])}") for topic in self.briefing.topics)
        for topic, text in entries:
            # Long topics remain readable as headings; tabs keep the toolbar compact.
            short = text if topic is None or len(topic) <= 20 else topic[:18] + f"…  ·  {len(self.briefing.articles[topic])}"
            item = button(short, "filter")
            item.setToolTip(text)
            item.setCheckable(True)
            item.setChecked(topic == self.selected_topic)
            item.clicked.connect(lambda checked=False, value=topic: self.filter_topic(value))
            self._filters.addButton(item)
            self.filters_layout.addWidget(item)
        self.filters_layout.addStretch()

    def filter_topic(self, topic: str | None):
        self.selected_topic = topic
        self.render_articles()

    def clear_articles(self):
        self.cards.clear()
        while self.article_layout.count():
            item = self.article_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def add_card(self, article: Article, index: int, color: str):
        card = ArticleCard(article, index, color, canonical_url(article.url) in self.bookmarks)
        card.save_requested.connect(self.toggle_saved)
        card.open_failed.connect(self.show_error)
        self.cards.append(card)
        self.article_layout.addWidget(card)

    def render_articles(self):
        self.clear_articles()
        if self.view == "saved":
            for index, article in enumerate(reversed(list(self.bookmarks.values())), 1):
                self.add_card(article, index, TEAL)
        elif self.briefing:
            for topic_index, topic in enumerate(self.briefing.topics):
                if self.selected_topic and topic != self.selected_topic:
                    continue
                items = self.briefing.articles[topic]
                heading = QWidget()
                heading_row = row()
                heading_row.setContentsMargins(0, 12, 0, 2)
                heading.setLayout(heading_row)
                name = label(f"0{topic_index + 1}   {topic}", "topicHeading", True)
                name.setStyleSheet(f"color: {TOPIC_COLORS[topic_index]};")
                heading_row.addWidget(name, 1)
                heading_row.addWidget(label(f"{len(items)} / 5 ARTICLES", "eyebrow"))
                self.article_layout.addWidget(heading)
                if not items:
                    self.article_layout.addWidget(label("No suitable recent articles found. Try a broader topic or refresh.", "muted", True))
                for index, article in enumerate(items, 1):
                    self.add_card(article, index, TOPIC_COLORS[topic_index])

    def toggle_saved(self, article: Article, saved: bool):
        key = canonical_url(article.url)
        if saved:
            self.bookmarks[key] = article
        else:
            self.bookmarks.pop(key, None)
        self.store.save_bookmarks(self.bookmarks)
        self.update_reading_count()
        if self.view == "saved":
            QTimer.singleShot(0, self.show_saved)

    def update_reading_count(self):
        count = len(self.bookmarks)
        self.nav_saved.setText("  Reading list" + (f"  ({count})" if count else ""))

    def set_busy(self, busy: bool):
        for control in [*self.inputs, self.nav_briefing, self.nav_saved, self.nav_topics, self.edit_button, self.refresh_button]:
            control.setEnabled(not busy)
        self.loading.setVisible(busy)
        self.build_button.setText("Finding your stories…" if busy else "Build my briefing  →")
        self.build_button.setEnabled(not busy)
        if not busy:
            self.update_inputs()

    def start_search(self):
        if self.worker or self.view == "saved":
            return
        try:
            topics = list(validate_topics([edit.text() for edit in self.inputs]))
        except ValueError as error:
            self.show_error(str(error))
            return
        self.error.hide()
        self.notice.hide()
        self.empty.hide()
        self.progress.setValue(0)
        self.loading_text.setText("Searching established publishers for your three topics.")
        self.cancel_button.setEnabled(True)
        self.worker = NewsWorker(self.service, topics, self)
        self.worker.result.connect(self.search_ready)
        self.worker.failure.connect(self.search_failed)
        self.worker.progress.connect(self.search_progress)
        self.worker.cancelled.connect(self.search_cancelled)
        self.worker.finished.connect(self.search_finished)
        self.set_busy(True)
        self.worker.start()
        self.scroll.ensureWidgetVisible(self.loading)

    def refresh(self):
        if self.view == "briefing" and self.briefing and not self.worker:
            for edit, topic in zip(self.inputs, self.briefing.topics):
                edit.setText(topic)
            self.start_search()

    def cancel_search(self):
        if self.worker:
            self.worker.requestInterruption()
            self.cancel_button.setEnabled(False)
            self.loading_text.setText("Cancelling… waiting for active requests to finish.")

    def search_progress(self, completed: int, topic: str):
        self.progress.setValue(completed)
        if self.worker and not self.worker.isInterruptionRequested():
            self.loading_text.setText("Choosing your stories and removing duplicates…" if completed == 3
                                      else f"Checked {topic}.  {completed} of 3 topic searches finished.")

    def search_ready(self, briefing: Briefing):
        if self._closing or (self.worker and self.worker.isInterruptionRequested()):
            return
        self.briefing = briefing
        self.selected_topic = None
        self.store.save_topics(list(briefing.topics))
        self.rebuild_filters()
        # finished() follows this signal; render once the worker reference is cleared.

    def search_failed(self, message: str):
        if self._closing or (self.worker and self.worker.isInterruptionRequested()):
            return
        self.show_error(message)

    def search_cancelled(self):
        if not self._closing:
            self.loading_text.setText("Search cancelled.")

    def search_finished(self):
        previous = self.worker
        self.worker = None
        if previous:
            previous.deleteLater()
        if self._closing:
            self.close()
            return
        failed = self.error.isVisible()
        self.set_busy(False)
        if self.briefing and not failed:
            self.show_briefing()
            self.fade_in()
            self.scroll.verticalScrollBar().setValue(0)
        elif self.view == "compose":
            self.empty.show()
        if failed:
            self.error.show()
            self.scroll.ensureWidgetVisible(self.error)

    def fade_in(self):
        if self._fade:
            self._fade.stop()
        effect = QGraphicsOpacityEffect(self.article_area)
        self.article_area.setGraphicsEffect(effect)
        self._fade = QPropertyAnimation(effect, b"opacity", self)
        self._fade.setDuration(240)
        self._fade.setStartValue(0.1)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.start()

    def show_error(self, message: str):
        self.error.setText(message)
        self.error.show()
        self.scroll.ensureWidgetVisible(self.error)

    def show_method(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("How Briefly chooses stories")
        dialog.setMinimumWidth(650)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(30, 28, 30, 25)
        layout.setSpacing(18)
        layout.addWidget(label("A little context for your context.", "pageTitle"))
        sections = (
            ("01   Match your interests", "Your three typed topics drive separate keyword searches of English news from the past 30 days. We search your meaningful words without requiring one exact phrase, and check individual publishers if more stories are needed. Singular/plural forms and common related words help rank relevant matches."),
            ("02   Keep the source in view", "We restrict results to an explicit list of established publishers and check source domains. This is a publisher filter, not independent verification of each article. Different sources can have different perspectives."),
            ("03   Make space for variety", "We aim for five distinct stories per topic, remove duplicate links and similar headlines, and favor a mix of publishers. If fewer qualify, we show the shortfall."),
            ("04   Go straight to the story", "Read the original article in your browser. Some publishers require a subscription. Google News discovery links redirect to the publisher. Your topics are sent to the selected news service when you search; preferences and bookmarks stay locally."),
        )
        for title, text in sections:
            card, contents = frame("methodCard", (18, 15, 18, 15), 8)
            contents.addWidget(label(title, "sectionTitle"))
            contents.addWidget(label(text, "muted", True))
            layout.addWidget(card)
        layout.addWidget(label("PUBLISHERS\n" + "  ·  ".join(dict.fromkeys(PUBLISHERS.values())), "small", True))
        layout.addWidget(button("Got it", "primary", dialog.accept), 0, Qt.AlignmentFlag.AlignRight)
        dialog.exec()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self._closing = True
            self.worker.requestInterruption()
            self.loading_text.setText("Closing safely after active requests finish…")
            self.cancel_button.setEnabled(False)
            event.ignore()
            return
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    configure_application(app)
    window = BrieflyWindow()
    # The same vector mark is used as the native window icon.
    mark = BrandMark()
    window.setWindowIcon(QIcon(mark.grab()))
    window.show()
    return app.exec()

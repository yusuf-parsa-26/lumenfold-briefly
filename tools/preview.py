"""Capture deterministic desktop layouts using fictional, labelled examples."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from briefly.app import BrieflyWindow, configure_application
from briefly.storage import Store
from tests.fixtures import example_briefing


def main() -> int:
    app = QApplication([])
    configure_application(app)
    output = Path(__file__).resolve().parents[1] / "artifacts"
    output.mkdir(exist_ok=True)
    with TemporaryDirectory() as directory:
        window = BrieflyWindow(store=Store(Path(directory)))
        window.show()
        QTest.qWait(120)
        for name, size in (("welcome", (1380, 940)), ("welcome-compact", (1060, 760))):
            window.resize(*size)
            QTest.qWait(120)
            assert window.grab().save(str(output / f"{name}.png"))
        window.resize(1380, 940)
        window.briefing = example_briefing()
        window.rebuild_filters()
        window.show_briefing()
        QTest.qWait(120)
        assert window.grab().save(str(output / "briefing.png"))
        window.resize(1060, 760)
        QTest.qWait(120)
        assert window.grab().save(str(output / "briefing-compact.png"))
        window.resize(1380, 940)
        window.filter_topic(window.briefing.topics[2])
        window.toggle_saved(window.cards[0].article, True)
        window.show_saved()
        QTest.qWait(120)
        assert window.grab().save(str(output / "reading-list.png"))
        window.show_compose()
        window.show_error("Could not reach the news service. Check your internet connection and try again.")
        QTest.qWait(120)
        assert window.grab().save(str(output / "error.png"))
        window.close()
    print(f"Saved six fixture previews to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

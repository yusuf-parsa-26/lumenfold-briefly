"""The shared visual language for the native Qt interface."""

NAVY = "#182c33"
TEAL = "#267065"
RUST = "#bb5438"
PAPER = "#f7f6f2"
INK = "#23383e"
MUTED = "#6f7b7f"
TOPIC_COLORS = ("#267065", "#bb5438", "#596caa")

STYLESHEET = """
* { font-family: 'Segoe UI'; font-size: 14px; color: #23383e; }
QMainWindow, QWidget#canvas, QScrollArea, QWidget#scrollBody { background: #f7f6f2; }
QWidget { background: transparent; }
QLabel { background: transparent; }
QFrame#sidebar { background: #182c33; border: none; }
QLabel#brand { color: #fffdf5; font-family: 'Georgia'; font-size: 29px; font-weight: bold; }
QLabel#brandTag { color: #acbabd; font-size: 12px; }
QLabel#sideCaption { color: #a6b6ba; font-size: 10px; font-weight: 600; letter-spacing: 2px; }
QLabel#sideText { color: #c3d1d2; font-size: 13px; }
QLabel#sideSmall { color: #a6b6ba; font-size: 11px; }
QFrame#sideNote { background: #233c43; border: 1px solid #385057; border-radius: 12px; }
QPushButton { border: none; border-radius: 9px; padding: 10px 16px; font-weight: 600; }
QPushButton:focus { border: 2px solid #738e91; }
QPushButton#nav { color: #bacacd; text-align: left; padding: 14px 17px; border-radius: 8px; }
QPushButton#nav:hover { background: #263e46; color: white; }
QPushButton#nav:checked { background: #344d51; color: #fffdf5; }
QPushButton#sideLink { color: #dfc091; text-align: left; padding: 8px 0; font-size: 12px; }
QPushButton#sideLink:hover { color: #fff1d7; }
QLabel#eyebrow { color: #647477; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
QLabel#pageTitle { font-family: 'Georgia'; font-size: 26px; }
QLabel#muted { color: #6f7b7f; font-size: 13px; }
QLabel#small { color: #6f7b7f; font-size: 11px; }
QLabel#date { color: #586a70; font-size: 12px; }
QLabel#pill { background: #e9efeb; color: #397267; border-radius: 12px; padding: 6px 11px; font-size: 11px; }
QFrame#hero { background: #eeeae0; border: 1px solid #e4dfd3; border-radius: 18px; }
QLabel#heroTitle { font-family: 'Georgia'; font-size: 39px; color: #23383e; }
QLabel#heroCopy { color: #607074; font-size: 14px; }
QLabel#heroEyebrow { color: #9b6a45; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
QFrame#composer, QFrame#article, QFrame#empty, QFrame#methodCard { background: #ffffff; border: 1px solid #e3e6e1; border-radius: 14px; }
QFrame#article:hover { border: 1px solid #bacac4; }
QLabel#sectionTitle { font-size: 19px; font-weight: 600; }
QLabel#fieldCaption { font-size: 11px; font-weight: 700; color: #788586; letter-spacing: 1px; }
QLineEdit { background: #f9faf7; border: 1px solid #dbe1dc; border-radius: 8px; padding: 13px 12px; font-size: 14px; selection-background-color: #267065; }
QLineEdit:hover { border-color: #b8c8bf; }
QLineEdit:focus { border: 2px solid #267065; padding: 12px 11px; background: white; }
QPushButton#primary { background: #267065; color: white; padding: 13px 22px; }
QPushButton#primary:hover { background: #205f57; }
QPushButton#primary:pressed { background: #184d46; }
QPushButton#primary:disabled { background: #e4e9e5; color: #8d9c96; }
QPushButton#secondary { background: white; border: 1px solid #dbe1dc; padding: 10px 16px; }
QPushButton#secondary:hover { background: #eef3ef; border-color: #b2c5bb; }
QPushButton#secondary:disabled { color: #9ba6a5; }
QPushButton#filter { border: 1px solid #dce2dc; padding: 9px 14px; font-size: 12px; background: #fff; }
QPushButton#filter:hover { background: #edf2ed; }
QPushButton#filter:checked { background: #182c33; color: white; border-color: #182c33; }
QPushButton#textLink { color: #267065; padding: 5px 0; text-align: left; font-size: 12px; }
QPushButton#textLink:hover { color: #173f3a; }
QPushButton#save { background: #f6f7f3; border: 1px solid #e1e5dd; padding: 8px; border-radius: 8px; }
QPushButton#save:hover { background: #e9efea; }
QPushButton#save:checked { background: #e1ede5; border-color: #a0b9aa; }
QLabel#articleTitle { font-family: 'Georgia'; font-size: 21px; color: #23383e; }
QLabel#articleSource { font-size: 11px; font-weight: 600; color: #4b615d; }
QLabel#articleNumber { font-family: 'Georgia'; font-size: 28px; color: #bbc5bd; }
QLabel#articleDescription { color: #68777b; font-size: 13px; }
QLabel#topicHeading { font-size: 18px; font-weight: 600; }
QLabel#notice { background: #f7efe0; border: 1px solid #e4d7bb; border-radius: 10px; padding: 13px 16px; color: #795d35; font-size: 12px; }
QLabel#error { background: #f9eeea; border: 1px solid #e7c6ba; border-radius: 8px; padding: 11px 14px; color: #9d4936; font-size: 12px; }
QProgressBar { border: none; background: #e4eae3; border-radius: 3px; height: 5px; }
QProgressBar::chunk { background: #267065; border-radius: 3px; }
QScrollArea { border: none; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 5px 0; }
QScrollBar::handle:vertical { background: #cbd3cb; border-radius: 4px; min-height: 35px; }
QScrollBar::handle:vertical:hover { background: #a6b7aa; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QDialog { background: #f7f6f2; }
QToolTip { background: #182c33; color: white; border: none; padding: 7px; }
"""

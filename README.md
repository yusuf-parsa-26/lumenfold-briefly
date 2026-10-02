# Briefly

A native **PySide6** news app: choose three interests and get up to **five English articles per topic**, in a clean, editorial desktop interface.

## Install and run

You need **Python 3.10 or newer**, an internet connection for fetching articles, and a desktop environment that can run PySide6. Git is needed if you clone the repository; alternatively, download and extract the repository ZIP from GitHub. No Google News API key or account is required.

### Windows (Command Prompt)

Open Command Prompt in the folder where you want to place the project. If you use Git, get the project first:

```bat
git clone https://github.com/yusuf-parsa-26/lumenfold-briefly.git
cd lumenfold-briefly
```

After `cd lumenfold-briefly`, enter `cd` by itself to display the full folder location. If you downloaded the ZIP, extract it and open Command Prompt in the extracted folder instead. Then create a virtual environment, install dependencies, and launch:

```bat
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

After setup, you can double-click `run.bat` in the project folder to launch it again. `run.bat` expects the `.venv` created above. If the `py` launcher is unavailable, use `python` in the first command after confirming that `python --version` shows 3.10 or newer.

### macOS or Linux (terminal)

```sh
git clone https://github.com/yusuf-parsa-26/lumenfold-briefly.git
cd lumenfold-briefly
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

For a ZIP download, skip the first two commands and run the rest from the extracted folder. On later launches, run `.venv/bin/python main.py`. Linux may require your distribution's graphical Qt/X11 or Wayland libraries. If `venv` is missing, install your distribution's Python `venv` package first.

If installation fails, check that the virtual environment uses Python 3.10+ and that pip can reach the package index. If the window does not appear, launch from a terminal to see the error; on Linux, ensure you are in a graphical desktop session. If stories do not load, check your connection and try another topic or refresh. The RSS service can return fewer than five suitable articles for a topic.

To run the automated checks after setup, use Command Prompt on Windows:

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

On macOS or Linux, replace `.venv\Scripts\python.exe` with `.venv/bin/python`.

## Uninstall

Close Briefly, then delete the `lumenfold-briefly` folder (or the extracted ZIP folder) in your file manager. The dependencies were installed only in that folder's `.venv`, so deleting the folder removes the app and its Python packages. There is no separate uninstaller or system-wide app entry.

The folder also contains `.briefly/preferences.ini`, which holds your saved topics and bookmarks. Copy that file somewhere else first if you want to keep them. If you cloned the repository and prefer Command Prompt, run the following **from inside the project folder** after closing the app:

```bat
cd ..
rmdir /s /q lumenfold-briefly
```

Check the folder name before running the deletion command. If you used a ZIP, substitute its extracted folder name. Python and Git are separate programs; removing this folder does not uninstall them.

## Your briefing

- Type any three different topics in the three text boxes. There is no preset topic menu. Names, places, teams, companies, and specific interests are welcome—for example, `Bangladesh economy`, `electric vehicles`, or `quantum computing`. Press **Build my briefing** or **Ctrl+Enter**.
- Get up to 15 distinct stories, grouped by topic. Filter to one topic, or see everything together.
- Open an article in your default browser. Use the bookmark button to keep it in your reading list.
- Edit your interests any time. **Refresh** / **Ctrl+R** fetches a new briefing for the current topics.
- Requests run in the background. Cancel leaves the interface responsive while active requests finish; closing waits safely for the worker.

Topics and bookmarks persist locally in `.briefly/preferences.ini` inside the project folder. This folder is excluded from Git. News topics are sent to the discovery service only when you build or refresh a briefing. Bookmarks retain article metadata, not full articles; reading still requires internet access. Delete `.briefly` to reset local preferences.

## Where the articles come from

By default, Briefly uses **Google News English RSS search**, with no API key. It checks the feed's publisher URL against an explicit allowlist that includes Reuters, AP, BBC News, The Guardian, NPR, PBS, and other established general or specialist publishers. Google links open via Google News and redirect to the publisher. RSS availability, index coverage, language classification, and redirects are controlled by the service and may change.

Regional English coverage includes [The Daily Star](https://www.thedailystar.net/about-us) and [The Business Standard](https://www.tbsnews.net/anniversary/seven-years-tbs-online-through-history-headlines-and-change-1521286), so local topics are not dependent only on international coverage. These links describe the publishers and their newsroom commitments; the same source, relevance, and recency checks apply.

An optional **NewsAPI** provider supplies direct article links and publisher descriptions. In Windows Command Prompt, set the key for that session before launching:

```bat
set "NEWSAPI_KEY=your-own-key"
.venv\Scripts\python.exe main.py
```

The key is sent in the `X-Api-Key` header, never embedded in source code, request URLs, or interface errors. If NewsAPI fails or has too few matching candidates, RSS discovery is used when available. The interface identifies the services used. A `.env` file is not automatically loaded.

[NewsAPI documents](https://newsapi.org/docs/endpoints/everything) English filtering, domain restrictions, and relevance sorting. Its [Developer plan](https://newsapi.org/pricing) currently has delayed articles and is limited to development/testing; respect your plan's restrictions when distributing or deploying the app. The original script's hard-coded key has been removed; replace or revoke that key in your account if it was exposed elsewhere.

## Selection and reliability

Every search is built from the user's own topic text, up to 160 characters per box. RSS searches use simple meaningful keywords and ignore filler such as "news about", instead of requiring the whole input as one exact phrase or relying on complex Boolean syntax. If fewer than five suitable stories are found, additional searches target individual established publishers. NewsAPI uses its documented Boolean syntax for the same topic words. Singular/plural variations and common related terms help rank matches; these are search aids, not a list of permitted topics.

Candidates must have an allowlisted publisher, a safe article link, and a publication date within the past 30 days. Publisher filtering happens after RSS retrieval so a long list of source operators does not overwhelm custom terms. Headline/description keyword coverage and exact phrases drive relevance, including common related words such as "computer" for "computing" or "EV" for "electric vehicle". At least 75% of the meaningful terms must have a visible match. Unrelated headlines are rejected even if the provider returned them. Newer articles receive a small boost. Repeated publishers receive a small ranking penalty to encourage variety.

Selection proceeds round-robin across topics, with a maximum of five each. Canonical links and similar headlines are deduplicated across the entire briefing. Overlapping or niche topics can therefore return fewer than five stories. The app explains shortfalls rather than padding with unrelated or stale articles. This ranks the best matches within the retrieved candidates, not every article on the internet.

**An established publisher is not a guarantee that an individual article is correct.** This app does not independently fact-check reports, verify every language classification, infer political neutrality, or generate summaries. Read the original source and compare perspectives. Some articles have paywalls. Google RSS generally contains a headline rather than a useful description; those cards show the headline and metadata without an invented summary.

## Development and verification

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m tools.check_live
.venv\Scripts\python.exe -m tools.preview
```

Unit and Qt interaction tests run without internet; the live check makes real requests. Preview captures use explicitly labelled fixture headlines, not actual current news, and save to `artifacts/`. The app uses vector artwork and never downloads decorative or article images.

The modules separate provider/ranking logic (`briefly/news.py`), the native interface (`briefly/app.py`), visual components/styles, and local preferences. Network errors are handled without exposing credentials.

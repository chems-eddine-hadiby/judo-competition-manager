# Judo Competition Manager

A PyQt5 desktop application for managing judo competitions with match control, competitor management, draw generation, results tracking, and a public scoreboard.

## Highlights
- Match control with timer, osaekomi, shido, waza-ari, ippon, golden score
- Time dispute adjustment buttons (±1s / ±5s / ±10s / ±30s)
- Competitor management with weight, gender, age category, and club
- Draw generation with bracket tree, repechage (simple/double), and round robin (3 or 5 athletes)
- Champion seeding (up to 8 per category) with gold highlight
- Public scoreboard window for external display
- Printable draw PDF
- Contest history and results (classement)
- GitHub sync for publishing/importing competitions

## Requirements
- Python 3.8+
- PyQt5
- certifi

Install dependencies:
```bash
pip install -r requirements.txt
```

## Run
```bash
python main.py
```

## First-time Configuration
On launch, configure:
- Age group (Senior / Junior / Cadet / Custom)
- Match time
- Weight categories
- Competition name
- Custom category name (enabled only if age group is Custom)
- Golden score toggle

## Main Tabs
- **Match Control**: select competitors, control timer, scores, penalties, save results
- **Competitors**: add/edit athletes and manage roster
- **Draw**: generate brackets, set champions, choose repechage mode, print draw
- **Results**: contest history + final classement

## Draw Details
- Bracket size is the next power of two
- Byes are auto-advanced
- Round Robin for 3 or 5 athletes with a balanced schedule
- Repechage:
  - Simple: standard QF/SF structure for 8 athletes; larger brackets expand progressively
  - Double: all who lost to each finalist feed into a ladder, leading to bronze
- Champion seeding:
  - Up to 8 champions per category, ordered
  - Seeds placed at fixed bracket positions
  - Champions preferentially receive first‑round byes when possible

## Scoreboard
- Open from the header button
- **F11** toggles fullscreen, **Esc** exits fullscreen

## Results / Classement
- Bracket: 1, 2, 3, 3, 5, 5, 7, 7 (filled as contests are saved)
- Round Robin: ranking by wins, then points (ippon=100, waza‑ari=10, yuko=1)
- Contest history can be cleared from the Results tab

## Data Storage
All data is stored in:
```
~/JudoManager/
```
Files:
- `players.json`
- `draws.json`
- `matches.json`
- `settings.json`

## Competition Categories
- Predefined weight categories are separated by gender (male/female).
- You can add custom categories per gender.
- You can remove predefined categories (they are hidden in settings).

## Sync (Publish / Import)
Competitions can be shared through a private GitHub repo.

### How it works
- Publish uploads `players.json`, `draws.json`, `matches.json`, and `settings.json`.
- Import downloads and replaces the local JSON files.
- A competition password is stored as a salted hash in `meta.json`.

### Requirements
- Set the environment variable `GITHUB_TOKEN` with a repo-scoped token.
- The competition folder name is `competitionName-ageCategory`.

### Quick connectivity test
Run:
```bash
python github_test.py
```

## Auto Sync (Background)
- The app polls the repo every ~15 seconds and pulls updates.
- Changes are pushed after match updates and key edits.
- Conflict policy: last write wins.
- Simple match locking prevents two users starting the same match.

## Build EXE (Windows)
Use PyInstaller (with app icon):
```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name JudoManager --icon icon.ico --add-data "icon.ico;." main.py
```
The EXE will be in `dist/JudoManager.exe`.

## Notes
- Draw UI uses a bracket tree with connectors
- Draws update when match results are saved

# Judo Competition Manager

A PyQt5 desktop application for managing judo competitions with match control, competitor management, draw generation, results tracking, and a public scoreboard.

## Highlights
- Match control with timer, osaekomi, shido, waza-ari, ippon, golden score
- Competitor management with weight, gender, age category, club
- Draw generation with bracket view, repechage (simple/double), and round robin (3 or 5 athletes)
- Public scoreboard window for external display
- Printable draw PDF

## Requirements
- Python 3.8+
- PyQt5

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
- Custom category name (if age group is Custom)

## Main Tabs
- **Match Control**: select competitors, control timer, scores, penalties, save results
- **Competitors**: add/edit athletes and manage roster
- **Draw**: generate brackets, choose repechage mode, print draw
- **Results**: view saved match results

## Draw Details
- Bracket size is the next power of two
- Byes are auto-advanced
- Round Robin for 3 or 5 athletes
- Repechage:
  - Simple: standard QF/SF structure for 8 athletes; larger brackets expand progressively
  - Double: all who lost to each finalist feed into a ladder, leading to bronze

## Scoreboard
- Open from the header button
- **F11** toggles fullscreen, **Esc** exits fullscreen

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

## Build EXE (Windows)
Use PyInstaller:
```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name JudoManager main.py
```
The EXE will be in `dist/JudoManager.exe`.

## Notes
- Draw UI uses a bracket tree with connectors
- Draws update when match results are saved

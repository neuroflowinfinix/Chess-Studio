# ♟️ Chess Studio

**Chess Studio** is a modern, high-performance chess analysis and training suite built in Python and Pygame. Designed to bridge the gap between heavy offline engines and sleek web-based GUIs, it features a highly animated interface, dynamic text-to-speech (TTS) bot personalities, and a robust hybrid-engine architecture.

Unlike standard chess GUIs, this application understands the *context* of the board. It dynamically triggers vocal trash-talk during blunders, draws sleek translucent MultiPV continuation arrows, and seamlessly hot-swaps between local NNUE engines (like Stockfish) and the Lichess Cloud API to protect your CPU during deep analysis.

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-brightgreen.svg)
![Pygame](https://img.shields.io/badge/Pygame-2.6%2B-yellow.svg)

---

## 👨‍💻 Developer's Note

This project is the culmination of 3-4 months of dedicated, intense development. Building a chess GUI from scratch that can handle asynchronous engine threading, spring-physics UI rendering, and real-time API fallbacks without dropping frames was a monumental challenge. 

A massive thank you to the open-source chess community. This project stands on the shoulders of giants, and was heavily inspired by the incredible work done by the developers of **[LucasChess](https://lucaschess.pythonanywhere.com/)** (for its legendary offline training depth) and **[En Croissant](https://encroissant.org/)** (for its beautiful, modern approach to UI and database integration). 

---

## ✨ Key Features

* **🧠 Hybrid Engine Architecture:** Automatically falls back to local engines during heavy Game Reviews to prevent Lichess Cloud API IP bans, while maintaining instant, zero-CPU cloud evaluations for live play.
* **📺 Broadcast-Quality UI:** Features a custom spring-physics evaluation bar based on True Win Probability (WDL), fading "ghost" moves, floating evaluation bubbles, and dynamic tactical threat arrows.
* **🗣️ Reactive TTS Personalities:** Play against dynamic bots (including a terrifying "Assassin" logic and a low-Elo "Martin" simulator) that vocally react to discovered checks, queen blunders, and brilliant sacrifices in real-time.
* **📖 Grandmaster Explorer:** A fully integrated SQLite database explorer that asynchronously fetches master-level continuations and win rates without freezing the main event loop.
* **🎯 Guided Practice Trainer:** An interactive opening trainer that uses 3-strike rules and dashed hint arrows to force you to memorize critical lines.
* **📊 Deep Game Review:** Post-game analysis generates accuracy scores, categorizes moves (Brilliant, Great, Blunder, etc.), and saves annotated PGNs directly to a local profile archive.
* Note: in the source code, the feature calibrate engine has been retained which works with a terminal, this feature will be removed from the release for normal users who are not developers.
* Store and analyze your games from lichess.org and chess.com

### The main UI with integrated openings panel

<img width="1680" height="987" alt="python_xn92SdL6XA" src="https://github.com/user-attachments/assets/27a150cc-eb8d-4894-a31c-47a5772c9208" />

### Engine settings

<img width="1680" height="987" alt="python_pADuxM4qwI" src="https://github.com/user-attachments/assets/1a78f9d6-5bbb-4a81-8c81-1fb3e60d0cf4" />

### v/s bot mode

<img width="1680" height="987" alt="python_y6FxwTrAIp" src="https://github.com/user-attachments/assets/1f2a9023-1394-421c-a48d-de35ca69ee55" />

### PGN imports

<img width="1680" height="987" alt="python_5jiIrvJ55R" src="https://github.com/user-attachments/assets/74bd7824-cb4a-476e-a3e0-a163038ac93c" />

### chess.com and lichess.org account imports

<img width="1680" height="987" alt="python_PBViQBQvO2" src="https://github.com/user-attachments/assets/496a996e-9769-4596-9353-1e1fd3a0dd99" />

### Interactive mate and openings trainer

<img width="1680" height="987" alt="python_iZrccOgbE1" src="https://github.com/user-attachments/assets/a1cb4524-65a0-4275-8ced-3a8c95db441e" />

### Detailed analysis and review

<img width="1680" height="987" alt="python_VNDbpdx0KV" src="https://github.com/user-attachments/assets/afa97693-8f71-4444-aa5e-f9bf28c916fd" />

---

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/neuroflowinfinix/Chess-Studio.git](https://github.com/neuroflowinfinix/Chess-Studio.git)
   cd Chess-Studio
   ```

2. **Install the required dependencies:**
   Make sure you have Python 3.8+ installed. 
   ```bash
   pip install pygame chess requests matplotlib numpy joblib
   ```
   *(Note: Ensure you have your preferred TTS library installed if you are using the voice features).*

3. **Add your Chess Engine:**
   Due to file size limits, chess engines are not included in this repository. 
   * Download [Stockfish](https://stockfishchess.org/download/) (or your preferred UCI engine like RubiChess).
   * Place the `.exe` file inside the `engines/` folder.
   * If using NNUE, place the `.nnue` file in `engines/nnue/` or `assets/evaluationfiles/`, make sure the name of .nnue file of an engine is exactly same as that of the engine .exe file.

4. **Run the application:**
   ```bash
   python main.py
   ```

---

## 🎮 Controls & Hotkeys

* **Left Click:** Select and move pieces.
* **Right Click & Drag:** Draw custom tactical arrows on the board.
* **Left Click (Off-board):** Clear all custom arrows.
* **Arrow Keys (Left/Right):** Navigate through move history.
* **E:** Toggle the Grandmaster Opening Explorer overlay.
* **Ctrl + Z:** Undo move (Takeback).
* **Ctrl + F:** Flip the board.
* **Ctrl + S:** Save the current game to PGN.
* **Ctrl + R:** Reset / New Game.

---

## 📁 File Structure Overview

* `main.py`: The core application loop and event handler.
* `ui_renderer.py`: Handles all Pygame drawing, animations, and the WDL evaluation bar.
* `analysis_engine.py`: Manages asynchronous communication with UCI engines and move classification.
* `live_evaluator.py`: Live-game telemetry and evaluation.
* `popups.py`: All UI modal windows (Review, Settings, Profile, etc.).
* `database_explorer.py`: SQLite logic for the GM Explorer.
* `account_manager.py`: External network status monitoring.
* `assets/`: Contains piece images, sounds, TTS voice maps, and archived PGN ledgers.
* `engines/`: Directory for your local `.exe` UCI chess engines.
* `build_db.py`: database builder.

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.

---

## 🙏 Acknowledgments

* **LucasChess** & **En Croissant** for setting the gold standard in open-source chess software.
* **[python-chess](https://python-chess.readthedocs.io/en/latest/)** for the incredibly robust board representation and UCI protocol handling.
* **[Lichess API](https://lichess.org/api)** for providing world-class cloud evaluation databases.
* **[Pygame](https://www.pygame.org/)** for the rendering framework.
* **[PGNMentor](https://www.pgnmentor.com/files.html#players)** for pgn files used in making database and .bin files for Checkmate_master bot.
```

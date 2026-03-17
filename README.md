# Telegram Multi-Utility Bot

A powerful async Telegram bot built with `python-telegram-bot` (v20.x) that provides AI chat, YouTube audio conversion, and image generation features.

## Features

- **AI Chat (Gemini 2.0 Flash)**: Natural language conversations with context awareness.
- **YouTube → Audio**: Download and convert YouTube videos to high-quality MP3s.
- **Image Generator (Pollinations)**: Create stunning images from text prompts with multiple model options.
- **Async & Concurrent**: Handles multiple users simultaneously without blocking.
- **Background Tasks**: Heavy operations like downloading and image generation run in the background.

## Prerequisites

- **Python 3.10+**
- **FFmpeg**: Required for audio conversion. Must be installed and available in your system's PATH.
  - **Windows**: `choco install ffmpeg` or download from [ffmpeg.org](https://ffmpeg.org/download.html).
  - **Linux**: `sudo apt install ffmpeg`
  - **macOS**: `brew install ffmpeg`

## Setup

1. **Clone or Download** the repository.
2. **Create a Virtual Environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```
3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Environment Variables**:
   Create a `.env` file in the root directory:
   ```env
   TELEGRAM_BOT_TOKEN=8645746271:AAGxXUOzAjztKossfzyoD_XWCYQzq0AhwmE
   GEMINI_API_KEY=AIzaSyCj1P60ctcJkJyb3BKFLVFkX-3WOKgMVVY
   ```

## Running the Bot

```bash
python bot.py
```

## Project Structure

- `bot.py`: Main entry point and state machine handlers.
- `utils.py`: API wrappers and processing logic.
- `requirements.txt`: Project dependencies.
- `.env`: (Not included) Sensitive configuration.

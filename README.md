# Chess Opening Analyzer

Compare your Chess.com games against your Chessly repertoire (stored in Lichess Studies) and find the first move you deviated from book.

## Features

- 🔐 Connect your Lichess account via OAuth
- 📚 Select your repertoire studies (one per opening)
- 🎮 Fetch games from Chess.com with filters (date, time control, rated)
- 🔍 Find the first deviation in each game
- ✅ Shows what you played vs. what you should have played
- ⚠️ Detects when opponent left your book

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- A Lichess account with your repertoire saved as Studies

### Local Development

1. **Clone and install backend dependencies:**

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Install frontend dependencies:**

```bash
cd frontend
npm install
```

3. **Start the backend:**

```bash
cd backend
uvicorn main:app --reload --port 8000
```

4. **Start the frontend (separate terminal):**

```bash
cd frontend
npm run dev
```

5. **Open http://localhost:5173**

### Creating Your Repertoire on Lichess

1. Go to [lichess.org/study](https://lichess.org/study)
2. Create one study per opening (e.g., "Italian Game", "Sicilian Defense")
3. Add your Chessly moves as chapters
4. For each opponent move, enter your one correct response
5. Save and make sure you're logged in when using this app

## Deployment to Render

1. Push this repo to GitHub
2. Create a new Web Service on [render.com](https://render.com)
3. Connect your GitHub repo
4. Set the `REDIRECT_URI` environment variable to your Render URL + `/callback`
   (e.g., `https://chess-opening-analyzer.onrender.com/callback`)
5. Deploy!

## Tech Stack

- **Backend:** FastAPI, python-chess, httpx
- **Frontend:** React, Vite
- **APIs:** Lichess API, Chess.com Public API
- **Hosting:** Render (free tier)

## License

MIT

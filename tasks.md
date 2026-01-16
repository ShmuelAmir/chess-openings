# Chess Opening Deviation Analyzer - Tasks

## Overview

Web app that compares your chess.com games against your Chessly repertoire (stored in Lichess Studies) and shows the first move you deviated from book.

---

## Tasks

### Phase 1: Backend Setup

- [x] Create FastAPI app structure
- [x] Implement Lichess OAuth2 with PKCE
- [x] Create Lichess API client (list studies, fetch PGN)
- [x] Create Chess.com API client (fetch games with filters)

### Phase 2: Core Logic

- [x] Build repertoire parser (PGN → move tree)
- [x] Build deviation analyzer (compare game vs repertoire)
- [x] Handle "opponent left book" case
- [x] Handle "you deviated" case

### Phase 3: Frontend

- [x] Set up React app with Vite
- [x] Create Lichess OAuth flow component
- [x] Create study picker component
- [x] Create chess.com filters form
- [x] Create results table component

### Phase 4: Integration & Deploy

- [x] Connect frontend to backend API
- [x] Add Render deployment config
- [ ] Test full flow end-to-end
- [ ] Deploy to Render

---

## Progress Log

### January 16, 2026

- Project started
- Created initial project structure
- Implemented full backend (FastAPI, Lichess OAuth, Chess.com client, analyzer)
- Implemented full frontend (React + Vite, all components)
- Added Render deployment config

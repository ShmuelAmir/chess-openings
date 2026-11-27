# Chess Opening Analyzer

Helps a player find where they leave their prepared openings. Their Repertoire comes from their Lichess studies, their games come from their linked Chess.com account, and every game is checked for the first move that wasn't in the Repertoire. How it's built lives in [docs/architecture.md](./docs/architecture.md).

## Language

### Repertoire

**Repertoire**:
The opening lines the user has prepared: every Lichess Study they own, except the ones they've marked "not repertoire". It has separate lines for White and Black. Games where the user plays White are checked only against the White lines, and games as Black only against the Black lines.
_Avoid_: book, prep, opening tree

**Study**:
One Lichess study in the Repertoire, normally one opening. It belongs to exactly one color, the orientation of its first chapter, and adds lines only to that color. Its name is part of the Repertoire, so renaming it on Lichess changes the Repertoire, and the new name shows after the next Sync.
_Avoid_: course, chapter (a chapter is a part of a Study)

**Book move**:
A move the Repertoire has at a given position. When several moves are prepared there, each one is a Book move; no single move is "correct".
_Avoid_: correct move, best move

**Opening Name**:
The readable label for a Study, taken from its name, for example "Sicilian Defense" or "London System".
_Avoid_: opening (on its own), which is ambiguous with the Chess.com opening label

**Chess.com opening label**:
The opening name Chess.com gives a game. It knows nothing about the Repertoire, and only the Opening Distribution uses it.

### Games and analysis

**Deviation**:
The first move in a game that isn't a Book move. It has one of three causes:
- **Player error:** the user played a move outside their prepared lines.
- **Opponent left book:** the opponent played an unprepared move first.
- **Book completed:** the game went past the end of the prepared lines.
_Avoid_: mistake, leak

**Miss Rate**:
The share of analysed games with a player-error Deviation. It's the headline measure of whether recall is improving. Only real games count, never Drill Attempts. The Game Filters narrow which games count, so picking a Study gives that Study's Miss Rate.
_Avoid_: accuracy (Chess.com's engine score), error rate

**Miss Depth**:
How far into a line the user gets before going wrong: which of their own moves (2nd, 3rd, …; the full-move number, the same for both colors) the player-error Deviation came on. It's the companion to Miss Rate: misses moving later over time is progress, even when the Miss Rate stays the same.
- **Which games:** only games with a player-error Deviation. The earliest possible is the 2nd move, because a game that's off-book on the user's 1st move isn't analysed.
- **Per opening:** the Study filter narrows it the same way it narrows Miss Rate.
- **Over time:** per month, how many misses fell on each move (2nd through 9th, then 10th or later), with the month's median marked once it has at least 3 misses.
_Avoid_: Book Depth, Recall Depth

**Opening Distribution**:
How often the user plays each opening and how they score in it, by Chess.com opening label. It reads the games only, never the Repertoire, Recall Gaps or Deviations.

**Game Filters**:
The criteria that choose which games are analysed:
- **Time control:** bullet, blitz, rapid or daily.
- **Rated:** rated games only, or rated and casual.
- **Color:** White, Black or both. This filter is on the Opening Distribution only; on the Recall view the Study filter decides the color.
- **Date range:** on the Recall view, one of four presets (last month, last 3 months, last year, all time). On the Opening Distribution, explicit start and end dates.
- **Study:** one or more Studies, or none for all of them. It narrows which Recall Gaps are shown and which games the totals count, but never changes what the Repertoire or a Recall Gap is. A gap shows when any selected Study contains its position. A game counts when its Deviation position is in a selected Study; passing through one Study's lines on the way into another's doesn't count.

The Game Filters can't be changed during practice.
_Avoid_: "settings"

### Recall loop

**Recall Gap**:
A Repertoire position where the user has made a player-error Deviation at least once. It's the unit of the recall loop: one thing to fix.
- **Identity:** the position itself (board, side to move, castling, en passant, but not the move counters), whatever move order reached it.
- **Occurrence:** each player-error Deviation at the position. Different wrong moves at the same position are occurrences of the same gap.
- **Ranking:** by number of occurrences inside the Game Filters, with ties broken by the most recent occurrence.
- **Studies:** the gap belongs to every Study whose lines contain its position.

Only player errors form Recall Gaps. Opponent-left-book and book-completed Deviations appear only in the totals.
_Avoid_: mistake, leak, weak spot

**Open / Closed**:
A Recall Gap's status. It becomes Closed once the user has reached its position in two real games since its last occurrence and played a Book move both times. All real games count, whatever the Game Filters, and Drill Attempts never count. A new occurrence reopens the gap and starts the count again.
_Avoid_: fixed, resolved, mastered

**Drill Attempt**:
One practice run of a Recall Gap. The user replays the line of the gap's most recent occurrence from the first move up to the gap's position and plays a move there. The app plays the opponent's moves, and any Book move counts as correct at every turn. The attempt passes, or fails at the first wrong move, which is recorded with its position. Drill Attempts decide when a gap is Due, but they never create gaps, change their ranking or change whether they're Open or Closed.
_Avoid_: exercise, puzzle, quiz

**Due**:
Whether a Recall Gap should be drilled now. A gap with no Drill Attempts is Due. Successive passes hold it back for 1 day, then 3, then 7, and it stays at 7. A fail makes it Due at once and restarts that count, and so does a real-game occurrence newer than the last Drill Attempt (in any game, whatever the Game Filters).

**Practice session**:
Drills the Due Open gaps that the Game Filters show, one after another in ranking order, until nothing is Due or the user stops. Closed gaps are left out, though the user can still drill one on demand.

**Recall view**:
The user's ranked Recall Gaps, totals and Miss Rate under the Game Filters, together with the list of Studies for the Study filter, each with its name, color and number of Recall Gaps. The Studies list is part of the Recall view, not a separate screen.

**Progress panel**:
Part of the Recall view, opened from the Miss Rate trend. It shows the monthly Miss Rate and Miss Depth over the last 12 months, under every Game Filter except the date range. Selecting a Study shows progress in that opening.

### Account and data

**User**:
The person using the app, identified by their Lichess account. Their Repertoire, "not repertoire" list and Drill Attempts belong to that account: signing in again keeps them, and another Lichess account never sees them.
_Avoid_: player, because every game has two players

**Linked Chess.com account**:
The Chess.com account whose games the User analyses. The User can change it, and doing so leaves the Repertoire unchanged.

**Sync**:
Brings the linked Chess.com account's games and the Lichess Repertoire up to date, then re-runs the analysis if anything changed. It runs when the app opens and the last Sync is stale, or when the user asks. A User has one Sync.
- **Changing the linked account:** a Sync that's already running finishes for the account it started with, and the new account's Sync runs after it. A Sync's result belongs to the account it ran for, and is never shown for another account.
- **Partial Sync:** some Chess.com months, or the Lichess refresh, failed. What succeeded is kept, and the failed parts are retried on the next Sync.
- **During practice:** a Sync never interrupts a Drill Attempt. Its result waits until practice ends.
- **What changed:** when a Sync changes something, it reports the difference from the previous analysis: new games, new Recall Gaps, and gaps newly Closed or reopened. This shows until the app is next opened.
_Avoid_: refresh, import

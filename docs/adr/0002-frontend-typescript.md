# ADR-0002: The Frontend Is TypeScript, in Strict Mode

**Date:** 2026-11-27  
**Status:** Accepted  
**Context:** Type checking the frontend (issue #82)

## Problem

The frontend was plain JavaScript, and nothing checked the few types it wrote down: a JSDoc typedef for the Recall view's practice state (PR #74), five annotations in one module. The `implement` skill tells agents to "run typechecking regularly", but there was no typecheck to run, so the step was skipped without anyone saying so.

The mistakes a type checker catches were found at runtime or in review instead:

1. The in-memory backend drifting from the HTTP backend
2. A misspelled Game Filter field
3. A component passing the wrong shape of Recall Gap
4. TanStack Router's typed route params and search params going unused, since it types them only in TypeScript

## Options considered

1. **JSDoc checking for the Recall view only.** Turn on `checkJs` for the Recall view store and its typedef. Rejected: it checks the one module that already has types and leaves the drift above, which sits in the backend adapters, the Game Filters and the components, unchecked.
2. **JSDoc checking for all of the frontend.** Rejected: there was almost no JSDoc to check, so this meant writing types for the whole frontend anyway, in comment syntax that is wordier than TypeScript's and gives weaker support for React props, generics and TanStack Router's route registration.
3. **JSDoc as documentation only.** Keep the typedefs as comments and check nothing. Rejected: an unchecked type goes stale like any comment, and it leaves "run typechecking" with no command behind it.
4. **TypeScript, strict.** Chosen.

## Solution

Every frontend source and test file is TypeScript (`.ts`, `.tsx`), checked by one `frontend/tsconfig.json` with `strict: true`. The migration ran module by module with `allowJs` on (#91 to #98); with it done, `allowJs` is gone.

- **`make lint` runs the typecheck.** `make lint-frontend` runs Prettier, `tsc --noEmit` (`npm run typecheck`) and a check that `frontend/src` holds no `.js` or `.jsx` file, and fails if any of the three does. The last check is needed because `tsc` without `allowJs` skips a JavaScript file rather than reporting it. CI runs `make lint`, so a type error never reaches main.
- **Vitest runs `src/**/*.test.ts` only**, and the Vite config is `vite.config.ts`, so the only JavaScript left in the frontend is in `node_modules`.
- **The domain types live at the frontend backend seam.** `frontend/src/backend/backend.ts` holds the `Backend` interface, which both the HTTP and the in-memory adapter implement, and the types its calls take and return, named in the glossary's language (`RecallGap`, `GameFilters`, `SyncState`, `DrillAttempt`, `Study`, …). They describe the API's JSON as it is; nothing validates a response at runtime. Coding standard 4 keeps them in step with the API.
- **Page-local API types stay local.** The Opening Distribution and Settings pages call the backend server directly, not through `Backend`, so the shapes only they read (`OpeningDistribution`, `OwnedStudy`, the OAuth JSON, the FastAPI error body, …) are declared in those pages.
- **Escapes are explained.** `any`, `@ts-ignore` and non-null assertions are avoided, and carry a comment saying why where they can't be. Type-only facts, such as the in-memory backend's scripting API rejecting a misspelled call name, are checked in `*.typecheck.ts` and `*.typecheck.tsx` files with `@ts-expect-error`, which `tsc` runs; they get no runtime tests.

## Tradeoffs

**Pros:**

- **A real command:** "run typechecking" means `make lint` (or `npm run typecheck`), locally and in CI
- **Drift is a type error:** adding or changing a `Backend` call fails in every adapter, and in every scripted test answer, until all are updated
- **Typed routes:** a link to a route that doesn't exist is a type error
- **No build change:** Vite and Vitest already compiled TypeScript

**Cons:**

- **Types are trusted, not checked:** a backend response that differs from the `Backend` types is only caught by the API contract test, not at runtime
- **A compiler to keep current:** `typescript` is one more dev dependency

## Future Work

- Generate the `Backend` types from the backend's OpenAPI schema, so they can't drift from the API

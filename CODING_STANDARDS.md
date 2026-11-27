# Coding Standards

Judgement calls for review. Formatting, import order and the like belong to the linters, not here.

1. **Comments explain _why_, never repeat the code.** A comment that restates the line below it goes stale and adds noise; 23 of them once needed a cleanup PR.
2. **A glossary term is never reused for something else.** Each term in `GLOSSARY.md` means one thing; a review once caught "depth" used for cell colour intensity, which collides with Miss Depth.
3. **The Recall Gap aggregator stays pure: no I/O.** `backend/recall_gaps.py` is tested with plain data and no fakes, which stops working the moment it reads a file, the cache or the network.
4. **A change to the shape of what the API returns updates the API contract test and the frontend's `Backend` types in the same PR.** The frontend relies on that shape, and the contract test (`test_the_recall_view_is_served_as_the_pipeline_returns_it` in `backend/tests/test_main.py`) is what catches it drifting. The types in `frontend/src/backend/backend.ts` describe it to the frontend, and nothing checks them against a real response.

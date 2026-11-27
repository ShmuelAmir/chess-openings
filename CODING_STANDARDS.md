# Coding Standards

Judgement calls for review. Formatting, import order and the like belong to the linters, not here.

1. **Comments explain _why_, never repeat the code.** A comment that restates the line below it goes stale and adds noise; 23 of them once needed a cleanup PR.
2. **A glossary term is never reused for something else.** Each term in `GLOSSARY.md` means one thing; a review once caught "depth" used for cell colour intensity, which collides with Miss Depth.
3. **The Recall Gap aggregator stays pure: no I/O.** `backend/recall_gaps.py` is tested with plain data and no fakes, which stops working the moment it reads a file, the cache or the network.
4. **A change to the shape of what the API returns updates the API contract test in the same PR.** The frontend relies on that shape, and `backend/tests/test_main.py` (`test_the_recall_view_is_served_as_the_pipeline_returns_it`) is the only check that it holds.

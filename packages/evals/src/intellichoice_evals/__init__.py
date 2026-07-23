"""SPEC §5.31 Evaluation platform (S30, plan §13).

This package does not reimplement evaluators that already live correctly next to the
code they test - it gives the scattered SPEC §5.31.1-§5.31.4 categories one indexed
home (`registry.py`) plus the pieces that genuinely didn't exist before this session:
a real LLM-as-judge caller (`llm_judge.py`, `BedrockTask.LLM_JUDGE`'s first caller) and
a golden fixture of tricky answer/hint pairs for the leak-detection evaluator
(`leak_sample.py`), reusing `intellichoice_curriculum.authored_validation`'s existing
leak-check functions rather than duplicating that logic.
"""

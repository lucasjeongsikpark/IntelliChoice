"""The one place the weak-skill cut is defined.

It used to live in `learning_api.services.mastery_bootstrap`, which was fine while every
consumer was inside learning-api (`topic_resolver`, `learning_gain`). AUD-L-13 (D-156)
added a consumer in `intellichoice_memory.consolidation` - a package, which cannot import
an app - and the alternative was a second copy of the number. Two definitions of a
classification threshold is how the same skill ends up "weak" to one subsystem and
"proficient" to another, which is precisely the class of defect AUD-L-13 reports.

`mastery_bootstrap` re-exports this name, so existing imports are unaffected.
"""

# D-017: bootstrap weak-skill cut, superseded once the enterprise IRT model (SPEC §5.10.2)
# lands. A skill whose `mastery.weighted_score` is below this is "weak"; at or above it,
# "proficient". Used for study-plan targeting (`topic_resolver`), unresolved-skill
# classification (`learning_gain`), and the memory-fact consistency floor
# (`consolidation`).
WEAK_SKILL_THRESHOLD = 0.7

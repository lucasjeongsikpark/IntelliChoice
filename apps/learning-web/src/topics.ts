/**
 * Topic display names come from the server now (D-380).
 *
 * **What was here and why it was wrong.** A hand-maintained `TOPIC_LABELS` map with three
 * entries. D-187 accepted the drift as "cosmetic (an unlisted topic renders its id)" when the
 * map covered nearly the whole bank — and the C1 generation waves took the bank to **33
 * topics while the map stayed at 3**, so 30 of 33 rendered `g4_multiplication_division` at a
 * student on their own dashboard. The rare path had become the default and nothing
 * re-examined the premise. SPEC §5.10.3 and CLAUDE.md rule 10 are about exactly this.
 *
 * The file's own docstring had named the fix — *"would need a new field on the history
 * endpoint to lose this map"* — so that field now exists (`topic_name`), resolved from the
 * curriculum next to `unresolved_skill_names`, which had always been done properly.
 */

/**
 * Last-resort humanisation for a name the server did not supply.
 *
 * Reached only for a row predating `topic_name`, and it is deliberately not a lookup table:
 * a second map would recreate exactly the drift this change removes. `g4_word_problems`
 * becomes "G4 Word Problems" — imperfect, and unmistakably better than the raw id at a child.
 */
function humanise(topicId: string): string {
  return topicId
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function topicLabel(topicId: string | null, topicName?: string | null): string {
  if (topicName) return topicName;
  if (!topicId) return "\u2014";
  return humanise(topicId);
}

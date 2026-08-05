// Display labels only. The `available` flags that used to live here were the second of two
// disagreeing availability sources (D-187) - hand-maintained in the frontend while the
// backend's `grade_topic_candidates` went unread - and now come from
// `GET /learning/sessions/:id/topics`, which derives them from the template bank.
//
// The labels stayed, deliberately: `StudentDashboardScreen` names topics from *historical*
// sessions, outside any learning session, so it has no topic-list response to read and
// would need a new field on the history endpoint to lose this map. Drift here is cosmetic
// (an unlisted topic renders its id, see the fallback below) rather than a student being
// offered a topic with no questions behind it, which is what the availability flags risked.
const TOPIC_LABELS: Record<string, string> = {
  linear_equations: "Linear Equations",
  fraction_operations: "Fraction Operations",
  place_value: "Place Value",
};

export function topicLabel(topicId: string | null): string {
  if (!topicId) return "—";
  return TOPIC_LABELS[topicId] ?? topicId;
}

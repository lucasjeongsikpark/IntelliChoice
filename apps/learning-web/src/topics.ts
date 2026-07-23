// Only `linear_equations` has an authored template bank (S4/D-003/D-016) - the other
// two curriculum topics are listed so pickers reflect the real taxonomy, but disabled
// rather than silently hidden.
export const TOPICS = [
  { id: "linear_equations", label: "Linear Equations", available: true },
  { id: "fraction_operations", label: "Fraction Operations", available: false },
  { id: "place_value", label: "Place Value", available: false },
];

export function topicLabel(topicId: string | null): string {
  if (!topicId) return "—";
  return TOPICS.find((t) => t.id === topicId)?.label ?? topicId;
}

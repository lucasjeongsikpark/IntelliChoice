import type { TopicOption } from "../types";

interface Props {
  // D-187: `null` means "not loaded yet", which is not the same as "no topics" - an empty
  // list would be a real (and alarming) answer, so the two must not share a representation.
  topics: TopicOption[] | null;
  // Distinguishes "still loading" from "the fetch failed" - both leave `topics` null, and
  // showing the loading line for a failure is a spinner that never resolves.
  loadFailed: boolean;
  onSelect: (topicId: string) => void;
  busy: boolean;
  error: string | null;
}

/**
 * Suggested-for-this-grade first, everything else after, **order preserved within each
 * group** so the curriculum's own sequence still reads top to bottom.
 *
 * A stable partition rather than a sort: `Array.prototype.sort` is only required to be
 * stable in modern engines and the intent here is "two lists", not "one list ranked".
 *
 * The empty group is dropped by the caller rather than rendered as an empty heading — a
 * student whose grade matches nothing sees the plain list they saw before, with no dangling
 * "For you" promising something that is not there.
 */
function groupTopics(topics: TopicOption[]): [string, TopicOption[]][] {
  return [
    ["For you", topics.filter((t) => t.recommended_for_grade)],
    ["All topics", topics.filter((t) => !t.recommended_for_grade)],
  ];
}

export function TopicSelectScreen({ topics, loadFailed, onSelect, busy, error }: Props) {
  return (
    <div className="panel">
      <h1>Choose a topic</h1>
      {error && <p className="error">{error}</p>}
      {topics === null ? (
        loadFailed ? (
          <p className="error">We couldn&rsquo;t load the topics just now. Please refresh to try again.</p>
        ) : (
          <p>Loading topics…</p>
        )
      ) : (
        <>
          {groupTopics(topics).map(([heading, group]) =>
            group.length === 0 ? null : (
              <section key={heading}>
                {/* The heading carries what the per-card badge used to. With 33 topics the
                    badge was scattered through a ~5,000px scroll, so the two or three
                    suggested for this student's grade were the hardest ones to find - the
                    exact opposite of what a recommendation is for. */}
                <h2 className="topic-group-heading">{heading}</h2>
                <div className="card-list">
                  {group.map((t) => (
                    <button
                      key={t.topic_id}
                      className="card"
                      disabled={busy || !t.available}
                      onClick={() => onSelect(t.topic_id)}
                    >
                      <strong>{t.name}</strong>
                      {/* Availability comes from the bank now, so "Coming soon" is a fact
                          about content rather than a flag someone remembered to flip. */}
                      {!t.available && <span>Coming soon</span>}
                    </button>
                  ))}
                </div>
              </section>
            ),
          )}
        </>
      )}
    </div>
  );
}

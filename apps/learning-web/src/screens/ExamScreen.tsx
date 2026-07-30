import { useEffect, useRef, useState } from "react";
import { ExamTimer } from "../components/ExamTimer";
import { QuestionNavBar } from "../components/QuestionNavBar";
import { SubmitConfirmationModal } from "../components/SubmitConfirmationModal";
import type { ExamOverview, QuestionItem } from "../types";

interface Props {
  phase: string;
  // Raw `snapshot.items` every render - non-null only at a phase transition (the fixed
  // 10-item pre/post-exam batch, or the study phase's single current item). This screen
  // caches the exam-phase batch itself (see the effect below) since subsequent per-answer
  // snapshots carry `items: null` once free navigation replaces "advance to the next
  // question" (S22/D-064).
  items: QuestionItem[] | null;
  streak: number;
  overview: ExamOverview | null;
  busy: boolean;
  error: string | null;
  onSubmit: (questionVariantId: string, selectedOption: string, responseTimeMs: number) => void;
  onSkip: (assessmentItemId: string) => void;
  onFlag: (assessmentItemId: string, flagged: boolean) => void;
  onRecordTime: (assessmentItemId: string, elapsedMs: number) => void;
  onFetchOverview: () => void;
  onFinalize: (confirmUnanswered: boolean) => Promise<boolean>;
}

const PHASE_LABELS: Record<string, string> = {
  pre_exam: "Pre-exam",
  study: "Study",
  post_exam: "Post-exam",
};

const DIFFICULTY_LABELS: Record<number, string> = {
  1: "Warm-up",
  2: "Building confidence",
  3: "Growing stronger",
  4: "Challenge",
  5: "Advanced challenge",
};

function difficultyLabel(difficulty: number | undefined): string {
  if (difficulty === undefined) return "";
  return DIFFICULTY_LABELS[difficulty] ?? `Level ${difficulty}`;
}

const OVERVIEW_POLL_MS = 20000;

export function ExamScreen({
  phase,
  items,
  streak,
  overview,
  busy,
  error,
  onSubmit,
  onSkip,
  onFlag,
  onRecordTime,
  onFetchOverview,
  onFinalize,
}: Props) {
  const isExamPhase = phase === "pre_exam" || phase === "post_exam";

  const [cachedBatch, setCachedBatch] = useState<QuestionItem[] | null>(null);
  const [currentDisplayOrder, setCurrentDisplayOrder] = useState(0);
  const [answeredSelections, setAnsweredSelections] = useState<Record<number, string>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");

  // AUD-F-02: `POST /exam/finalize` closes the exam server-side, but this screen stays
  // mounted until the phase-change snapshot arrives over SSE. Anything it sends in that
  // window - the poll's next tick, or the view-time flush in the autosave effect's cleanup
  // as it unmounts - lands on a closed exam and is rejected 409. Each rejection is a
  // browser console error, and §2.6 criterion 3 requires zero of those. Nothing is lost by
  // suppressing them: the last question's timing already reached the server as that
  // answer's own `response_time_ms`.
  //
  // Cleared on every phase change, so the post-exam gets its own guard rather than
  // inheriting the pre-exam's.
  const finalizedRef = useRef(false);

  // Reset all per-phase-instance state when the phase itself changes (pre_exam -> study
  // -> post_exam) - this screen stays mounted across all three, so state from the prior
  // phase must not bleed into the next.
  useEffect(() => {
    setCachedBatch(null);
    setCurrentDisplayOrder(0);
    setAnsweredSelections({});
    setSelected(null);
    setModalOpen(false);
    // React runs every cleanup before any effect body, so the autosave cleanup for the
    // outgoing phase has already read the old value by the time this clears it.
    finalizedRef.current = false;
  }, [phase]);

  // Batched pre/post-exam items arrive once at the phase transition (SPEC §5.9.2's fixed
  // question set); the study phase serves one question at a time and needs no caching.
  useEffect(() => {
    if (isExamPhase && items && items.length > 1) {
      setCachedBatch(items);
    }
  }, [isExamPhase, items]);

  useEffect(() => {
    if (!isExamPhase) return;
    onFetchOverview();
    const id = window.setInterval(() => {
      if (finalizedRef.current) return;
      onFetchOverview();
    }, OVERVIEW_POLL_MS);
    return () => window.clearInterval(id);
  }, [isExamPhase, phase, onFetchOverview]);

  useEffect(() => {
    setSelected(null);
  }, [currentDisplayOrder, phase]);

  // Gated on `isExamPhase`, which AUD-F-24 turned from a nicety into a correctness
  // requirement. `overview` is the *exam's* item list and App keeps holding it after the
  // phase moves on, so outside an exam phase this lookup used to keep resolving a
  // **pre-exam** item. That fed the view-time effect below an `assessmentItemId` belonging
  // to a finished exam, while the phase-change effect above had just cleared
  // `finalizedRef` - so the next dependency change flushed a `POST .../time` for a
  // pre-exam item against a closed exam and took a 409 (AUD-F-02's class, measured as
  // exactly one 409 at +2004ms once the screen stopped unmounting at the transition).
  //
  // Previously the unmount hid it: the screen was destroyed at the phase change, so the
  // stale-overview window never got a second commit to fire in. Keeping the screen mounted
  // is the point of AUD-F-24, so the staleness has to be handled rather than outrun.
  // Gating here is also just what the data means - view time is recorded against
  // `assessment_item_id`, which only exists for pre/post-exam items, never for study.
  const currentOverviewItem = isExamPhase
    ? overview?.items.find((item) => item.display_order === currentDisplayOrder)
    : undefined;

  // View-time autosave tick: flushes accumulated time for the item being left whenever
  // the student navigates away (nav-bar jump, submit-and-advance) or the screen unmounts.
  // The `finalizedRef` check is AUD-F-02's: unmounting *because the exam was finalized* is
  // the one case where this flush has nowhere valid to land.
  const viewStartRef = useRef<number>(Date.now());
  useEffect(() => {
    viewStartRef.current = Date.now();
    const assessmentItemId = currentOverviewItem?.assessment_item_id;
    return () => {
      if (assessmentItemId && !finalizedRef.current) {
        onRecordTime(assessmentItemId, Date.now() - viewStartRef.current);
      }
    };
  }, [currentDisplayOrder, phase, currentOverviewItem?.assessment_item_id, onRecordTime]);

  const currentItem = isExamPhase
    ? (cachedBatch?.find((item) => item.display_order === currentDisplayOrder) ?? null)
    : (items?.[0] ?? null);

  const isReadOnly = isExamPhase && currentOverviewItem?.status === "answered";

  function handleSelect(key: string) {
    if (busy || isReadOnly) return;
    setSelected(key);
    setStatusMessage(`Option ${key.toUpperCase()} selected.`);
  }

  function handleSubmitClick() {
    if (!currentItem || !selected || busy) return;
    const chosen = selected;
    const responseTimeMs = Date.now() - viewStartRef.current;
    onSubmit(currentItem.question_variant_id, chosen, responseTimeMs);
    setAnsweredSelections((prev) => ({ ...prev, [currentDisplayOrder]: chosen }));
    setStatusMessage(`Answer submitted for question ${currentDisplayOrder + 1}.`);
    setSelected(null);
    if (isExamPhase) {
      onFetchOverview();
      if (cachedBatch && currentDisplayOrder < cachedBatch.length - 1) {
        setCurrentDisplayOrder((d) => d + 1);
      }
    }
  }

  function handleSkip() {
    if (!currentOverviewItem || busy) return;
    onSkip(currentOverviewItem.assessment_item_id);
    setStatusMessage(`Question ${currentDisplayOrder + 1} skipped.`);
    if (cachedBatch && currentDisplayOrder < cachedBatch.length - 1) {
      setCurrentDisplayOrder((d) => d + 1);
    }
  }

  function handleFlagToggle() {
    if (!currentOverviewItem || busy) return;
    const flagged = currentOverviewItem.status !== "flagged";
    onFlag(currentOverviewItem.assessment_item_id, flagged);
    setStatusMessage(
      `Question ${currentDisplayOrder + 1} ${flagged ? "flagged for review" : "unflagged"}.`,
    );
  }

  function handleJump(displayOrder: number) {
    setCurrentDisplayOrder(displayOrder);
    setStatusMessage(`Jumped to question ${displayOrder + 1}.`);
  }

  // Both finalize paths raise `finalizedRef` *before* awaiting, and lower it again only if
  // the call fails. Setting it afterwards is too late and measurably so: `finalizeExam`
  // calls `setSnapshot` inside the awaited request, so React can flush that render - and
  // unmount this screen, running the view-time cleanup - in a microtask that lands before
  // the `await` here resumes. Instrumented during S41: the flush reported
  // `phase=pre_exam finalized=false` for the last item every single run.
  async function handleExpire() {
    setStatusMessage("Time's up. Submitting your exam now.");
    finalizedRef.current = true;
    const ok = await onFinalize(false);
    if (!ok) {
      finalizedRef.current = false;
      setModalOpen(true);
    }
  }

  async function handleFinalizeConfirm() {
    const hasUnanswered = overview?.items.some((item) => item.status !== "answered") ?? false;
    finalizedRef.current = true;
    const ok = await onFinalize(hasUnanswered);
    if (ok) setModalOpen(false);
    else finalizedRef.current = false;
  }

  function handleContainerKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (busy || isReadOnly || !currentItem) return;
    if (["1", "2", "3", "4"].includes(event.key)) {
      const index = Number(event.key) - 1;
      const key = ["a", "b", "c", "d"][index];
      if (key) {
        event.preventDefault();
        handleSelect(key);
      }
    } else if (event.key === "Enter" && selected) {
      event.preventDefault();
      handleSubmitClick();
    }
  }

  if (!currentItem) {
    return (
      <div className="panel">
        <p>Loading the next question…</p>
      </div>
    );
  }

  const options: [string, string][] = [
    ["a", currentItem.option_a],
    ["b", currentItem.option_b],
    ["c", currentItem.option_c],
    ["d", currentItem.option_d],
  ];
  const position =
    isExamPhase && cachedBatch
      ? `Question ${currentDisplayOrder + 1} of ${cachedBatch.length}`
      : "";
  const rememberedSelection = answeredSelections[currentDisplayOrder];

  return (
    <div className="panel wide" onKeyDown={handleContainerKeyDown}>
      <div className="progress-bar">
        <span className="phase-chip">{PHASE_LABELS[phase] ?? phase}</span>
        <span>{position}</span>
        {phase === "study" && streak > 1 && <span className="streak">🔥 {streak} in a row</span>}
        {isExamPhase && (
          <ExamTimer remainingSeconds={overview?.remaining_seconds ?? null} onExpire={handleExpire} />
        )}
      </div>

      {isExamPhase && overview && (
        <QuestionNavBar
          items={overview.items}
          currentDisplayOrder={currentDisplayOrder}
          disabled={busy}
          onJump={handleJump}
        />
      )}

      {isExamPhase && currentOverviewItem && (
        <span className="difficulty-badge">{difficultyLabel(currentOverviewItem.difficulty)}</span>
      )}

      <h1>{currentItem.rendered_question}</h1>

      {isReadOnly && (
        <p className="readonly-note">
          You've already answered this question - it's locked in and can't be changed.
        </p>
      )}

      <div className="options">
        {options.map(([key, text]) => {
          const isSelected = isReadOnly ? rememberedSelection === key : selected === key;
          return (
            <button
              key={key}
              type="button"
              className={`option ${isSelected ? "selected" : ""}`}
              disabled={busy || isReadOnly}
              aria-pressed={isSelected}
              onClick={() => handleSelect(key)}
            >
              <span aria-hidden="true">{key.toUpperCase()}.</span> {text}
            </button>
          );
        })}
      </div>

      {error && <p className="error">{error}</p>}

      {!isReadOnly && (
        <>
          <button type="button" disabled={busy || !selected} onClick={handleSubmitClick}>
            {busy ? "Submitting…" : "Submit answer"}
          </button>
          {isExamPhase && (
            <div className="exam-actions">
              <button type="button" className="secondary" disabled={busy} onClick={handleSkip}>
                Skip
              </button>
              <button
                type="button"
                className="secondary"
                disabled={busy}
                onClick={handleFlagToggle}
              >
                {currentOverviewItem?.status === "flagged" ? "Unflag" : "Flag for review"}
              </button>
            </div>
          )}
        </>
      )}

      {isExamPhase && overview && (
        <button
          type="button"
          className="secondary"
          disabled={busy}
          onClick={() => setModalOpen(true)}
        >
          Submit exam
        </button>
      )}

      <div className="sr-only" role="status" aria-live="polite">
        {statusMessage}
      </div>

      {modalOpen && overview && (
        <SubmitConfirmationModal
          overview={overview}
          busy={busy}
          onConfirm={() => void handleFinalizeConfirm()}
          onCancel={() => setModalOpen(false)}
        />
      )}
    </div>
  );
}

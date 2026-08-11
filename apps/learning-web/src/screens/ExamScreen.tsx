import { useEffect, useRef, useState } from "react";
import { ExamTimer } from "../components/ExamTimer";
import { QuestionNavBar } from "../components/QuestionNavBar";
import { QuestionStem } from "../components/QuestionStem";
import { SubmitConfirmationModal } from "../components/SubmitConfirmationModal";
import type { AssistanceQuestion, ExamOverview, QuestionItem } from "../types";

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
  // D-272: the question the help on screen right now is about, straight from the server
  // (`assistance_question`). Non-null means this column shows *that* question, locked, with
  // the option the student chose marked - for the whole time help is up, chooser through
  // hint 3, solution and video included.
  //
  // It replaces D-217's `paused` + `pausedQuestionText` pair, and the replacement is the
  // fix rather than a tidy-up. Those two could only produce a *stem* - no options - and only
  // while the client happened to have cached the right question; once the ladder closed,
  // `App.tsx` had no correct question at all and rendered the help alone in a narrow card.
  assistanceQuestion?: AssistanceQuestion | null;
  // D-218: true while a stage-transition narrative is over this screen. The overlay is
  // `aria-modal` with a scroll lock, so the exam behind it is genuinely unreachable - which
  // is why the time limit must not be counting yet, and why focus must not be moved into a
  // screen the student cannot see.
  overlayOpen?: boolean;
  error: string | null;
  onSubmit: (questionVariantId: string, selectedOption: string, responseTimeMs: number) => void;
  onSkip: (assessmentItemId: string) => void;
  onFlag: (assessmentItemId: string, flagged: boolean) => void;
  onRecordTime: (assessmentItemId: string, elapsedMs: number) => void;
  onFetchOverview: () => void;
  // D-218: reports that the exam is on screen with nothing over it. Idempotent server-side.
  onExamViewed: () => void;
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

/**
 * D-272: the question a hint, solution, video or chat is about - locked, complete, and with
 * the option the student actually chose marked.
 *
 * **The options are the point.** The screen this replaces showed the stem alone, and only
 * sometimes. A student reading "start by working out how many are in 5 rows" with no answer
 * choices in front of them has to hold four numbers in memory while they read - the
 * split-attention cost the whole two-column layout exists to remove.
 *
 * Marking their own choice is the other half. "You picked C" is information they cannot get
 * back any other way once the answer path closes, and it is what makes the hint feel like it
 * is about *their* attempt rather than about the question in general.
 */
function AnsweredQuestionCard({
  phase,
  label,
  question,
}: {
  phase: string;
  label: string;
  question: AssistanceQuestion;
}) {
  const options: [string, string][] = [
    ["a", question.option_a],
    ["b", question.option_b],
    ["c", question.option_c],
    ["d", question.option_d],
  ];
  return (
    <div className="panel wide">
      <div className="progress-bar">
        <span className="phase-chip">{label}</span>
        {phase === "study" && <span>The question you're working on</span>}
      </div>
      <QuestionStem text={question.rendered_question} />
      <div className="options">
        {options.map(([key, text]) => {
          const chosen = question.selected_option === key;
          return (
            // A `div`, not a disabled `button`. There is nothing to press here, and a row of
            // disabled buttons reads to a screen reader as four controls that are broken
            // rather than as a question that has been answered.
            <div key={key} className={`option locked ${chosen ? "chosen" : ""}`}>
              <span className="option-key" aria-hidden="true">
                {key.toUpperCase()}
              </span>
              <span className="option-text">{text}</span>
              {chosen && <span className="option-chosen-tag">you chose this</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function ExamScreen({
  phase,
  items,
  streak,
  overview,
  busy,
  assistanceQuestion = null,
  overlayOpen = false,
  error,
  onSubmit,
  onSkip,
  onFlag,
  onRecordTime,
  onFetchOverview,
  onExamViewed,
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

  // D-218. The panel is the element `handleContainerKeyDown` is bound to, so the `1`-`4` and
  // Enter shortcuts every option advertises only fire while focus is inside it. Focus was
  // routinely *not* inside it: the stage-transition overlay focuses its own Continue button
  // and that button unmounts on dismiss, and each submit unmounts the focused option - both
  // drop focus to `<body>`. Measured on staging 2026-08-07: pressing `2` on arriving at the
  // post-exam did nothing; focusing an option by hand made `2` and Enter work immediately.
  //
  // `tabIndex={-1}` makes the panel programmatically focusable without adding a tab stop.
  const panelRef = useRef<HTMLDivElement>(null);

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

  // D-218: the exam is now genuinely on screen, so start its clock. Idempotent server-side
  // (`mark_first_viewed` keeps the first report), which is what lets this fire again after a
  // mid-exam refresh without handing back the whole time limit.
  useEffect(() => {
    if (!isExamPhase || overlayOpen) return;
    onExamViewed();
  }, [isExamPhase, phase, overlayOpen, onExamViewed]);

  // AUD-F-03: restore the student's place after a mid-exam refresh. `currentDisplayOrder` is
  // this component's state, so a reload used to restore the session, the answers and the
  // read-only locks and still drop the student to question 1 - measured going from
  // "Question 3 of 10" to "Question 1 of 10". SPEC Phase 11's own "done when" is that a
  // refresh restores the exact position, and `useLearningSession`'s docstring cites that as
  // the reason the session id is persisted at all, so this was a documented requirement that
  // no test covered.
  //
  // **Derived from the overview, not persisted.** The overview already carries a server-side
  // `status` per `display_order`, and its endpoint exists for precisely this - its docstring
  // says it "lets the exam nav bar restore item statuses after a mid-exam refresh". Writing a
  // second copy of the position into `sessionStorage` would add a source of truth that can
  // disagree with the one the server already keeps.
  //
  // **One-shot per phase, and that is the whole design.** Re-applying this on every overview
  // fetch would fight the nav bar: the poll runs every 20 s, so a student who jumped back to
  // review an answered question would be silently bounced forward again within the next tick.
  // The ref stores the phase rather than a boolean so it self-clears at a phase boundary -
  // the same reason `App.tsx`'s `interactedPhase` does (AUD-F-21) - which means a genuine
  // pre -> post transition gets its own restore and correctly lands on 0, all items unseen.
  //
  // **Residual, stated because it is not what the finding's wording promises.** This restores
  // *the first item still needing an answer*, not literally the last question on screen,
  // because nothing server-side records view position: `time_spent_ms` is cumulative per item
  // and carries no ordering. They differ when a student skips forward - skip question 1,
  // answer 2 through 10, refresh, and this lands on 1 rather than 10. That is unfinished work
  // and a defensible place to land, but it is an approximation of "exact position" and a
  // future change that wants the literal one has to persist it server-side.
  const restoredPhaseRef = useRef<string | null>(null);
  useEffect(() => {
    if (!isExamPhase || !overview) return;
    if (restoredPhaseRef.current === phase) return;
    // App keeps holding the previous phase's overview after the phase moves on (the staleness
    // AUD-F-24 documents), so without this the post-exam would restore a position derived
    // from the pre-exam's item statuses.
    if (overview.phase !== phase) return;
    restoredPhaseRef.current = phase;
    if (overview.items.length === 0) return;
    const ordered = [...overview.items].sort((a, b) => a.display_order - b.display_order);
    // `skipped` and `flagged` are both still unanswered, and deliberately count as work
    // remaining - only `answered` is locked in.
    const firstUnanswered = ordered.find((item) => item.status !== "answered");
    const target = firstUnanswered ?? ordered[ordered.length - 1];
    if (target) setCurrentDisplayOrder(target.display_order);
  }, [isExamPhase, phase, overview]);

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

  // D-218: put focus back inside the panel whenever the thing that had it went away - the
  // overlay closing, or the previous question's option unmounting on submit. Without this
  // focus lands on `<body>` and the keyboard shortcuts silently stop working (see `panelRef`).
  //
  // Deliberately not while `overlayOpen`: the overlay owns focus while it is up, and stealing
  // it would drop a screen-reader user out of a dialog they have not dismissed.
  //
  // `currentItem` is in the dependency list, and has to be - which is why this effect sits
  // *below* its declaration rather than up with the others. The first deployed version keyed
  // on `currentDisplayOrder` alone and silently did nothing on arrival: before the batch
  // lands, `currentItem` is null and the early return above renders a plain `.panel` with no
  // ref, so `panelRef.current` was null when the effect ran, and nothing in the dependency
  // list changed when the real panel appeared a render later. Confirmed against the deployed
  // build 2026-08-08 - focus was restored after every submit and never on arrival.
  useEffect(() => {
    if (!isExamPhase || overlayOpen || !currentItem) return;
    const panel = panelRef.current;
    if (!panel) return;
    // Only when focus is loose. A student who has tabbed to "Flag for review" keeps it.
    const active = document.activeElement;
    if (active && active !== document.body && panel.contains(active)) return;
    panel.focus({ preventScroll: true });
  }, [isExamPhase, phase, overlayOpen, currentDisplayOrder, currentItem]);

  /**
   * The number the student is *shown*, so the live region and the visible label cannot
   * disagree about which question just happened.
   *
   * They did. `currentDisplayOrder` indexes into this batch, and in the study phase the
   * batch is one item long, so it is always 0 - while the heading reads the item's own
   * `display_order`. Measured on staging 2026-08-07: the screen said "Practice question 4"
   * and the live region announced "Answer submitted for question 1." A sighted student never
   * saw the second number; a screen-reader user got only that one.
   */
  const shownQuestionNumber = isExamPhase
    ? currentDisplayOrder + 1
    : (currentItem?.display_order ?? currentDisplayOrder) + 1;

  // D-207: `answeredSelections` is consulted alongside the server's own status, and that
  // second clause is a fix rather than a convenience.
  //
  // The overview is what makes a question read-only, and it arrives on a poll. Submitting
  // the *last* question is the one case where `handleSubmitClick` does not advance
  // (there is nowhere to advance to), so the student stays on a question whose lock has
  // not landed yet: `onFetchOverview()` is fired immediately after `onSubmit`, but the
  // answer POST is still in flight, so the overview it fetches still says `unseen`. Select
  // an option again, click Submit again, and the second request takes a 409 from
  // `flow.ensure_item_unanswered`. Measured on staging at 2026-08-06T20:12:46.914Z - the
  // eleventh `POST /answers` of a ten-question exam, 15.4 ms, rejected.
  //
  // `answeredSelections` is written synchronously in `handleSubmitClick`, so it closes
  // that window without waiting for anything. It is also already the state this screen
  // uses to redisplay a locked answer, so the two facts stay in one place.
  //
  // Kept as `||`, not a replacement: the local record is per-mount and does not survive
  // the refresh that AUD-F-03 restores from, so the server's status is still the one that
  // knows about answers from a previous page load.
  const isReadOnly =
    isExamPhase &&
    (currentOverviewItem?.status === "answered" ||
      answeredSelections[currentDisplayOrder] !== undefined);

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
    setStatusMessage(`Answer submitted for question ${shownQuestionNumber}.`);
    setSelected(null);
    if (isExamPhase) {
      // D-218: no `onFetchOverview()` here any more. It used to fire alongside the
      // un-awaited `onSubmit`, so it raced the answer POST and usually won - the overview it
      // stored still said the question was unanswered, and the 20 s poll was what eventually
      // corrected it. Measured on staging 2026-08-07: after answering questions 4 through 9
      // the navigator kept announcing each as "not yet answered" while `GET exam/overview` at
      // the same moment returned `answered`. The refresh now happens inside `submitAnswer`,
      // after the POST resolves, which is what `skipExamItem`/`flagExamItem` already did.
      //
      // The stale window was not only cosmetic: `handleFinalizeConfirm` derives
      // `hasUnanswered` from this same overview, so the submit-exam dialog could warn about
      // questions the student had just answered.
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

  // D-272. Ahead of the `!currentItem` guard on purpose: help can be open while `items`
  // still holds a question (mid-ladder) *and* while it holds nothing (the chooser) *and*
  // while it already holds the next one (after the ladder closes). All three must show the
  // same thing - the question the help is about - and only the server knows which that is.
  //
  // Rendered from inside this component rather than as a sibling the parent swaps in, for
  // AUD-F-24's reason: React reconciles by position, so swapping the element type here
  // would unmount and remount the exam screen every time a student asked for help.
  if (assistanceQuestion) {
    return (
      <AnsweredQuestionCard
        phase={phase}
        label={PHASE_LABELS[phase] ?? phase}
        question={assistanceQuestion}
      />
    );
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
  // D-213: the study phase used to show no position at all, so a student had no idea how
  // far in they were.
  //
  // It gets a count without a denominator, and that is the honest shape rather than a
  // limitation. An exam is a fixed batch, so "of N" is a fact the client already holds. A
  // study session is not: `create_study_item` assigns `display_order = len(items)`, and the
  // retry ladder adds items as the student needs them, so the total is unknown until the
  // session ends. Printing `base_problem_count` as the denominator would be worse than
  // printing nothing - it would say "3 of 5" and then serve a sixth.
  const position = isExamPhase
    ? cachedBatch
      ? `Question ${shownQuestionNumber} of ${cachedBatch.length}`
      : ""
    : `Practice question ${shownQuestionNumber}`;
  // D-241: the exam cannot be submitted while questions are still unanswered.
  //
  // **Except once the timer has run out**, and that exception is the whole design. An
  // expired exam refuses further answers (`submit_answer` -> 409 "exam time limit
  // exceeded - finalize to submit"), so blocking finalize as well would leave a student
  // who ran out of time unable to answer AND unable to submit - trapped in a screen with
  // no exit. `handleExpire` finalizes automatically and falls back to the confirmation
  // modal, and that path stays open.
  //
  // The server rule is unchanged and still the authority (S22, SPEC §5.9/§5.13): finalize
  // with unanswered items requires `confirm_unanswered`. This is a client-side policy on
  // top of it, not a replacement for it - which is why the modal still explains that
  // unanswered questions are graded incorrect when the expired path reaches it.
  const unansweredCount =
    overview?.items.filter((item) => item.status !== "answered").length ?? 0;
  const examExpired =
    overview?.remaining_seconds != null && overview.remaining_seconds <= 0;
  const submitBlocked = unansweredCount > 0 && !examExpired;

  const rememberedSelection = answeredSelections[currentDisplayOrder];

  return (
    <div className="panel wide" ref={panelRef} tabIndex={-1} onKeyDown={handleContainerKeyDown}>
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

      <QuestionStem text={currentItem.rendered_question} />

      {isReadOnly && (
        <p className="readonly-note">
          You've already answered this question - it's locked in and can't be changed.
        </p>
      )}

      <div className="options">
        {options.map(([key, text], index) => {
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
              <span className="option-key" aria-hidden="true">
                {key.toUpperCase()}
              </span>
              <span className="option-text">{text}</span>
              {/* The 1-4 shortcut has worked since S22 and nothing said so. Hidden from
                  screen readers, which announce the button's text and would otherwise
                  read a stray digit after every option. */}
              <span className="option-shortcut" aria-hidden="true">
                {index + 1}
              </span>
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
        <div className="submit-exam">
          <button
            type="button"
            className="secondary"
            disabled={busy || submitBlocked}
            onClick={() => setModalOpen(true)}
          >
            Submit exam
          </button>
          {submitBlocked && (
            <p className="submit-exam-hint">
              {unansweredCount} question{unansweredCount === 1 ? "" : "s"} left to answer. Use
              the numbers above to jump to {unansweredCount === 1 ? "it" : "them"}.
            </p>
          )}
        </div>
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

/**
 * The question itself, rendered as something a 12-year-old can actually read.
 *
 * `rendered_question` is not one sentence. For 20 of the 48 approved authored items it is
 * `context_block + "\n\n" + stem` (see `ai_pipeline.py`'s `rendered_question =
 * f"{item.context_block}\n\n{item.stem}"`), and one of them carries a markdown-style
 * bullet list inside the context block. That whole string used to go into a bare `<h1>`,
 * which `packages/ui-brand/base.css` styles at 28px/600 with `letter-spacing: -0.02em` -
 * heading typography, applied to a sixty-word word problem. HTML collapses the `\n\n` and
 * the bullet newlines to single spaces, so the setup, the list and the question all ran
 * together into one large bold block.
 *
 * Two changes, and the split is the one that matters:
 *
 *   - **Paragraphs come from the data, not from a guess.** Splitting on the blank line
 *     recovers exactly the boundary the pipeline wrote. The final paragraph is the thing
 *     being asked, so it gets the emphasis; everything before it is the scenario. An item
 *     with no context block is a single paragraph and renders as it always did.
 *   - **`white-space: pre-line`** (in App.css) keeps single newlines, which is what makes
 *     the "Offer X / Offer Y" bullet item legible instead of a run-on line.
 *
 * Still an `<h1>`: this *is* the page's heading, and screen-reader users navigating by
 * heading need it to stay one. Only its typography changes.
 */
interface Props {
  text: string;
}

export function QuestionStem({ text }: Props) {
  // `\r\n` because the string round-trips through YAML, JSON and Postgres; a lone `\r`
  // would otherwise survive into the split and produce a phantom empty paragraph.
  const paragraphs = text
    .replace(/\r\n/g, "\n")
    .split(/\n\s*\n/)
    .map((part) => part.trim())
    .filter(Boolean);

  const ask = paragraphs[paragraphs.length - 1] ?? text;
  const setup = paragraphs.slice(0, -1);

  return (
    <h1 className="question-stem">
      {setup.map((paragraph, index) => (
        <span key={index} className="question-setup">
          {paragraph}
        </span>
      ))}
      <span className="question-ask">{ask}</span>
    </h1>
  );
}

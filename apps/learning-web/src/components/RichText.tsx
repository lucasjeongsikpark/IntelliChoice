import { tokenize } from "../lib/markdown";

/**
 * Renders the tutor's `**bold**` and `` `code` `` as formatting rather than as literal
 * asterisks and backticks. Parsing lives in `lib/markdown.ts`; see its header for why this
 * is a hand-rolled subset and not a Markdown dependency.
 *
 * Everything below renders as text nodes, so nothing here can turn model output into an
 * element - there is no injection surface to sanitise.
 */

interface Props {
  text: string;
  /**
   * How many characters of the *rendered* text to show, for the progressive reveal. The
   * budget is spent across tokens in order, so markup appears already formatted as it is
   * revealed rather than as `**partial` that reformats when the closing delimiter lands.
   * Omitted means "all of it".
   */
  maxChars?: number;
}

export function RichText({ text, maxChars }: Props) {
  const tokens = tokenize(text);
  let budget = maxChars ?? Number.POSITIVE_INFINITY;

  return (
    <>
      {tokens.map((token, index) => {
        if (budget <= 0) return null;
        const shown = token.text.length <= budget ? token.text : token.text.slice(0, budget);
        budget -= token.text.length;
        if (token.bold) return <strong key={index}>{shown}</strong>;
        if (token.code) return <code key={index}>{shown}</code>;
        // A plain fragment: line breaks are honoured by `white-space: pre-line` on the
        // bubble rather than by inserting `<br>` elements, so the text stays selectable and
        // copyable as one run.
        return <span key={index}>{shown}</span>;
      })}
    </>
  );
}

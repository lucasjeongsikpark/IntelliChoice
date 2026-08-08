import { tokenize } from "../lib/markdown";

/**
 * Renders an answer's `**bold**` and `` `code` `` as formatting rather than as literal
 * asterisks and backticks, and preserves its line breaks. Parsing lives in
 * `lib/markdown.ts`; see its header for why this is a hand-rolled subset, and why it is
 * duplicated from `learning-web` rather than shared.
 *
 * Everything below renders as text nodes, so nothing here can turn model output into an
 * element - there is no injection surface to sanitise. That matters more in this app than in
 * the learning one: a Q&A answer is synthesised from retrieved document chunks, and those
 * chunks are explicitly untrusted content (the RAG system prompt says so).
 */

interface Props {
  text: string;
}

export function RichText({ text }: Props) {
  // `white-space: pre-line` on the wrapper, so the model's line breaks and the normalized
  // "• " bullets survive. Without it the branch locator's three-line answer rendered as one
  // run of text on the deployed build (D-219).
  return (
    <span style={{ whiteSpace: "pre-line" }}>
      {tokenize(text).map((token, index) => {
        if (token.bold) return <strong key={index}>{token.text}</strong>;
        if (token.code) return <code key={index}>{token.text}</code>;
        return <span key={index}>{token.text}</span>;
      })}
    </span>
  );
}

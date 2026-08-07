/**
 * The small subset of Markdown a tutor reply actually uses.
 *
 * Kept apart from the component that renders it so the parsing is directly testable and so
 * the component file exports only components (the Fast Refresh rule oxlint enforces).
 *
 * **Why not a Markdown library.** The input is model output rendered into a page a minor is
 * using. A general renderer brings links, images, and raw HTML passthrough, each of which is
 * a way for generated text to put something unreviewed in front of a student - and the
 * mitigation is a sanitiser, i.e. a second dependency guarding the first. Bold and inline
 * code are the only markup the tutor prompt can produce that reads as broken when left raw.
 */

export interface Token {
  text: string;
  bold: boolean;
  code: boolean;
}

/**
 * Split on `**bold**` and `` `code` `` in one pass.
 *
 * Unpaired delimiters stay literal rather than being swallowed: a reply containing a stray
 * `*` should show the `*`, not lose the rest of the sentence to an unterminated match.
 */
export function tokenize(text: string): Token[] {
  const tokens: Token[] = [];
  const pattern = /\*\*([\s\S]+?)\*\*|`([^`]+?)`/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      tokens.push({ text: text.slice(lastIndex, match.index), bold: false, code: false });
    }
    if (match[1] !== undefined) tokens.push({ text: match[1], bold: true, code: false });
    else tokens.push({ text: match[2] ?? "", bold: false, code: true });
    lastIndex = pattern.lastIndex;
  }
  if (lastIndex < text.length) {
    tokens.push({ text: text.slice(lastIndex), bold: false, code: false });
  }
  return tokens;
}

/** The visible length of `text` once markup delimiters are removed. */
export function renderedLength(text: string): number {
  return tokenize(text).reduce((total, token) => total + token.text.length, 0);
}

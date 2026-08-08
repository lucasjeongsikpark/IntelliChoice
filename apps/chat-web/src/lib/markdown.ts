/**
 * The small subset of Markdown a Q&A answer actually uses.
 *
 * **Ported from `apps/learning-web/src/lib/markdown.ts` (D-219), deliberately duplicated
 * rather than shared.** D-217 built this for the learning app and the chat app never got it,
 * so `**Tutor Onboarding Procedure:**` rendered with its asterisks on the deployed build
 * (walked 2026-08-08) and a `- ` list from the branch locator collapsed onto one line. The
 * two apps have no shared TypeScript package and adding one means Vite/tsconfig wiring in
 * both for ~100 lines; the cost of duplication is that a future fix has to land twice, which
 * is the trade accepted here. If a third consumer appears, that is the signal to extract it.
 *
 * **Why not a Markdown library.** The input is model output rendered into a page a minor may
 * be reading. A general renderer brings links, images, and raw HTML passthrough, each of
 * which is a way for generated text to put something unreviewed in front of a user - and the
 * mitigation is a sanitiser, i.e. a second dependency guarding the first.
 */

export interface Token {
  text: string;
  bold: boolean;
  code: boolean;
}

/**
 * Reshape the two block-level constructs a model still occasionally emits (despite the
 * prompt now asking for plain text) into something that reads cleanly rather than as literal
 * syntax - a `#`/`##` heading marker becomes just its text, and a `-`/`*`/`+` bullet becomes
 * a real "• " glyph. Line-based and text-only, so it stays inside this file's injection-safe
 * guarantee: it only ever reshapes text, never introduces markup.
 *
 * The bullet case is not hypothetical here even with a perfectly obedient model - the branch
 * locator's answer is built deterministically in `_format_branch_locator_answer` and uses
 * "- " lines.
 */
export function normalizeBlockMarkup(text: string): string {
  return text
    .split("\n")
    .map((line) => line.replace(/^\s{0,3}#{1,6}\s+/, "").replace(/^(\s*)[-*+]\s+/, "$1• "))
    .join("\n");
}

/**
 * Split on `**bold**` and `` `code` `` in one pass.
 *
 * Unpaired delimiters stay literal rather than being swallowed: an answer containing a stray
 * `*` should show the `*`, not lose the rest of the sentence to an unterminated match.
 */
export function tokenize(text: string): Token[] {
  const tokens: Token[] = [];
  const normalized = normalizeBlockMarkup(text);
  const pattern = /\*\*([\s\S]+?)\*\*|`([^`]+?)`/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(normalized)) !== null) {
    if (match.index > lastIndex) {
      tokens.push({ text: normalized.slice(lastIndex, match.index), bold: false, code: false });
    }
    if (match[1] !== undefined) tokens.push({ text: match[1], bold: true, code: false });
    else tokens.push({ text: match[2] ?? "", bold: false, code: true });
    lastIndex = pattern.lastIndex;
  }
  if (lastIndex < normalized.length) {
    tokens.push({ text: normalized.slice(lastIndex), bold: false, code: false });
  }
  return tokens;
}

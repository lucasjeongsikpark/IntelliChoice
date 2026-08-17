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
  /** D-381: `*emphasis*`, which reached students as literal asterisks. See `tokenize`. */
  italic: boolean;
}

/**
 * D-217: reshape the two block-level Markdown constructs a model still occasionally emits
 * (despite the prompt now asking for plain text) into something that reads cleanly rather
 * than as literal syntax - a `#`/`##` heading marker becomes just its text, and a `-`/`*`/
 * `+` bullet becomes a real "• " glyph. Line-based and text-only, so it stays inside this
 * file's injection-safe guarantee (it only ever reshapes text, never introduces markup).
 * Leaves `**bold**` and `` `code` `` for `tokenize` below; leaves numbered lists ("1. ")
 * alone, since those already read fine.
 */
export function normalizeBlockMarkup(text: string): string {
  return text
    .split("\n")
    .map((line) =>
      line.replace(/^\s{0,3}#{1,6}\s+/, "").replace(/^(\s*)[-*+]\s+/, "$1• "),
    )
    .join("\n");
}

/**
 * Split on `**bold**`, `*emphasis*` and `` `code` `` in one pass.
 *
 * Unpaired delimiters stay literal rather than being swallowed: a reply containing a stray
 * `*` should show the `*`, not lose the rest of the sentence to an unterminated match.
 *
 * **`*emphasis*` was added in D-381**, because the model emits it and a student was reading
 * the asterisks. The prompt asks for plain text and mostly gets it, which is why only bold
 * and code were handled - but "mostly" is the whole problem: the failure lands in a hint, in
 * front of a child, at the moment they are already stuck. Rendering it costs one alternation
 * and stays inside this file's text-only guarantee.
 *
 * Order matters and is load-bearing: the `**` alternative must precede the `*` one, or
 * `**bold**` matches as an emphasis containing an empty string. The single-asterisk pattern
 * also refuses newlines and asterisks inside, so a bullet line that survived
 * `normalizeBlockMarkup` cannot pair with a later `*` halfway down a paragraph.
 */
export function tokenize(text: string): Token[] {
  const tokens: Token[] = [];
  text = normalizeBlockMarkup(text);
  const pattern = /\*\*([\s\S]+?)\*\*|\*([^*\n]+?)\*|`([^`]+?)`/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      tokens.push({
        text: text.slice(lastIndex, match.index),
        bold: false,
        code: false,
        italic: false,
      });
    }
    if (match[1] !== undefined) {
      tokens.push({ text: match[1], bold: true, code: false, italic: false });
    } else if (match[2] !== undefined) {
      tokens.push({ text: match[2], bold: false, code: false, italic: true });
    } else {
      tokens.push({ text: match[3] ?? "", bold: false, code: true, italic: false });
    }
    lastIndex = pattern.lastIndex;
  }
  if (lastIndex < text.length) {
    tokens.push({ text: text.slice(lastIndex), bold: false, code: false, italic: false });
  }
  return tokens;
}

/** The visible length of `text` once markup delimiters are removed. */
export function renderedLength(text: string): number {
  return tokenize(text).reduce((total, token) => total + token.text.length, 0);
}

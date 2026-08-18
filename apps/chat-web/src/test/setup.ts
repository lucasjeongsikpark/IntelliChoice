/**
 * D-413: what every component test in this app needs before it can be trusted.
 *
 * **`cleanup` is not optional here, and its absence is silent.** `@testing-library/react` registers
 * its own `afterEach(cleanup)` only when the test runner exposes globals, and this project's vitest
 * config deliberately does not (`globals: true` is off; the tests import `expect`/`test` explicitly).
 * Without it every `render` stays in `document.body` for the rest of the file, so `screen.getAllBy*`
 * matches earlier tests' markup. Measured while writing the first component test: a screen with two
 * Stop buttons reported three, and the extra one belonged to the previous test.
 *
 * A file-by-file `afterEach(cleanup)` would work and would be forgotten exactly once.
 */

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(cleanup);

/**
 * jsdom implements no scrolling at all: `Element.prototype.scrollTo` does not exist, so any
 * component that keeps a transcript pinned to the bottom throws before it can be asserted on.
 * A no-op is the right fake - scroll position is not a property these tests are about.
 */
Element.prototype.scrollTo = () => {};

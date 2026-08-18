/**
 * D-413: the same component-test setup chat-web has, in place before the first component test here.
 *
 * **`cleanup` is not optional and its absence is silent.** `@testing-library/react` registers its
 * own `afterEach(cleanup)` only when the runner exposes globals, and this project's vitest config
 * deliberately does not (`globals: true` is off; tests import `expect`/`test` explicitly). Without
 * it every `render` stays in `document.body` for the rest of the file and `screen.getAllBy*` matches
 * markup left behind by earlier tests. That was measured in chat-web while writing this project's
 * first component test: a screen with two Stop buttons reported three.
 *
 * This app has no component test yet, and the file exists anyway for D-347's reason - the single
 * most repeated defect shape in this project is a fix that landed in one frontend and not the other.
 * The next person to write a component test here should inherit a correct harness rather than
 * rediscover a leaking one.
 */

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(cleanup);

/**
 * jsdom implements no scrolling at all: `Element.prototype.scrollTo` does not exist, so any
 * component that pins a scroll container throws before it can be asserted on. A no-op is the right
 * fake - scroll position is not a property these tests are about.
 */
Element.prototype.scrollTo = () => {};

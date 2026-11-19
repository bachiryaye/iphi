import "@testing-library/jest-dom/vitest";

import { cleanup, configure } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

// The 1 s default is exceeded on a cold or loaded runner, where the first
// render of a page also pays for module transforms.
configure({ asyncUtilTimeout: 5000 });

// jsdom has no layout: scrolling evidence rows into view is a no-op in tests.
Element.prototype.scrollIntoView = () => undefined;

// jsdom does not measure layout; browser tests exercise the actual graph observer.
beforeEach(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe = vi.fn();
      unobserve = vi.fn();
      disconnect = vi.fn();
    },
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

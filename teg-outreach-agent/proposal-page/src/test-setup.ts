import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// jsdom has no IntersectionObserver — a no-op is fine (charts start in their
// "not yet revealed" state, which the tests assert against).
if (!("IntersectionObserver" in globalThis)) {
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      observe() {}
      disconnect() {}
      unobserve() {}
    },
  );
}

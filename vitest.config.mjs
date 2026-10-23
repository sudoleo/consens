import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/js/**/*.test.mjs"],
    // Each test builds its own jsdom through tests/js/helpers/appWindow.mjs, so
    // the default node environment is enough here and keeps the global scope of
    // one test out of the next one's way.
    environment: "node",
    // Every test file gets its own child process, not a worker thread. Under
    // Node 18 on Windows, terminating a worker right after a file that had
    // worked many jsdom windows hard (dompurify-vendor) at times never
    // finished, and the run hung after its summary; a process always ends.
    pool: "forks",
    globals: false,
    restoreMocks: true,
  },
});

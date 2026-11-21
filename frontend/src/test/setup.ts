import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";
import { resetMockState } from "@/mocks/handlers";

afterEach(() => {
  cleanup();
  resetMockState();
});

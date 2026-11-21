import assert from "node:assert/strict";
import { test } from "node:test";
import { deepEqualJson } from "./openapi-equal.mjs";

test("deepEqualJson ignores object key order", () => {
  assert.equal(deepEqualJson({ a: 1, b: { c: 2, d: 3 } }, { b: { d: 3, c: 2 }, a: 1 }), true);
});

test("deepEqualJson detects value and structure differences", () => {
  assert.equal(deepEqualJson({ a: 1 }, { a: 2 }), false);
  assert.equal(deepEqualJson({ a: 1 }, { a: 1, b: 2 }), false);
  assert.equal(deepEqualJson([1, 2], [2, 1]), false);
  assert.equal(deepEqualJson([1, 2], [1, 2]), true);
});

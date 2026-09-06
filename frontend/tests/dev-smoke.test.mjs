import assert from "node:assert/strict";
const origin = process.env.FRONTEND_TEST_URL || "http://127.0.0.1:3000";
const response = await fetch(origin);
assert.equal(response.status, 200);
const html = await response.text();
assert.match(html, /class="app-shell"/);
assert.match(html, /id="contract-file"/);
assert.doesNotMatch(html, /createContext is not a function|Internal Server Error/);
const entry = html.match(/rel="modulepreload" href="([^"]+)"/);
assert.ok(entry, "Browser entry must be present");
for (const path of [entry[1], "/app/page.tsx", "/app/globals.css"]) {
  const asset = await fetch(new URL(path, origin));
  assert.equal(asset.status, 200, path);
  const body = await asset.text();
  assert.doesNotMatch(body, /createContext is not a function|Internal Server Error/);
}
console.log("PASS: rendered application, browser entry, page module and CSS return 200");

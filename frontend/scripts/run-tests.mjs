import { testRenderedHtml } from "../tests/rendered-html.test.mjs";
import { testUiComponents } from "../tests/ui-components.test.mjs";

const tests = [
  ["rendered html", testRenderedHtml],
  ["ui components", testUiComponents],
];

let failed = 0;

for (const [name, fn] of tests) {
  try {
    await fn();
    console.log(`ok - ${name}`);
  } catch (error) {
    failed += 1;
    console.error(`not ok - ${name}`);
    console.error(error);
  }
}

if (failed > 0) {
  process.exitCode = 1;
}

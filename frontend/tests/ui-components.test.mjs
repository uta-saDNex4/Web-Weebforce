import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));

async function readCssTree(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const contents = await Promise.all(
    entries.map(async (entry) => {
      const entryPath = path.join(directory, entry.name);
      if (entry.isDirectory()) {
        return readCssTree(entryPath);
      }
      return entry.name.endsWith(".css") ? readFile(entryPath, "utf8") : "";
    }),
  );
  return contents.join("\n");
}

export async function testUiComponents() {
  const css = await readCssTree(path.join(root, "dist"));

  assert.match(css, /--tw-enter-opacity/);
  assert.match(css, /scrollbar-width:\s*thin/);
  assert.match(css, /scrollbar-width:\s*none/);
  assert.match(css, /scrollbar-gutter:\s*stable/);
  assert.match(css, /scroll-fade-reveal-b/);
  assert.match(css, /mask-image:/);
  assert.match(css, /tw-shimmer/);
  assert.match(css, /prefers-reduced-motion:\s*reduce/);

  const progressSource = await readFile(
    path.join(root, "components/ui/progress.tsx"),
    "utf8",
  );
  assert.match(progressSource, /data-slot="progress"/);
  assert.match(progressSource, /ProgressPrimitive\.Root/);
  assert.match(progressSource, /ProgressPrimitive\.Indicator/);
  assert.match(
    progressSource,
    /translateX\(-\$\{100 - \(value \?\? 0\)\}%\)/,
  );

  const chartSource = await readFile(
    path.join(root, "components/ui/chart.tsx"),
    "utf8",
  );
  assert.match(chartSource, /\[data-chart=\$\{id\}\]/);
  assert.match(chartSource, /\(prefers-color-scheme: dark\)/);
  assert.match(chartSource, /@media \$\{media\}/);
  assert.doesNotMatch(chartSource, /\.dark/);

  const sidebarSource = await readFile(
    path.join(root, "components/ui/sidebar.tsx"),
    "utf8",
  );
  assert.match(sidebarSource, /const width = "70%"/);
  assert.match(sidebarSource, /--skeleton-width": width/);
  assert.match(sidebarSource, /data-sidebar="menu-skeleton"/);
}

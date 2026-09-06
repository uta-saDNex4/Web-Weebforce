import { spawnSync } from "node:child_process";
import { resolve } from "node:path";

// Propagate actual build failures; never substitute a placeholder application.
const cli = resolve("node_modules", "vinext", "dist", "cli.js");
const result = spawnSync(process.execPath, [cli, "build"], { stdio: "inherit" });
if (result.error) console.error(result.error.message);
process.exit(result.status ?? 1);

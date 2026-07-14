import { copyFile, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = resolve(projectRoot, "public", "_headers");
const destination = resolve(projectRoot, ".open-next", "assets", "_headers");

await mkdir(dirname(destination), { recursive: true });
await copyFile(source, destination);

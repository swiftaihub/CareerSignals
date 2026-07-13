import { readdir, readFile } from "node:fs/promises";
import { join, relative } from "node:path";

const roots = process.argv.slice(2).filter((value) => !value.startsWith("--"));
const apiOrigin = process.env.API_BASE_URL?.trim();
const forbidden = [
  "PASSWORD_RECOVERY_COOKIE_SECRET",
  "SUPABASE_SERVICE_ROLE_KEY",
  "SUPABASE_SECRET_KEY",
  "DATABASE_URL",
  "MOTHERDUCK_TOKEN",
  "DEMO_SESSION_SECRET",
  "CLOUDFLARE_API_TOKEN",
  "ORACLE_SSH_PRIVATE_KEY"
];
if (apiOrigin) forbidden.push(apiOrigin);

let checked = 0;
let failed = false;

async function walk(root, current = root) {
  let entries;
  try {
    entries = await readdir(current, { withFileTypes: true });
  } catch (error) {
    if (error?.code === "ENOENT") return;
    throw error;
  }
  for (const entry of entries) {
    const path = join(current, entry.name);
    if (entry.isSymbolicLink()) {
      console.error(`Client bundle contains an unsupported symbolic link: ${relative(process.cwd(), path)}.`);
      failed = true;
      continue;
    }
    if (entry.isDirectory()) {
      await walk(root, path);
      continue;
    }
    if (!entry.isFile()) continue;
    const content = await readFile(path);
    checked += 1;
    for (const marker of forbidden) {
      if (marker && content.includes(Buffer.from(marker))) {
        console.error(`Client bundle contains forbidden marker in ${relative(process.cwd(), path)}.`);
        failed = true;
        break;
      }
    }
  }
}

for (const root of roots.length ? roots : [".next/static", ".open-next/assets"]) {
  await walk(root);
}

if (!checked) {
  console.error("No client bundle files were found to scan.");
  process.exit(1);
}
if (failed) process.exit(1);
console.log(`Client bundle scan passed (${checked} assets checked byte-for-byte).`);

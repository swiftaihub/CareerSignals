import { createHash } from "node:crypto";
import { lstat, readFile, readdir, readlink } from "node:fs/promises";
import { join, relative, sep } from "node:path";

const [target = "web", expectedSha = ""] = process.argv.slice(2);
const manifest = JSON.parse(await readFile("SOURCE_MANIFEST.json", "utf8"));
const errors = [];

if (manifest.source_repository !== "swiftaihub/CareerSignals") {
  errors.push("unexpected source_repository");
}
if (manifest.deployment_target !== target) {
  errors.push("unexpected deployment_target");
}
if (!/^[0-9a-f]{40}$/i.test(manifest.source_commit_sha ?? "")) {
  errors.push("source_commit_sha must be a full Git SHA");
}
if (expectedSha && !/^[0-9a-f]{40}$/.test(expectedSha)) {
  errors.push("expected source SHA must be a full lowercase Git SHA");
}
if (expectedSha && manifest.source_commit_sha.toLowerCase() !== expectedSha.toLowerCase()) {
  errors.push("source_commit_sha does not match the manually confirmed SHA");
}
if (manifest.source_branch !== "main") {
  errors.push("production deployment requires a canonical main source");
}
if (Number.isNaN(Date.parse(manifest.generated_at_utc ?? ""))) {
  errors.push("generated_at_utc is invalid");
}

const actualFiles = await inventory(process.cwd());
if (manifest.file_count !== actualFiles.length) {
  errors.push("file_count does not match generated content");
}
if (JSON.stringify(manifest.files) !== JSON.stringify(actualFiles)) {
  errors.push("file inventory does not match generated content");
}
const contentDigest = sha256(Buffer.from(JSON.stringify(actualFiles)));
if (manifest.content_digest_sha256 !== contentDigest) {
  errors.push("content digest does not match generated content");
}

if (errors.length) {
  for (const error of errors) console.error(`Manifest validation failed: ${error}`);
  process.exit(1);
}

console.log(`Validated ${target} source manifest for ${manifest.source_commit_sha}.`);

async function inventory(root) {
  const entries = [];
  await walk(root, root, entries);
  entries.sort((left, right) => left.path < right.path ? -1 : left.path > right.path ? 1 : 0);
  return entries;
}

async function walk(root, current, entries) {
  for (const entry of await readdir(current, { withFileTypes: true })) {
    if (current === root && entry.name === ".git") continue;
    if (current === root && entry.name === "SOURCE_MANIFEST.json") continue;
    const path = join(current, entry.name);
    const relativePath = relative(root, path).split(sep).join("/");
    const metadata = await lstat(path);
    if (metadata.isDirectory()) {
      await walk(root, path, entries);
      continue;
    }
    const kind = metadata.isSymbolicLink() ? "symlink" : "file";
    const content = kind === "symlink"
      ? Buffer.from(await readlink(path), "utf8")
      : await readFile(path);
    entries.push({
      kind,
      path: relativePath,
      sha256: sha256(content),
      size: content.length
    });
  }
}

function sha256(content) {
  return createHash("sha256").update(content).digest("hex");
}

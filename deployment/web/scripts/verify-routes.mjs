import { readFile } from "node:fs/promises";

const configPath = process.argv[2] || "wrangler.jsonc";
const source = await readFile(configPath, "utf8");
const expectedWorkerName = "careersignals-web";
const requiredRoutes = [
  {
    pattern: "jobs.swiftaihub.com/careersignals",
    zone_name: "swiftaihub.com"
  },
  {
    pattern: "jobs.swiftaihub.com/careersignals/*",
    zone_name: "swiftaihub.com"
  }
];

let config;
try {
  config = JSON.parse(source);
} catch {
  console.error("wrangler.jsonc must be strict JSON so production route validation cannot be bypassed by comments.");
  process.exit(1);
}

if (config.name !== expectedWorkerName) {
  console.error(`Worker name must be exactly ${expectedWorkerName}.`);
  process.exit(1);
}

const actualRoutes = Array.isArray(config.routes) ? config.routes : [];
const canonicalize = (route) => JSON.stringify({
  pattern: route?.pattern,
  zone_name: route?.zone_name
});
const actual = actualRoutes.map(canonicalize).sort();
const expected = requiredRoutes.map(canonicalize).sort();
if (JSON.stringify(actual) !== JSON.stringify(expected)) {
  console.error("Worker routes must be exactly the two approved /careersignals routes in the swiftaihub.com zone.");
  process.exit(1);
}

console.log(`Worker ${expectedWorkerName} is limited to /careersignals and its descendants.`);

import { createReadStream, existsSync, readFileSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join } from "node:path";

const ROOT = join(process.cwd(), "..", "app", "static", "proposal");
const FIXTURE = readFileSync(join(process.cwd(), "src", "__fixtures__", "proposal.json"), "utf8");
const TYPES = {
  ".js": "text/javascript",
  ".css": "text/css",
  ".html": "text/html",
  ".svg": "image/svg+xml",
  ".json": "application/json",
  ".map": "application/json",
};

createServer((req, res) => {
  const url = new URL(req.url, "http://x");
  if (url.pathname === "/health") return res.end("ok");

  if (url.pathname.endsWith(".json") && url.pathname.startsWith("/proposals/")) {
    res.setHeader("content-type", "application/json");
    return res.end(FIXTURE);
  }

  if (url.pathname.startsWith("/p/")) {
    res.setHeader("content-type", "text/html");
    return res.end(readFileSync(join(ROOT, "index.html"), "utf8"));
  }

  const rel = url.pathname.replace(/^\/static\/proposal\//, "");
  const file = join(ROOT, rel);
  if (existsSync(file) && !file.endsWith("/")) {
    res.setHeader("content-type", TYPES[extname(file)] ?? "application/octet-stream");
    return createReadStream(file).pipe(res);
  }

  res.statusCode = 404;
  res.end("nf");
}).listen(4178);

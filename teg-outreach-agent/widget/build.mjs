import * as esbuild from "esbuild";

await esbuild.build({
  entryPoints: ["src/index.ts"],
  bundle: true,
  format: "iife",
  globalName: "TegOutreach",
  outfile: "dist/teg-outreach-widget.js",
  minify: true,
  target: ["es2019"],
});
console.log("built dist/teg-outreach-widget.js");

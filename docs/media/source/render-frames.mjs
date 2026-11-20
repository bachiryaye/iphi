import { bundle } from "@remotion/bundler";
import {
  openBrowser,
  renderStill,
  selectComposition,
} from "@remotion/renderer";
import { mkdir, readFile } from "node:fs/promises";
import { resolve } from "node:path";

const chapters = JSON.parse(await readFile("chapters.json", "utf8"));
console.log("Bundling the chapter frames.");
const serveUrl = await bundle({
  entryPoint: resolve("Frame.tsx"),
  enableCaching: false,
  onProgress: (progress) => console.log(`Bundle ${progress}%`),
});
const browser = await openBrowser("chrome", {
  browserExecutable: process.env.IPHI_VIDEO_CHROME,
  chromeMode: "chrome-for-testing",
});

try {
  await mkdir("frames", { recursive: true });
  for (let index = 0; index < chapters.length; index++) {
    const inputProps = { index };
    const composition = await selectComposition({
      serveUrl,
      id: "Chapter",
      inputProps,
      puppeteerInstance: browser,
    });
    await renderStill({
      serveUrl,
      composition,
      inputProps,
      puppeteerInstance: browser,
      output: resolve(
        "frames",
        `chapter-${String(index + 1).padStart(2, "0")}.png`,
      ),
    });
    console.log(`Chapter ${index + 1}/${chapters.length} rendered.`);
  }
} finally {
  await browser.close({ silent: true });
}

// Capture screenshots of the running app (desktop + mobile, both themes).
//   node scripts/shots.mjs
import fs from "fs";
import { chromium } from "playwright";

const BASE = process.env.WEB || "http://localhost:3000";
const API = process.env.API || "http://localhost:8090";
const TOKEN = process.env.TOKEN || "SINA0994";
const OUT = "shots";
fs.mkdirSync(OUT, { recursive: true });

async function getJson(path) {
  try {
    const r = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${TOKEN}` } });
    return await r.json();
  } catch {
    return null;
  }
}

const tasks = (await getJson("/api/tasks")) || [];
const reviews = (await getJson("/api/reviews")) || [];
const taskId = tasks[0]?.id;
const reviewId = (reviews.find((r) => r.status === "completed") || reviews[0])?.id;

function targets() {
  const t = [["dashboard", "/"], ["settings", "/settings"]];
  if (taskId) t.push(["edit", `/tasks/${taskId}/edit`], ["submit", `/tasks/${taskId}/submit`]);
  if (reviewId) t.push(["report", `/reviews/${reviewId}`]);
  return t;
}

const browser = await chromium.launch();

async function capture(prefix, viewport, themes) {
  for (const theme of themes) {
    const ctx = await browser.newContext({ viewport, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    await page.addInitScript(
      ([t, th]) => {
        localStorage.setItem("operator_token", t);
        localStorage.setItem("theme", th);
      },
      [TOKEN, theme],
    );
    for (const [name, path] of targets()) {
      try {
        await page.goto(BASE + path, { waitUntil: "networkidle", timeout: 20000 });
        await page.waitForTimeout(1300);
        await page.screenshot({ path: `${OUT}/${prefix}-${theme}-${name}.png`, fullPage: true });
        console.log(`shot ${prefix}-${theme}-${name}`);
      } catch (e) {
        console.log(`FAIL ${prefix}-${theme}-${name}: ${e.message}`);
      }
    }
    await ctx.close();
  }
}

await capture("d", { width: 1440, height: 900 }, ["dark", "light"]);
await capture("m", { width: 390, height: 844 }, ["dark", "light"]);

await browser.close();
console.log("done");

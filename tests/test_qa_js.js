// QA 27.11.2026: rotating a page in Pages turns an inserted image with it: node tests/test_qa_js.js
const fs = require("fs");
const src = fs.readFileSync(__dirname + "/../app/static/app.js", "utf8");
const m = src.match(/function rotObj\(o, W, H, by\) \{[\s\S]*?\n\}\n/);
const rotObj = new Function(m[0] + "; return rotObj;")();
const o = { type: "image", x: 100, y: 100, w: 200, h: 100, angle: 0 };
rotObj(o, 600, 800, 90);   // page 600 wide, 800 high, turned clockwise
const ok = o.w === 200 && o.h === 100 && o.angle === 90 && o.x + o.w / 2 === 800 - 150 && o.y + o.h / 2 === 200;
console.log(ok ? "ok   image turns with the page" : "FAIL image turns with the page " + JSON.stringify(o));
process.exit(ok ? 0 : 1);

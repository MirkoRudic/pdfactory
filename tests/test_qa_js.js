// QA 27.11.2026: rotating a page in Pages turns an inserted image with it: node tests/test_qa_js.js
const fs = require("fs");
const src = fs.readFileSync(__dirname + "/../app/static/app.js", "utf8");
const m = src.match(/function rotObj\(o, W, H, by\) \{[\s\S]*?\n\}\n/);
const rotObj = new Function(m[0] + "; return rotObj;")();
const o = { type: "image", x: 100, y: 100, w: 200, h: 100, angle: 0 };
rotObj(o, 600, 800, 90);   // page 600 wide, 800 high, turned clockwise
const ok = o.w === 200 && o.h === 100 && o.angle === 90 && o.x + o.w / 2 === 800 - 150 && o.y + o.h / 2 === 200;
console.log(ok ? "ok   image turns with the page" : "FAIL image turns with the page " + JSON.stringify(o));

// QA 27.11.2026: deleting the page an "on all pages" image was inserted on keeps the image
const m2 = src.match(/function dropPages\(d, uids\) \{[\s\S]*?\n\}\n/);
const dropPages = new Function(m2[0] + "; return dropPages;")();
const d = { items: [{ uid: "a" }, { uid: "b" }, { uid: "c" }],
            objects: { a: [{ type: "image", allPages: true, img: "logo" }, { type: "text", t: "only on a" }], b: [{ type: "text" }] } };
dropPages(d, ["a"]);
const ok2 = d.items.length === 2 && !d.objects.a && d.objects.b.length === 2 && d.objects.b[1].img === "logo";
console.log(ok2 ? "ok   image on all pages survives deleting its page" : "FAIL image on all pages " + JSON.stringify(d));
process.exit(ok && ok2 ? 0 : 1);

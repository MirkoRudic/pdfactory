"""Flow check: edit -> save -> file has the edits; pages: rotate/delete/undo; OCR on a scanned PDF."""
import json, shutil, sys, urllib.request
import pymupdf
from playwright.sync_api import sync_playwright
url, work, out = sys.argv[1:4]
shutil.copy(f"{work}/ugovor.pdf", f"{work}/flow.pdf"); shutil.copy(f"{work}/skenirano.pdf", f"{work}/flow_sken.pdf")
def post(p, b): urllib.request.urlopen(urllib.request.Request(url + p, json.dumps(b).encode(), {"Content-Type": "application/json"}, method="POST"))
errors = []
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/usr/bin/google-chrome")
    pg = b.new_page(viewport={"width": 1366, "height": 768})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(url); pg.evaluate("localStorage.clear()"); pg.reload(); pg.wait_for_timeout(800)
    post("api/open-external", {"path": f"{work}/flow.pdf"}); pg.wait_for_timeout(2000)
    pg.click('[data-mode="edit"]'); pg.wait_for_timeout(800)
    pg.click("text=Dodaj tekst")
    box = pg.locator(".page").first.bounding_box()
    pg.mouse.click(box["x"] + 200, box["y"] + 400); pg.keyboard.type("Potpisano ćirilica ЖЏ"); pg.keyboard.press("Escape")
    pg.click("text=Istakni"); pg.mouse.move(box["x"] + 100, box["y"] + 90); pg.mouse.down(); pg.mouse.move(box["x"] + 400, box["y"] + 120, steps=4); pg.mouse.up()
    pg.click("text=Popuni formular"); pg.wait_for_timeout(700)
    pg.locator("input.fld").first.fill("Mirko Rudić"); pg.locator("input.fld").first.press("Tab")
    pg.click("#bUndo"); pg.wait_for_timeout(200); pg.click("#bRedo")
    pg.click("#bSave"); pg.wait_for_timeout(2500)
    pg.screenshot(path=f"{out}/f1_saved.png")
    d = pymupdf.open(f"{work}/flow.pdf"); t = d[0].get_text()
    print("saved text has edit:", "Potpisano" in t, "ЖЏ" in t, "| form:", [w.field_value for w in d[0].widgets()])
    # pages: rotate first, delete second, undo delete
    pg.click('[data-mode="pages"]'); pg.wait_for_timeout(800)
    cells = pg.locator(".ocell"); cells.nth(0).click(); pg.click("#oRotR"); pg.wait_for_timeout(300)
    cells.nth(1).click(); pg.click("#oDel"); pg.wait_for_timeout(300)
    n_after_del = pg.locator(".ocell").count()
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(300)
    print("pages after delete:", n_after_del, "after undo:", pg.locator(".ocell").count())
    # drag page 3 before page 1
    pg.locator(".ocell").nth(2).drag_to(pg.locator(".ocell").nth(0), target_position={"x": 10, "y": 60}); pg.wait_for_timeout(500)
    pg.screenshot(path=f"{out}/f2_pages.png")
    pg.click("#bSave"); pg.wait_for_timeout(2500)
    d = pymupdf.open(f"{work}/flow.pdf")
    print("after pages save:", d.page_count, [p.rotation for p in d], d[0].get_text()[:30].replace("\n", " "))
    # OCR
    post("api/open-external", {"path": f"{work}/flow_sken.pdf"}); pg.wait_for_timeout(2000)
    pg.click('[data-mode="read"]'); pg.wait_for_timeout(800)
    pg.screenshot(path=f"{out}/f3_scan.png")
    pg.click("text=Prepoznaj tekst"); pg.wait_for_timeout(9000)
    pg.screenshot(path=f"{out}/f4_ocr.png")
    pg.fill("#q", "snimanje"); pg.press("#q", "Enter"); pg.wait_for_timeout(1000)
    print("search after ocr:", pg.inner_text("#qn"))
    pg.click("#bSave"); pg.wait_for_timeout(2000)
    print("ocr saved:", pymupdf.open(f"{work}/flow_sken.pdf")[0].get_text().strip()[:40])
    pg.click("#bQuit"); pg.wait_for_timeout(500); pg.screenshot(path=f"{out}/f5_quit.png")
    b.close()
print("errors:", errors)

// VAJB dialog.js 1.1 - replaces alert/confirm/prompt with the app's own dialog (RULES.md UI4, UI5).
// Needs base.css. Usage:
//   if (await vd.confirm("Obrisati projekat?", {ok: "Obriši", danger: true})) ...
//   await vd.message("Sačuvano.")
//   const name = await vd.prompt("Naziv", {value: "Novi"})   // null = cancelled
// Esc and click outside = cancel. Focus is trapped and returned. Each call builds its own dialog (UI5).
(function () {
  function open({ text, buttons, input }) {
    return new Promise((resolve) => {
      const prevFocus = document.activeElement;
      const ov = document.createElement("div");
      ov.className = "vd-overlay";
      ov.innerHTML = '<div class="vd-card" role="dialog" aria-modal="true"><p class="vd-text"></p><div class="vd-buttons"></div></div>';
      const card = ov.firstChild;
      card.querySelector(".vd-text").textContent = text;
      let field = null;
      if (input) {
        field = document.createElement("input");
        field.className = "vd-input";
        field.value = input.value || "";
        card.insertBefore(field, card.querySelector(".vd-buttons"));
      }
      const close = (val) => {
        document.removeEventListener("keydown", onKey, true);
        ov.remove();
        document.body.classList.remove("vd-lock");
        if (prevFocus && prevFocus.focus) prevFocus.focus();
        resolve(val);
      };
      const btns = buttons.map((b) => {
        const el = document.createElement("button");
        el.textContent = b.label;
        if (b.cls) el.className = b.cls;
        el.onclick = () => close(b.cancel ? (input ? null : false) : (input ? field.value : b.value));
        card.querySelector(".vd-buttons").appendChild(el);
        return el;
      });
      const cancel = buttons.find((b) => b.cancel);
      const onKey = (e) => {
        if (e.key === "Escape") { e.preventDefault(); close(cancel ? (input ? null : false) : true); }
        if (e.key === "Enter" && field && document.activeElement === field) { e.preventDefault(); close(field.value); }
        if (e.key === "Tab") {
          const f = [field, ...btns].filter(Boolean);
          const i = f.indexOf(document.activeElement);
          e.preventDefault();
          f[(i + (e.shiftKey ? f.length - 1 : 1)) % f.length].focus();
        }
      };
      ov.addEventListener("mousedown", (e) => { if (e.target === ov) close(cancel ? (input ? null : false) : true); });
      document.addEventListener("keydown", onKey, true);
      document.body.classList.add("vd-lock");
      document.body.appendChild(ov);
      (field || btns[btns.length - 1]).focus();
    });
  }

  // default button labels: Serbian; an app with another UI language sets window.VD_LABELS before use
  const L = (k, sr) => (window.VD_LABELS || {})[k] || sr;
  window.vd = {
    confirm: (text, o = {}) => open({ text, buttons: [
      { label: o.cancel || L("cancel", "Odustani"), cancel: true },
      { label: o.ok || L("ok", "Nastavi"), value: true, cls: o.danger ? "danger" : "primary" }] }),
    message: (text, o = {}) => open({ text, buttons: [{ label: o.ok || L("message", "U redu"), value: true, cls: "primary" }] }),
    prompt: (text, o = {}) => open({ text, input: { value: o.value }, buttons: [
      { label: o.cancel || L("cancel", "Odustani"), cancel: true },
      { label: o.ok || L("save", "Sačuvaj"), value: true, cls: "primary" }] }),
  };
})();

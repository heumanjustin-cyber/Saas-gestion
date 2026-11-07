/* BUHOS · carrito, pedido y seguimiento en vivo de la página pública del local.
   La página ya está pintada por el servidor; esto solo añade el pedido. Sin dependencias. */
(() => {
  "use strict";
  const cfg = JSON.parse(document.getElementById("buhos-config").textContent);
  const T = cfg.strings;
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const KEY = "buhos:" + cfg.slug + ":";
  const store = {
    get(k, d) { try { const v = localStorage.getItem(KEY + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(KEY + k, JSON.stringify(v)); } catch (e) { /* modo privado */ } },
    del(k) { try { localStorage.removeItem(KEY + k); } catch (e) { /* modo privado */ } },
  };
  const locale = { es: "es-ES", en: "en-GB", fr: "fr-FR" }[cfg.lang] || "es-ES";
  const cents = (s) => Math.round(parseFloat(s || "0") * 100);
  const eur = (c) => (c / 100).toLocaleString(locale, { style: "currency", currency: cfg.currency || "EUR" });
  const fmt = (s, o) => String(s).replace(/\{(\w+)\}/g, (_, k) => (o[k] !== undefined ? o[k] : ""));
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const uid = () => (crypto.randomUUID ? crypto.randomUUID().replace(/-/g, "") : Date.now().toString(36) + Math.random().toString(36).slice(2));

  let venue = cfg.venue;
  let menu = cfg.menu;
  const products = new Map();
  const categoryOf = new Map();
  const alMap = Object.fromEntries(cfg.allergens.map((a) => [a.code, a]));
  function indexMenu() {
    products.clear(); categoryOf.clear();
    for (const c of menu) for (const p of c.products) { products.set(p.id, p); categoryOf.set(p.id, c); }
  }
  indexMenu();

  /* ---------------------------------------------------------------- avisos */
  let toastTimer;
  function toast(msg) {
    const el = $("#toast"); el.textContent = msg; el.hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => { el.hidden = true; }, 1800);
  }
  function vibrate(p) { try { if (navigator.vibrate) navigator.vibrate(p); } catch (e) { /* sin vibración */ } }
  function beep() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      [0, 0.18].forEach((t) => {
        const o = ctx.createOscillator(); const g = ctx.createGain();
        o.frequency.value = 880; o.connect(g); g.connect(ctx.destination);
        g.gain.setValueAtTime(0.0001, ctx.currentTime + t);
        g.gain.exponentialRampToValueAtTime(0.3, ctx.currentTime + t + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + t + 0.15);
        o.start(ctx.currentTime + t); o.stop(ctx.currentTime + t + 0.16);
      });
    } catch (e) { /* sin audio */ }
  }

  /* ---------------------------------------------------------------- hoja inferior */
  const sheet = $("#sheet"); const body = $("#sheet-body");
  let onSheetClose = null; let sheetOpen = false;
  function openSheet(html, onClose) {
    body.innerHTML = html; sheet.hidden = false; document.body.style.overflow = "hidden";
    $("#toast").hidden = true;
    onSheetClose = onClose || null; body.scrollTop = 0;
    if (!sheetOpen) { sheetOpen = true; history.pushState({ buhosSheet: 1 }, ""); }
    const first = body.querySelector("input, button, select, textarea"); if (first && matchMedia("(min-width: 700px)").matches) first.focus();
  }
  function closeSheet(fromHistory) {
    if (sheet.hidden) return;
    sheet.hidden = true; document.body.style.overflow = ""; body.innerHTML = "";
    const cb = onSheetClose; onSheetClose = null; if (cb) cb();
    if (sheetOpen) { sheetOpen = false; if (!fromHistory) history.back(); }
  }
  sheet.addEventListener("click", (e) => { if (e.target.closest("[data-close]")) closeSheet(); });
  addEventListener("keydown", (e) => { if (e.key === "Escape") closeSheet(); });
  addEventListener("popstate", () => { if (sheetOpen) { sheetOpen = false; closeSheet(true); } });

  /* ---------------------------------------------------------------- alérgenos */
  let excluded = new Set(store.get("excluded", []));
  // Un plato cuyos alérgenos no ha confirmado el local nunca se da por seguro con el filtro puesto
  function productBlocked(p) {
    return excluded.size > 0 && (p.tags.includes("allergens_unverified") || p.allergens.some((a) => excluded.has(a)));
  }
  function applyFilter() {
    let hidden = 0;
    $$("[data-product]").forEach((el) => {
      const p = products.get(el.dataset.product);
      const blocked = p ? productBlocked(p) : false;
      el.classList.toggle("hide-al", blocked); if (blocked) hidden++;
    });
    $$("[data-cat-section]").forEach((sec) => {
      const visible = $$("[data-product]", sec).some((el) => !el.classList.contains("hide-al"));
      sec.hidden = !visible;
      const chip = $(`[data-cat="${sec.dataset.catSection}"]`); if (chip) chip.hidden = !visible;
    });
    const btn = $("[data-filter]"); const banner = $("#filter-banner");
    btn.classList.toggle("on", excluded.size > 0);
    $("#filter-count").textContent = excluded.size ? String(excluded.size) : "";
    if (excluded.size) {
      banner.hidden = false;
      banner.innerHTML = esc(fmt(T.filter_active, { n: excluded.size })) + " · <button type=\"button\" data-clear-filter>" + esc(T.filter_clear) + "</button>";
    } else banner.hidden = true;
    return hidden;
  }
  function openFilter() {
    const items = cfg.allergens.map((a) => `<label class="opt"><input type="checkbox" value="${a.code}" ${excluded.has(a.code) ? "checked" : ""}><span>${a.icon} ${esc(a.name)}</span></label>`).join("");
    openSheet(`<h2 id="sheet-title">${esc(T.filter_title)}</h2><p class="sub">${esc(T.allergen_legal)}</p><div class="group">${items}</div>
      <div class="sheet-foot"><button class="btn" type="button" data-clear-filter>${esc(T.filter_clear)}</button><button class="btn primary" type="button" data-apply-filter>OK</button></div>`);
  }
  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-filter]")) openFilter();
    if (e.target.closest("[data-apply-filter]")) {
      excluded = new Set($$("input[type=checkbox]:checked", body).map((i) => i.value));
      store.set("excluded", [...excluded]); applyFilter(); closeSheet();
    }
    if (e.target.closest("[data-clear-filter]")) { excluded = new Set(); store.set("excluded", []); applyFilter(); closeSheet(); }
  });

  /* ---------------------------------------------------------------- carrito */
  let cart = store.get("cart", []);
  function lineKey(l) { return [l.product_id, [...l.option_ids].sort().join(","), [...l.removed].sort().join(","), l.note || ""].join("|"); }
  function unitCents(l) {
    const p = products.get(l.product_id); if (!p) return 0;
    let c = cents(p.price);
    for (const g of p.groups) for (const o of g.options) if (l.option_ids.includes(o.id)) c += cents(o.price_delta);
    return c;
  }
  function sanitizeCart() {
    cart = cart.filter((l) => { const p = products.get(l.product_id); return p && p.available; });
    saveCart();
  }
  function saveCart() { store.set("cart", cart); renderCartBar(); }
  function subtotal() { return cart.reduce((s, l) => s + unitCents(l) * l.qty, 0); }
  function count() { return cart.reduce((s, l) => s + l.qty, 0); }
  function renderCartBar() {
    const bar = $("#cartbar"); const n = count();
    bar.hidden = n === 0;
    $("#cb-count").textContent = String(n);
    $("#cb-total").textContent = eur(subtotal());
  }
  function addLine(line) {
    const k = lineKey(line);
    const found = cart.find((l) => lineKey(l) === k);
    if (found) found.qty = Math.min(50, found.qty + line.qty); else cart.push(line);
    saveCart(); vibrate(15); toast(T.added);
  }
  function optionSummary(l) {
    const p = products.get(l.product_id); if (!p) return "";
    const names = [];
    for (const g of p.groups) for (const o of g.options) if (l.option_ids.includes(o.id)) names.push(o.name);
    return names.concat(l.removed).concat(l.note ? ["«" + l.note + "»"] : []).join(", ");
  }

  /* ---------------------------------------------------------------- ficha del plato */
  function openProduct(pid, preset) {
    const p = products.get(pid); if (!p) return;
    if (!p.available) { toast(T.sold_out); return; }
    const sel = new Map();
    for (const g of p.groups) {
      const s = new Set();
      for (const o of g.options) {
        const wanted = preset ? preset.has(g.name + "|" + o.name) : o.default;
        if (wanted && o.available && !o.allergens.some((a) => excluded.has(a))) s.add(o.id);
      }
      sel.set(g.id, s);
    }
    const removed = new Set((preset && preset.removed ? preset.removed : []).filter((r) => p.removable.includes(r)));
    let qty = 1;
    const groupsHtml = p.groups.map((g) => {
      const single = g.max === 1;
      const req = g.min > 0 ? T.required : T.optional;
      const lim = !single && g.max > 0 ? " · " + fmt(T.up_to, { n: g.max }) : "";
      const opts = g.options.map((o) => {
        const blocked = o.allergens.some((a) => excluded.has(a));
        const dis = !o.available || blocked;
        const delta = cents(o.price_delta);
        const tag = !o.available ? T.sold_out : blocked ? T.options_unavailable : delta ? (delta > 0 ? "+" : "") + eur(delta) : "";
        const ico = o.allergens.map((a) => (alMap[a] ? alMap[a].icon : "")).join("");
        return `<label class="opt${dis ? " dis" : ""}"><input type="${single ? "radio" : "checkbox"}" name="g-${g.id}" value="${o.id}"
          ${sel.get(g.id).has(o.id) ? "checked" : ""} ${dis ? "disabled" : ""}><span>${esc(o.name)} ${ico}</span><em>${esc(tag)}</em></label>`;
      }).join("");
      return `<fieldset class="group" data-group="${g.id}"><legend>${esc(g.name)} <small>${esc(req + lim)}</small></legend>${opts}</fieldset>`;
    }).join("");
    const rmHtml = p.removable.length ? `<div class="group"><legend>${esc(T.remove_title)}</legend><div class="rm">${p.removable.map((r) =>
      `<button type="button" data-rm="${esc(r)}" aria-pressed="${removed.has(r)}">${esc(r)}</button>`).join("")}</div></div>` : "";
    const up = p.upsell ? `<button class="upsell" type="button" data-upsell="${p.upsell.product_id}"><span>🍟</span><span><b>${esc(fmt(T.make_menu, { x: eur(cents(p.upsell.extra)) }))}</b>
      <small>${esc(p.upsell.name)} · ${esc(T.make_menu_sub)}</small></span></button>` : "";
    const al = p.allergens.length ? `<p class="sub">${esc(T.contains)}: ${p.allergens.map((a) => (alMap[a] ? alMap[a].icon + " " + esc(alMap[a].name) : a)).join(", ")}</p>` : "";
    openSheet(`<h2 id="sheet-title">${esc(p.name)}</h2>${p.description ? `<p class="sub">${esc(p.description)}</p>` : ""}${al}
      ${groupsHtml}${rmHtml}${up}
      <div class="sheet-foot"><div class="qty"><button type="button" data-q="-1" aria-label="-">−</button><output id="pq">1</output><button type="button" data-q="1" aria-label="+">+</button></div>
      <button class="btn primary" type="button" id="padd"></button></div>`);

    function price() {
      let c = cents(p.price);
      for (const g of p.groups) for (const o of g.options) if (sel.get(g.id).has(o.id)) c += cents(o.price_delta);
      return c * qty;
    }
    function refresh() { $("#padd").textContent = T.add + " · " + eur(price()); $("#pq").textContent = String(qty); }
    refresh();
    body.onchange = (e) => {
      const fs = e.target.closest("[data-group]"); if (!fs) return;
      const g = p.groups.find((x) => x.id === fs.dataset.group);
      const s = new Set($$("input:checked", fs).map((i) => i.value));
      if (g.max > 1 && s.size > g.max) { e.target.checked = false; s.delete(e.target.value); toast(fmt(T.up_to, { n: g.max })); }
      sel.set(g.id, s); fs.classList.remove("missing"); refresh();
    };
    body.onclick = (e) => {
      const q = e.target.closest("[data-q]");
      if (q) { qty = Math.max(1, Math.min(50, qty + Number(q.dataset.q))); refresh(); return; }
      const rm = e.target.closest("[data-rm]");
      if (rm) { const v = rm.dataset.rm; if (removed.has(v)) removed.delete(v); else removed.add(v); rm.setAttribute("aria-pressed", String(removed.has(v))); return; }
      const upb = e.target.closest("[data-upsell]");
      if (upb) {
        const carry = new Set(); carry.removed = [...removed];
        for (const g of p.groups) for (const o of g.options) if (sel.get(g.id).has(o.id)) carry.add(g.name + "|" + o.name);
        openProduct(upb.dataset.upsell, carry); return;
      }
      if (e.target.closest("#padd")) {
        for (const g of p.groups) {
          if (sel.get(g.id).size < g.min) {
            const fs = $(`[data-group="${g.id}"]`, body); fs.classList.add("missing");
            fs.querySelector("small").textContent = fmt(T.required_group, { g: g.name.toLowerCase() });
            fs.scrollIntoView({ behavior: "smooth", block: "center" }); vibrate([30, 40, 30]); return;
          }
        }
        const option_ids = []; for (const g of p.groups) option_ids.push(...sel.get(g.id));
        addLine({ product_id: p.id, qty, option_ids, removed: [...removed], note: "" });
        closeSheet();
      }
    };
  }
  document.addEventListener("click", (e) => {
    const add = e.target.closest("[data-add]");
    if (add) { openProduct(add.dataset.add); return; }
    const item = e.target.closest("[data-product]");
    if (item && !e.target.closest("a") && !sheetOpen) openProduct(item.dataset.product);
  });

  /* ---------------------------------------------------------------- pedido */
  let checkout = store.get("checkout", { fulfillment: null, name: "", phone: "", address: "", note: "", when: "", pay: "" });
  function fulfillments() {
    const o = venue.ordering; const out = [];
    if (o.dine_in && cfg.qr && cfg.qr.table) out.push("dine_in");
    if (o.takeaway) out.push("takeaway");
    if (o.delivery) out.push("delivery");
    return out;
  }
  function openCart() {
    sanitizeCart();
    const fs = fulfillments();
    if (!checkout.fulfillment || !fs.includes(checkout.fulfillment)) checkout.fulfillment = fs[0] || "takeaway";
    if (!checkout.pay || !venue.ordering.payment_methods.includes(checkout.pay)) checkout.pay = venue.ordering.payment_methods[0] || "";
    renderCart();
  }
  function renderCart(errorMsg) {
    if (!cart.length) { openSheet(`<h2 id="sheet-title">${esc(T.cart)}</h2><p class="sub">${esc(T.empty_cart)}</p>`); return; }
    const f = checkout.fulfillment; const o = venue.ordering;
    const lines = cart.map((l, i) => {
      const p = products.get(l.product_id);
      return `<div class="line"><div class="line-main"><b>${esc(p.name)}</b><small>${esc(optionSummary(l))}</small></div>
        <div class="qty"><button type="button" data-lq="${i}:-1" aria-label="-">−</button><output>${l.qty}</output><button type="button" data-lq="${i}:1" aria-label="+">+</button></div>
        <span class="lp">${eur(unitCents(l) * l.qty)}</span></div>`;
    }).join("");
    // ¿Algo de beber? Si la categoría sugiere otra y aún no hay nada de ella en el pedido
    let suggest = "";
    const sugIds = new Set(cart.map((l) => (categoryOf.get(l.product_id) || {}).suggest_category_id).filter(Boolean));
    const inCart = new Set(cart.map((l) => (categoryOf.get(l.product_id) || {}).id));
    for (const sid of sugIds) {
      if (inCart.has(sid)) continue;
      const cat = menu.find((c) => c.id === sid); if (!cat) continue;
      const opts = cat.products.filter((p) => p.available && !p.groups.length && !productBlocked(p)).slice(0, 8);
      if (opts.length) suggest = `<div class="suggest"><p>${esc(T.add_drink)}</p><div class="rm">${opts.map((p) =>
        `<button type="button" data-quick="${p.id}">${esc(p.name)} · ${eur(cents(p.price))} +</button>`).join("")}</div></div>`;
    }
    const segs = fulfillments().map((x) => `<button type="button" data-f="${x}" aria-pressed="${x === f}">${esc(T[x])}</button>`).join("");
    const sub = subtotal();
    const fee = f === "delivery" ? cents(o.delivery_fee) : 0;
    const minC = cents(o.delivery_min_order);
    const field = (name, label, val, attrs) => `<label class="field" data-field="${name}"><span>${label}</span><input name="${name}" value="${esc(val)}" ${attrs || ""}></label>`;
    let fields = "";
    if (f === "takeaway") fields += field("name", esc(T.your_name), checkout.name, 'autocomplete="given-name" maxlength="120" required');
    if (f === "delivery") fields += field("name", esc(T.your_name), checkout.name, 'autocomplete="name" maxlength="120"');
    if (f !== "dine_in") fields += field("phone", `${esc(T.your_phone)} <small>${esc(T.phone_hint)}</small>`, checkout.phone, `type="tel" inputmode="tel" autocomplete="tel" maxlength="40" ${f === "delivery" ? "required" : ""}`);
    if (f === "delivery") fields += field("address", `${esc(T.address)} <small>${esc(T.address_hint)}</small>`, checkout.address, 'autocomplete="street-address" maxlength="255" required');
    const slots = venue.slots || [];
    const mustSchedule = !venue.is_open;
    let when = "";
    if (o.scheduled && slots.length) {
      when = `<label class="field" data-field="when"><span>${esc(T.when)}</span><select name="when">${mustSchedule ? `<option value="">${esc(T.choose_slot)}</option>` : `<option value="">${esc(T.asap)}</option>`}
        ${slots.map((s) => `<option value="${s.value}" ${checkout.when === s.value ? "selected" : ""}>${esc(s.label)}</option>`).join("")}</select></label>`;
    }
    const pays = o.payment_methods.map((m) => `<button type="button" data-pay="${m}" aria-pressed="${m === checkout.pay}">${esc(T[m] || m)}</button>`).join("");
    const minWarn = f === "delivery" && sub < minC ? `<p class="err">${esc(fmt(T.min_order, { x: eur(minC) }))}</p>` : "";
    openSheet(`<h2 id="sheet-title">${esc(T.cart)}</h2>
      <div class="lines">${lines}</div>${suggest}
      <div class="form"><div><b>${esc(T.how)}</b><div class="seg">${segs}</div>
        ${f === "dine_in" ? `<p class="note">${esc(fmt(T.table_banner, { table: cfg.qr.table }))}</p>` : ""}
        ${f === "delivery" && o.delivery_note ? `<p class="note">${esc(o.delivery_note)}</p>` : ""}</div>
        ${fields}${when}
        <label class="field" data-field="note"><span>${esc(T.order_note)}</span><input name="note" value="${esc(checkout.note)}" maxlength="280"></label>
        ${pays ? `<div><b>${esc(T.pay_at)}</b><div class="seg">${pays}</div></div>` : ""}
        <input class="hp" name="website" tabindex="-1" autocomplete="off" aria-hidden="true">
      </div>
      <div class="totals"><div><span>${esc(T.subtotal)}</span><span>${eur(sub)}</span></div>
        ${fee ? `<div><span>${esc(T.delivery_fee)}</span><span>${eur(fee)}</span></div>` : ""}
        <div class="grand"><span>${esc(T.total)}</span><span>${eur(sub + fee)}</span></div></div>
      ${minWarn}${errorMsg ? `<p class="err" role="alert">${esc(errorMsg)}</p>` : ""}
      <p class="note">${esc(T.allergen_legal)} ${esc(T.privacy)}</p>
      <div class="sheet-foot"><button class="btn primary" type="button" id="send" ${minWarn || !venue.ordering.enabled ? "disabled" : ""}>${esc(fmt(T.send_order, { total: eur(sub + fee) }))}</button></div>`);
    body.oninput = (e) => {
      const n = e.target.name;
      if (n && Object.prototype.hasOwnProperty.call(checkout, n)) { checkout[n] = e.target.value; store.set("checkout", checkout); }
      const fl = e.target.closest(".field"); if (fl) fl.classList.remove("bad");
    };
    body.onchange = body.oninput;
    body.onclick = (e) => {
      const lq = e.target.closest("[data-lq]");
      if (lq) { const [i, d] = lq.dataset.lq.split(":").map(Number); cart[i].qty += d; if (cart[i].qty <= 0) cart.splice(i, 1); saveCart(); renderCart(); return; }
      const fb = e.target.closest("[data-f]");
      if (fb) { checkout.fulfillment = fb.dataset.f; store.set("checkout", checkout); renderCart(); return; }
      const pb = e.target.closest("[data-pay]");
      if (pb) { checkout.pay = pb.dataset.pay; store.set("checkout", checkout); $$("[data-pay]", body).forEach((b) => b.setAttribute("aria-pressed", String(b === pb))); return; }
      const qb = e.target.closest("[data-quick]");
      if (qb) { addLine({ product_id: qb.dataset.quick, qty: 1, option_ids: [], removed: [], note: "" }); renderCart(); return; }
      if (e.target.closest("#send")) send();
    };
  }

  function bad(name) { const el = $(`[data-field="${name}"]`, body); if (el) { el.classList.add("bad"); const i = el.querySelector("input, select"); if (i) i.focus(); } }
  async function send() {
    const f = checkout.fulfillment;
    if (f === "takeaway" && !checkout.name.trim()) return bad("name");
    if (f === "delivery" && !checkout.phone.trim()) return bad("phone");
    if (f === "delivery" && !checkout.address.trim()) return bad("address");
    if (!venue.is_open && !checkout.when) { bad("when"); toast(T.schedule_required); return; }
    const btn = $("#send"); btn.disabled = true; btn.textContent = T.sending;
    let ref = store.get("pending_ref", null);
    if (!ref) { ref = uid(); store.set("pending_ref", ref); }  // el mismo en cada reintento: nunca duplica
    const payload = {
      client_ref: ref, fulfillment: f, qr_code: cfg.qr ? cfg.qr.code : null, language: cfg.lang,
      customer_name: checkout.name || null, customer_phone: checkout.phone || null,
      delivery_address: f === "delivery" ? checkout.address : null, customer_note: checkout.note || null,
      scheduled_for: checkout.when || null, payment_method: checkout.pay || null,
      website: ($("input[name=website]", body) || {}).value || null,
      lines: cart.map((l) => ({ product_id: l.product_id, quantity: l.qty, option_ids: l.option_ids, removed: l.removed, note: l.note || null })),
    };
    try {
      const r = await fetch(`${cfg.api}/venues/${encodeURIComponent(cfg.slug)}/orders`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        const d = data.detail;
        const msg = (d && d.message) || (typeof d === "string" ? d : Array.isArray(d) ? T.error_generic : T.error_generic);
        if (d && d.code && d.code !== "closed") store.del("pending_ref");  // el pedido cambiará: referencia nueva
        if (d && ["sold_out", "product_not_found", "option_sold_out"].includes(d.code)) await refreshVenue();
        renderCart(msg); return;
      }
      store.del("pending_ref");
      cart = []; saveCart();
      store.set("active", { token: data.token, number: data.number });
      checkout.note = ""; checkout.when = ""; store.set("checkout", checkout);
      store.set("last_token", data.token);
      openTracking(data.token);  // sustituye la hoja abierta (sin cerrar: evita carreras con history.back)
    } catch (e) {
      renderCart(T.error_generic);
    }
  }

  /* ---------------------------------------------------------------- seguimiento */
  let es = null; let poll = null; let lastStatus = null;
  function stepIndex(s) { return { pending: 0, accepted: 1, preparing: 1, ready: 2, completed: 3 }[s]; }
  function renderTracking(o) {
    const idx = stepIndex(o.status);
    const steps = ["step_pending", "step_preparing", "step_ready", "step_completed"].map((k, i) =>
      `<li class="${idx !== undefined && i < idx ? "done" : idx === i ? (i === 3 ? "done" : "now") : ""}">${esc(T[k])}</li>`).join("");
    const time = (iso) => new Date(iso).toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
    let extra = "";
    if (o.status === "ready") extra = `<p class="ready">${esc(T["ready_" + o.fulfillment] || T.step_ready)}</p>`;
    else if (o.status === "rejected" || o.status === "cancelled") extra = `<p class="bad">${esc(o.status === "rejected" ? T.rejected : o.status_label)}${o.status_reason ? ": " + esc(o.status_reason) : ""}</p>`;
    else if (o.estimated_ready_at && o.status !== "completed") extra = `<p class="sub">${esc(fmt(T.eta, { time: time(o.scheduled_for || o.estimated_ready_at) }))}</p>`;
    const lines = o.lines.map((l) => `<div class="line"><div class="line-main"><b>${l.quantity} × ${esc(l.name)}</b>
      <small>${esc(l.modifiers.map((m) => m.name).concat(l.removed).join(", "))}</small></div><span class="lp">${eur(cents(l.line_total))}</span></div>`).join("");
    const fee = cents(o.delivery_fee) ? `<div><span>${esc(T.delivery_fee)}</span><span>${eur(cents(o.delivery_fee))}</span></div>` : "";
    const html = `<div class="track"><p class="sub">${esc(T.your_number)}</p><p class="num">${esc(o.number)}</p>
      <p class="state" aria-live="polite">${esc(o.status_label)}${o.table ? " · " + esc(o.table) : ""}</p>
      ${["rejected", "cancelled"].includes(o.status) ? "" : `<ol class="steps">${steps}</ol>`}${extra}
      <p class="note">${esc(T.show_number)}</p>
      <div class="lines">${lines}</div>
      <div class="totals">${fee}<div class="grand"><span>${esc(T.total)}</span><span>${eur(cents(o.total))}</span></div></div>
      <div class="sheet-foot">${o.can_cancel ? `<button class="btn" type="button" data-cancel="${o.token}">${esc(T.cancel_order)}</button>` : ""}
        <button class="btn primary" type="button" data-close>${esc(["completed", "rejected", "cancelled"].includes(o.status) ? T.order_again : T.back)}</button></div></div>`;
    if (!sheet.hidden && body.querySelector(".track")) body.innerHTML = html; else openSheet(html, () => stopTracking());
    if (lastStatus && lastStatus !== o.status && o.status === "ready") { vibrate([200, 100, 200]); beep(); }
    lastStatus = o.status;
    document.title = (o.status === "ready" ? "✅ " : "") + `${T.track_title} ${o.number} · ${venue.name}`;
    updateActivePill(o);
    if (["completed", "rejected", "cancelled"].includes(o.status)) { stopTracking(); store.del("active"); }
  }
  function stopTracking() { if (es) { es.close(); es = null; } if (poll) { clearInterval(poll); poll = null; } }
  function openTracking(token) {
    stopTracking();
    const url = `${cfg.api}/orders/${encodeURIComponent(token)}`;
    fetch(`${url}?lang=${cfg.lang}`).then((r) => (r.ok ? r.json() : null)).then((o) => {
      if (!o) { store.del("active"); return; }
      renderTracking(o);
      if (["completed", "rejected", "cancelled"].includes(o.status)) return;
      if ("EventSource" in window) {
        es = new EventSource(`${url}/stream?lang=${cfg.lang}`);
        es.addEventListener("order", (ev) => renderTracking(JSON.parse(ev.data)));
        es.onerror = () => { if (es && es.readyState === 2) { es = null; startPolling(url); } };
      } else startPolling(url);
    }).catch(() => toast(T.error_generic));
  }
  function startPolling(url) {
    if (poll) return;
    poll = setInterval(() => fetch(`${url}?lang=${cfg.lang}`).then((r) => r.json()).then(renderTracking).catch(() => {}), 10000);
  }
  document.addEventListener("click", async (e) => {
    const c = e.target.closest("[data-cancel]");
    if (!c) return;
    c.disabled = true;
    const r = await fetch(`${cfg.api}/orders/${encodeURIComponent(c.dataset.cancel)}/cancel`, { method: "POST" });
    const data = await r.json().catch(() => ({}));
    if (r.ok) renderTracking(data); else { toast(typeof data.detail === "string" ? data.detail : T.error_generic); c.disabled = false; }
  });
  function updateActivePill(o) {
    const pill = $("#active-order");
    const active = store.get("active", null);
    if (!active || (o && ["completed", "rejected", "cancelled"].includes(o.status))) { pill.hidden = true; return; }
    pill.hidden = false;
    pill.textContent = fmt(T.active_order, { n: active.number, status: o ? o.status_label : "…" }) + " →";
    pill.onclick = () => openTracking(active.token);
  }

  /* ---------------------------------------------------------------- opinión privada y compartir */
  document.addEventListener("click", async (e) => {
    if (e.target.closest("[data-feedback]")) { const f = $("#feedback"); f.hidden = !f.hidden; if (!f.hidden) f.message.focus(); }
    if (e.target.closest("[data-share]")) {
      const url = location.origin + location.pathname;
      try {
        if (navigator.share) await navigator.share({ title: venue.name, url });
        else { await navigator.clipboard.writeText(url); toast(T.copied); }
      } catch (err) { /* cancelado */ }
    }
  });
  $("#feedback").addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target; const msg = $(".form-msg", f); const btn = $("button", f);
    btn.disabled = true;
    const active = store.get("last_token", null);
    try {
      const r = await fetch(`${cfg.api}/venues/${encodeURIComponent(cfg.slug)}/feedback`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: f.message.value, contact: f.contact.value || null, website: f.website.value || null, order_token: active }) });
      if (!r.ok) throw new Error();
      f.reset(); msg.textContent = T.sent_thanks;
    } catch (err) { msg.textContent = T.error_generic; }
    btn.disabled = false;
  });

  /* ---------------------------------------------------------------- categorías activas al hacer scroll */
  const chips = new Map($$("[data-cat]").map((a) => [a.dataset.cat, a]));
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      for (const en of entries) {
        if (!en.isIntersecting) continue;
        chips.forEach((a) => a.classList.remove("on"));
        const a = chips.get(en.target.dataset.catSection);
        if (a) { a.classList.add("on"); a.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" }); }
      }
    }, { rootMargin: "-130px 0px -60% 0px" });
    $$("[data-cat-section]").forEach((s) => io.observe(s));
  }

  /* ---------------------------------------------------------------- datos frescos (agotados, abierto/cerrado) */
  async function refreshVenue() {
    try {
      const r = await fetch(`${cfg.api}/venues/${encodeURIComponent(cfg.slug)}?lang=${cfg.lang}`);
      if (!r.ok) return;
      const data = await r.json();
      venue = data.venue; menu = data.menu; indexMenu();
      const pill = $("#status-pill"); pill.className = "status-line " + (venue.is_open ? "open" : "closed"); $("span", pill).textContent = venue.status_text;
      const short = $("#status-pill-short"); short.className = "pill " + (venue.is_open ? "open" : "closed"); $("span", short).textContent = venue.status_short;
      $$("[data-product]").forEach((el) => {
        const p = products.get(el.dataset.product);
        const avail = p && p.available;
        el.classList.toggle("out", !avail);
        const side = $(".item-side", el);
        const btn = $("[data-add]", side); const so = $(".soldout", side);
        if (avail && !btn) { if (so) so.remove(); side.insertAdjacentHTML("beforeend", `<button class="add" type="button" data-add="${p.id}" aria-label="${esc(T.add)}: ${esc(p.name)}">+</button>`); }
        if (!avail && btn) { btn.remove(); side.insertAdjacentHTML("beforeend", `<span class="soldout">${esc(T.sold_out)}</span>`); }
      });
      sanitizeCart(); applyFilter();
    } catch (e) { /* sin conexión: seguimos con lo que hay */ }
  }
  setInterval(refreshVenue, 120000);
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") refreshVenue(); });

  /* ---------------------------------------------------------------- arranque */
  $("#cartbar").addEventListener("click", openCart);
  applyFilter(); sanitizeCart(); renderCartBar();
  const params = new URLSearchParams(location.search);
  const fromLink = params.get("pedido");
  const active = store.get("active", null);
  if (fromLink) { store.set("active", { token: fromLink, number: "…" }); openTracking(fromLink); }
  else if (active) {
    updateActivePill(null);
    fetch(`${cfg.api}/orders/${encodeURIComponent(active.token)}?lang=${cfg.lang}`).then((r) => (r.ok ? r.json() : null))
      .then((o) => { if (!o) { store.del("active"); updateActivePill(null); } else { store.set("active", { token: o.token, number: o.number }); updateActivePill(o); } })
      .catch(() => {});
  }
  if (active) store.set("last_token", active.token);
})();

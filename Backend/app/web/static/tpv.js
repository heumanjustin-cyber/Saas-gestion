/* BUHOSS · TPV: carta táctil, ticket, cobro, pedidos del QR, tickets emitidos, caja y gestión. */
(async () => {
  "use strict";
  const B = window.BUHOS;
  const { $, $$, esc, cents, money, dec, api, toast, modal, confirmBox } = B;
  const root = $("#app");
  const me = await B.login(root, { title: "TPV", subtitle: "Empareja este TPV con tu local.", deviceName: "TPV barra" });
  const cid = me.company.id;
  const PAY = { cash: "Efectivo", card: "Tarjeta", bizum: "Bizum", other: "Otro" };
  const T = Object.assign({ lines: [], orders: [], table: "", fulfillment: "dine_in", kitchen: true }, B.LS.get("ticket") || {});
  let menu = []; const products = new Map();
  let session = null; let unpaid = []; let curCat = null;
  let autoPrint = B.LS.get("tpv_autoprint") !== false;

  root.innerHTML = `
    <div class="bar">
      <div><h1>${esc(me.company.name)} · ${esc(me.register.name)}</h1><div class="who">${esc(me.name)} · <span id="sess">…</span></div></div>
      <span class="sp"></span>
      <button class="b" id="b-orders">Pedidos QR <span class="badge" id="n-orders" hidden></span></button>
      <button class="b" id="b-tickets">Tickets</button>
      <button class="b" id="b-cash">Caja</button>
      ${me.is_manager ? `<button class="b" id="b-manage">Gestión</button>` : ""}
      <button class="b ghost" id="b-out" aria-label="Salir">⏻</button>
    </div>
    <div id="banners"></div>
    <div class="tpv">
      <section class="catalog"><div class="cat-tabs" id="tabs"></div><div class="grid" id="grid"></div></section>
      <aside class="ticket" id="ticket">
        <div class="t-head">
          <div class="row" style="flex-wrap:nowrap"><input id="t-table" placeholder="Mesa o nombre (opcional)" maxlength="60"><button class="b ghost" id="t-hide">✕</button></div>
          <div class="seg" id="t-ful"><button data-f="dine_in">Aquí</button><button data-f="takeaway">Para llevar</button></div>
          <label class="toggle" style="margin:0"><span>Enviar a cocina</span><input type="checkbox" id="t-kitchen"></label>
        </div>
        <div class="t-lines" id="t-lines"></div>
        <div class="t-foot">
          <div class="t-total"><span>Total</span><span id="t-total" class="num">0,00 €</span></div>
          <div class="grid2"><button class="b" id="t-clear">Vaciar</button><button class="b" id="t-free">+ Varios</button></div>
          <button class="b primary big full" id="t-pay">Cobrar</button>
        </div>
      </aside>
    </div>
    <button class="b primary big mobile-bar" id="m-bar">Ver ticket · <span id="m-total">0,00 €</span></button>`;

  /* ---------------------------------------------------------------- avisos de configuración */
  function banners() {
    const out = [];
    if (!me.fiscal.configured) out.push("Faltan los datos fiscales (NIF y razón social): configúralos en el panel para poder cobrar.");
    else if (me.fiscal.environment === "test") out.push("Modo pruebas: los tickets salen marcados «sin validez fiscal». Pásalo a producción el día del arranque.");
    if (!session) out.push("La caja está cerrada: ábrela con el fondo de cambio para empezar a cobrar.");
    $("#banners").innerHTML = out.map((t) => `<div class="banner">${esc(t)}</div>`).join("");
  }

  /* ---------------------------------------------------------------- carta */
  async function loadMenu() {
    menu = await api("/pos/catalog");
    products.clear();
    for (const c of menu) for (const p of c.products) products.set(p.id, p);
    if (!curCat || !menu.find((c) => c.id === curCat)) curCat = menu[0] ? menu[0].id : null;
    renderCatalog();
  }
  function renderCatalog() {
    $("#tabs").innerHTML = menu.map((c) => `<button data-cat="${c.id}" aria-pressed="${c.id === curCat}">${esc(c.name)}</button>`).join("");
    const cat = menu.find((c) => c.id === curCat);
    $("#grid").innerHTML = cat ? cat.products.map((p) => `<button class="prod ${p.available ? "" : "out"}" data-p="${p.id}"><b>${esc(p.name)}</b><span>${money(p.price)}</span></button>`).join("")
      : `<p class="empty">La carta está vacía.</p>`;
  }
  $("#tabs").onclick = (e) => { const b = e.target.closest("[data-cat]"); if (b) { curCat = b.dataset.cat; renderCatalog(); } };
  $("#grid").onclick = (e) => {
    const b = e.target.closest("[data-p]"); if (!b) return;
    const p = products.get(b.dataset.p);
    if (!p.available) toast("Agotado en la web: se vende igual en barra");
    if (p.groups.length || p.removable.length) openOptions(p); else addLine(p, [], []);
  };

  /* ---------------------------------------------------------------- ticket */
  const unitOf = (p, ids) => cents(p.price) + p.groups.flatMap((g) => g.options).filter((o) => ids.includes(o.id)).reduce((s, o) => s + cents(o.price_delta), 0);
  const descOf = (p, ids, removed) => p.groups.flatMap((g) => g.options).filter((o) => ids.includes(o.id)).map((o) => o.name).concat(removed).join(", ");
  function addLine(p, ids, removed, qty = 1) {
    const key = [p.id, [...ids].sort().join(","), [...removed].sort().join(",")].join("|");
    const found = T.lines.find((l) => l.key === key);
    if (found) found.qty += qty;
    else T.lines.push({ key, product_id: p.id, name: p.name, qty, unit: unitOf(p, ids), option_ids: ids, removed, desc: descOf(p, ids, removed) });
    save();
  }
  function total() {
    return T.lines.reduce((s, l) => s + l.unit * l.qty, 0) + T.orders.reduce((s, o) => s + cents(o.total), 0);
  }
  function save() { B.LS.set("ticket", T); renderTicket(); }
  function renderTicket() {
    $("#t-table").value = T.table || "";
    $$("#t-ful [data-f]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.f === T.fulfillment)));
    $("#t-kitchen").checked = !!T.kitchen;
    const orders = T.orders.map((o, i) => `<div class="t-order"><div class="row" style="justify-content:space-between"><b>Pedido ${esc(o.number)}${o.table ? " · " + esc(o.table) : ""}</b>
      <span class="num"><b>${money(o.total)}</b> <button class="b ghost" data-unorder="${i}" style="min-height:36px;padding:4px 10px">✕</button></span></div>
      <small class="muted">${esc(o.lines.map((l) => l.quantity + "× " + l.name).join(", "))}</small></div>`).join("");
    const lines = T.lines.map((l, i) => `<div class="t-line"><div class="grow"><b>${esc(l.name)}</b>${l.desc ? `<small>${esc(l.desc)}</small>` : ""}</div>
      <div class="q"><button data-lq="${i}:-1">−</button><output>${l.qty}</output><button data-lq="${i}:1">+</button></div>
      <span class="p">${money(l.unit * l.qty)}</span></div>`).join("");
    $("#t-lines").innerHTML = orders + lines || `<p class="empty">Toca un producto o trae un pedido del QR.</p>`;
    $("#t-total").textContent = money(total());
    $("#m-total").textContent = money(total());
    $("#t-pay").disabled = total() <= 0;
  }
  $("#t-lines").onclick = (e) => {
    const q = e.target.closest("[data-lq]");
    if (q) { const [i, d] = q.dataset.lq.split(":").map(Number); T.lines[i].qty += d; if (T.lines[i].qty <= 0) T.lines.splice(i, 1); save(); }
    const u = e.target.closest("[data-unorder]");
    if (u) { T.orders.splice(Number(u.dataset.unorder), 1); save(); }
  };
  $("#t-table").oninput = (e) => { T.table = e.target.value; B.LS.set("ticket", T); };
  $("#t-ful").onclick = (e) => { const b = e.target.closest("[data-f]"); if (b) { T.fulfillment = b.dataset.f; save(); } };
  $("#t-kitchen").onchange = (e) => { T.kitchen = e.target.checked; save(); };
  $("#t-clear").onclick = async () => { if (await confirmBox("Vaciar ticket", "Se quitan todas las líneas.", "Vaciar", true)) { T.lines = []; T.orders = []; T.table = ""; save(); } };
  $("#m-bar").onclick = () => $("#ticket").classList.add("open");
  $("#t-hide").onclick = () => $("#ticket").classList.remove("open");

  /* ---------------------------------------------------------------- opciones de un producto */
  function openOptions(p) {
    const sel = new Map(p.groups.map((g) => [g.id, new Set(g.options.filter((o) => o.default).map((o) => o.id))]));
    const removed = new Set(); let qty = 1;
    const m = modal(`<h2>${esc(p.name)}</h2><p class="muted">${money(p.price)}</p>
      ${p.groups.map((g) => `<p class="section-title">${esc(g.name)} · ${g.min > 0 ? "obligatorio" : "opcional"}${g.max > 1 ? " · hasta " + g.max : ""}</p>
        <div data-g="${g.id}">${g.options.map((o) => `<label class="opt"><input type="${g.max === 1 ? "radio" : "checkbox"}" name="g${g.id}" value="${o.id}" ${sel.get(g.id).has(o.id) ? "checked" : ""}>
        ${esc(o.name)}${o.available ? "" : ' <span class="chip red">agotado</span>'}<em>${cents(o.price_delta) ? "+" + money(o.price_delta) : ""}</em></label>`).join("")}</div>`).join("")}
      ${p.removable.length ? `<p class="section-title">Quitar</p><div class="rm">${p.removable.map((r) => `<button data-rm="${esc(r)}" aria-pressed="false">${esc(r)}</button>`).join("")}</div>` : ""}
      <div class="row" style="margin-top:16px;justify-content:space-between"><div class="row"><button class="b" data-q="-1">−</button><b id="oq" style="min-width:30px;text-align:center">1</b><button class="b" data-q="1">+</button></div>
      <button class="b primary big" id="oadd">Añadir</button></div>`, { wide: true });
    const price = () => (cents(p.price) + p.groups.flatMap((g) => g.options).filter((o) => sel.get(g_of(o)).has(o.id)).reduce((s, o) => s + cents(o.price_delta), 0)) * qty;
    const gIndex = new Map(p.groups.flatMap((g) => g.options.map((o) => [o.id, g.id])));
    const g_of = (o) => gIndex.get(o.id);
    const refresh = () => { $("#oadd", m.el).textContent = "Añadir · " + money(price()); $("#oq", m.el).textContent = qty; };
    refresh();
    m.el.addEventListener("change", (e) => {
      const box = e.target.closest("[data-g]"); if (!box) return;
      const g = p.groups.find((x) => x.id === box.dataset.g);
      const s = new Set($$("input:checked", box).map((i) => i.value));
      if (g.max > 1 && s.size > g.max) { e.target.checked = false; s.delete(e.target.value); }
      sel.set(g.id, s); refresh();
    });
    m.el.addEventListener("click", (e) => {
      const q = e.target.closest("[data-q]"); if (q) { qty = Math.max(1, qty + Number(q.dataset.q)); refresh(); }
      const r = e.target.closest("[data-rm]"); if (r) { const v = r.dataset.rm; removed.has(v) ? removed.delete(v) : removed.add(v); r.setAttribute("aria-pressed", String(removed.has(v))); }
      if (e.target.closest("#oadd")) {
        const missing = p.groups.find((g) => sel.get(g.id).size < g.min);
        if (missing) { toast("Elige " + missing.name.toLowerCase(), true); return; }
        addLine(p, p.groups.flatMap((g) => [...sel.get(g.id)]), [...removed], qty); m.close();
      }
    });
  }

  /* ---------------------------------------------------------------- teclado numérico */
  function keypad(el, initial, onChange) {
    let v = initial || "";
    el.innerHTML = `<div class="keypad">${["1", "2", "3", "4", "5", "6", "7", "8", "9", ",", "0", "⌫"].map((k) => `<button data-k="${k}">${k}</button>`).join("")}</div>`;
    el.onclick = (e) => {
      const b = e.target.closest("[data-k]"); if (!b) return;
      const k = b.dataset.k;
      if (k === "⌫") v = v.slice(0, -1);
      else if (k === ",") { if (!v.includes(",")) v = (v || "0") + ","; }
      else if (!(v.includes(",") && v.split(",")[1].length >= 2)) v += k;
      onChange(v);
    };
    return { set(x) { v = x; onChange(v); }, get: () => v };
  }
  const kcents = (v) => Math.round(parseFloat((v || "0").replace(",", ".")) * 100) || 0;

  /* ---------------------------------------------------------------- artículo libre */
  $("#t-free").onclick = () => {
    const m = modal(`<h2>Artículo libre</h2><label class="f">Descripción<input id="fd" maxlength="120" value="Varios"></label>
      <div class="display"><span>Precio</span><b id="fp">0,00 €</b></div><div id="fk"></div>
      <div class="seg" style="margin:10px 0" id="fr"><button data-r="10" aria-pressed="true">IVA 10 %</button><button data-r="21" aria-pressed="false">IVA 21 %</button><button data-r="4" aria-pressed="false">IVA 4 %</button></div>
      <button class="b primary big full" id="fok">Añadir</button>`);
    let rate = 10;
    const kp = keypad($("#fk", m.el), "", (v) => { $("#fp", m.el).textContent = money(kcents(v)); });
    $("#fr", m.el).onclick = (e) => { const b = e.target.closest("[data-r]"); if (!b) return; rate = Number(b.dataset.r); $$("#fr [data-r]", m.el).forEach((x) => x.setAttribute("aria-pressed", String(x === b))); };
    $("#fok", m.el).onclick = () => {
      const c = kcents(kp.get()); const d = $("#fd", m.el).value.trim();
      if (!c || !d) { toast("Pon descripción y precio", true); return; }
      T.lines.push({ key: "free:" + Date.now(), product_id: null, name: d, qty: 1, unit: c, option_ids: [], removed: [], desc: "IVA " + rate + " %", tax_rate: rate });
      save(); m.close();
    };
  };

  /* ---------------------------------------------------------------- cobro */
  $("#t-pay").onclick = () => {
    if (!me.fiscal.configured) { toast("Faltan los datos fiscales del local", true); return; }
    if (!session) { toast("Abre la caja primero", true); openCash(); return; }
    const tot = total(); if (tot <= 0) return;
    let method = "cash"; let tendered = ""; let cardPart = "";
    const m = modal(`<h2>Cobrar</h2><div class="pay-grid"><div>
      <div class="pay-total">${money(tot)}</div>
      <div class="seg" id="pm">${["cash", "card", "bizum", "mixed"].map((x) => `<button data-m="${x}" aria-pressed="${x === "cash"}">${x === "mixed" ? "Mixto" : PAY[x]}</button>`).join("")}</div>
      <div id="pbody" style="margin-top:12px"></div>
      <label class="toggle" style="margin-top:10px"><span>Imprimir ticket al cobrar</span><input type="checkbox" id="pprint" ${autoPrint ? "checked" : ""}></label>
      </div><div id="pk"></div></div>
      <button class="b ok big full" id="pok" style="margin-top:12px">Cobrar ${money(tot)}</button><div id="perr"></div>`, { wide: true });
    const body = $("#pbody", m.el); const ok = $("#pok", m.el); const pad = $("#pk", m.el);
    function draw() {
      pad.innerHTML = ""; pad.onclick = null;
      if (method === "cash") {
        body.innerHTML = `<div class="quick">${[["Exacto", tot], ["5 €", 500], ["10 €", 1000], ["20 €", 2000], ["50 €", 5000], ["100 €", 10000]].filter(([, v]) => v >= tot || v === tot)
          .map(([l, v]) => `<button data-t="${v}">${l}</button>`).join("")}</div>
          <div class="display"><span>Entregado</span><b id="pt">${money(kcents(tendered))}</b></div><div class="change" id="pc"></div>`;
        const kp = keypad(pad, tendered, (v) => { tendered = v; upd(); });
        body.querySelector(".quick").onclick = (e) => { const b = e.target.closest("[data-t]"); if (b) kp.set(dec(Number(b.dataset.t)).replace(".", ",")); };
        const upd = () => {
          const t = kcents(tendered);
          $("#pt", body).textContent = money(t);
          $("#pc", body).innerHTML = t >= tot ? `Cambio<b>${money(t - tot)}</b>` : t ? `<span class="muted">Faltan ${money(tot - t)}</span>` : "";
          ok.disabled = t > 0 && t < tot;
        };
        upd();
      } else if (method === "mixed") {
        body.innerHTML = `<div class="display"><span>Con tarjeta</span><b id="pcard">${money(kcents(cardPart))}</b></div>
          <div class="display"><span>En efectivo</span><b id="pcash">${money(Math.max(tot - kcents(cardPart), 0))}</b></div>`;
        keypad(pad, cardPart, (v) => {
          cardPart = v; const c = kcents(v);
          $("#pcard", body).textContent = money(c); $("#pcash", body).textContent = money(Math.max(tot - c, 0));
          ok.disabled = c <= 0 || c >= tot;
        });
        ok.disabled = true;
      } else {
        body.innerHTML = `<p class="muted" style="margin-bottom:10px">${method === "card" ? "Cobra " + money(tot) + " en el datáfono y confirma aquí." : "Comprueba el Bizum de " + money(tot) + " en el móvil del local."}</p>
          <label class="f">Referencia (opcional)<input id="pref" maxlength="80" placeholder="${method === "card" ? "Nº de operación" : "Nombre o teléfono"}"></label>`;
        ok.disabled = false;
      }
    }
    draw();
    $("#pm", m.el).onclick = (e) => { const b = e.target.closest("[data-m]"); if (!b) return; method = b.dataset.m; $$("#pm [data-m]", m.el).forEach((x) => x.setAttribute("aria-pressed", String(x === b))); draw(); };
    $("#pprint", m.el).onchange = (e) => { autoPrint = e.target.checked; B.LS.set("tpv_autoprint", autoPrint); };
    ok.onclick = async () => {
      let payments;
      if (method === "cash") { const t = kcents(tendered); payments = [{ method: "cash", amount: dec(tot), tendered: t ? dec(t) : null }]; }
      else if (method === "mixed") { const c = kcents(cardPart); payments = [{ method: "card", amount: dec(c) }, { method: "cash", amount: dec(tot - c) }]; }
      else payments = [{ method, amount: dec(tot), reference: ($("#pref", m.el).value || "").trim() || null }];
      ok.disabled = true; ok.textContent = "Cobrando…";
      try {
        const inv = await api("/pos/sales", { body: {
          lines: T.lines.map((l) => l.product_id ? { product_id: l.product_id, quantity: l.qty, option_ids: l.option_ids, removed: l.removed }
            : { description: l.name, unit_price: dec(l.unit), tax_rate: String(l.tax_rate || 10), quantity: l.qty }),
          order_ids: T.orders.map((o) => o.id), payments, fulfillment: T.fulfillment, table_label: T.table || null,
          send_to_kitchen: T.kitchen } });
        m.close();
        T.lines = []; T.orders = []; T.table = ""; T.kitchen = true; T.fulfillment = "dine_in"; save();
        $("#ticket").classList.remove("open");
        done(inv);
        refreshSession(); refreshUnpaid();
      } catch (err) {
        ok.disabled = false; ok.textContent = "Cobrar " + money(tot);
        $("#perr", m.el).innerHTML = `<p class="err">${esc(err.message)}</p>`;
        if (/no cuadran/.test(err.message)) loadMenu();
      }
    };
  };
  function done(inv) {
    const change = cents(inv.change);
    const m = modal(`<h2>Cobrado · ${esc(inv.full_number)}</h2>
      ${change ? `<div class="change">Cambio<b>${money(change)}</b></div>` : `<div class="change">Total<b>${money(inv.total)}</b></div>`}
      ${inv.order_numbers.length ? `<p class="muted" style="text-align:center">Pedido ${esc(inv.order_numbers.join(", "))}</p>` : ""}
      <div class="grid2" style="margin-top:14px"><button class="b big" id="dprint">Imprimir ticket</button><button class="b primary big" data-close>Nuevo ticket</button></div>`);
    $("#dprint", m.el).onclick = () => B.printUrl(`/pos/invoices/${inv.id}/ticket`).catch((e) => toast(e.message, true));
    if (autoPrint) B.printUrl(`/pos/invoices/${inv.id}/ticket`).catch((e) => toast(e.message, true));
  }

  /* ---------------------------------------------------------------- pedidos del QR pendientes de cobro */
  async function refreshUnpaid() {
    try { unpaid = await api("/pos/orders/unpaid"); } catch (e) { return; }
    const n = unpaid.filter((o) => !T.orders.find((x) => x.id === o.id)).length;
    const badge = $("#n-orders"); badge.hidden = !n; badge.textContent = String(n);
  }
  let deb;
  B.sse(`/my/venues/${cid}/orders/stream`, () => { clearTimeout(deb); deb = setTimeout(refreshUnpaid, 400); }, () => {});
  $("#b-orders").onclick = async () => {
    await refreshUnpaid();
    const free = unpaid.filter((o) => !T.orders.find((x) => x.id === o.id));
    const st = { pending: "Nuevo", accepted: "Aceptado", preparing: "En cocina", ready: "Listo", completed: "Entregado" };
    const m = modal(`<h2>Pedidos pendientes de cobro</h2><p class="muted">Del QR, la web y la barra. Marca los de una mesa y cóbralos juntos.</p>
      <div style="margin-top:12px">${free.length ? free.map((o) => `<label class="list-item"><input type="checkbox" value="${o.id}" style="width:24px;height:24px">
        <span class="grow"><b>Pedido ${esc(o.number)} · ${esc(o.table || (o.fulfillment === "delivery" ? "Domicilio" : o.customer_name || "Para recoger"))}</b>
        <small>${esc(o.lines.map((l) => l.quantity + "× " + l.name).join(", "))}</small></span>
        <span class="chip ${o.channel === "pos" ? "" : "qr"}">${o.channel === "pos" ? "Barra" : "QR"}</span><span class="chip">${st[o.status] || o.status}</span>
        <b class="num">${money(o.total)}</b></label>`).join("") : `<p class="empty">No hay pedidos pendientes de cobro.</p>`}</div>
      <button class="b primary big full" id="oadd" ${free.length ? "" : "disabled"}>Llevar al ticket</button>`, { wide: true });
    $("#oadd", m.el).onclick = () => {
      const ids = $$("input:checked", m.el).map((i) => i.value);
      for (const id of ids) {
        const o = free.find((x) => x.id === id);
        T.orders.push({ id: o.id, number: o.number, table: o.table, total: o.total, lines: o.lines.map((l) => ({ quantity: l.quantity, name: l.name })) });
        if (!T.table && o.table) T.table = o.table;
        if (o.fulfillment !== "dine_in") T.fulfillment = "takeaway";
      }
      save(); m.close(); refreshUnpaid();
    };
  };

  /* ---------------------------------------------------------------- tickets emitidos */
  $("#b-tickets").onclick = () => ticketsList("session");
  async function ticketsList(scope, q) {
    let rows;
    try { rows = await api(`/pos/invoices?scope=${scope}${q ? "&q=" + encodeURIComponent(q) : ""}`); } catch (e) { toast(e.message, true); return; }
    const label = { F2: "Ticket", F3: "Factura", F1: "Factura", R5: "Devolución" };
    const m = modal(`<h2>Tickets</h2><div class="row" style="margin:10px 0"><div class="seg" id="sc" style="flex:1">
      ${["session", "today", "all"].map((s) => `<button data-s="${s}" aria-pressed="${s === scope}">${{ session: "Esta caja", today: "Hoy", all: "Todos" }[s]}</button>`).join("")}</div>
      <input class="b" id="tq" placeholder="Buscar nº" value="${esc(q || "")}" style="max-width:160px;text-align:left"></div>
      ${rows.length ? rows.map((r) => `<button class="list-item" data-inv="${r.id}"><span class="grow"><b>${esc(r.full_number)}</b>
        <small>${new Date(r.issued_at).toLocaleString("es-ES", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })} · ${esc(r.table_label || "")} ${esc(r.methods.map((x) => PAY[x]).join(" + "))}</small></span>
        <span class="chip ${r.status === "voided" ? "red" : r.invoice_type === "R5" ? "red" : r.invoice_type === "F3" ? "green" : ""}">${r.status === "voided" ? "Anulado" : label[r.invoice_type] || r.invoice_type}</span>
        <b class="num">${money(r.total)}</b></button>`).join("") : `<p class="empty">Sin tickets.</p>`}`, { wide: true });
    $("#sc", m.el).onclick = (e) => { const b = e.target.closest("[data-s]"); if (b) { m.close(); ticketsList(b.dataset.s, $("#tq", m.el).value); } };
    $("#tq", m.el).onkeydown = (e) => { if (e.key === "Enter") { m.close(); ticketsList(scope, e.target.value); } };
    m.el.addEventListener("click", (e) => { const b = e.target.closest("[data-inv]"); if (b) { m.close(); ticketDetail(b.dataset.inv); } });
  }
  async function ticketDetail(id) {
    let inv;
    try { inv = await api(`/pos/invoices/${id}`); } catch (e) { toast(e.message, true); return; }
    const canRefund = me.is_manager && inv.invoice_type === "F2" && inv.status === "issued" && inv.lines.some((l) => parseFloat(l.refundable) > 0);
    const canVoid = me.is_manager && inv.invoice_type === "F2" && inv.status === "issued";
    const canF3 = inv.invoice_type === "F2" && inv.status === "issued";
    const m = modal(`<h2>${esc(inv.type_label)} ${esc(inv.full_number)}</h2>
      <p class="muted">${new Date(inv.issued_at).toLocaleString("es-ES")} · ${esc(inv.created_by)}${inv.status === "voided" ? " · ANULADO: " + esc(inv.reason) : ""}${inv.rectified ? " · rectifica " + esc(inv.rectified) : ""}</p>
      <div style="margin:12px 0">${inv.lines.map((l) => `<div class="kv"><span>${esc(l.quantity)} × ${esc(l.description)}</span><b>${money(l.line_total)}</b></div>`).join("")}
      <div class="kv"><span><b>Total</b></span><b>${money(inv.total)}</b></div>
      ${inv.payments.map((p) => `<div class="kv"><span>${PAY[p.method] || p.method}${p.reference ? " · " + esc(p.reference) : ""}</span><b>${money(p.amount)}</b></div>`).join("")}</div>
      ${inv.customer ? `<p class="muted">Cliente: ${esc(inv.customer.name)} · ${esc(inv.customer.nif)}</p>` : ""}
      <div class="row" style="margin-top:12px"><button class="b" id="dp">Reimprimir</button>
      ${canF3 ? `<button class="b" id="df3">Factura con NIF</button>` : ""}
      ${canRefund ? `<button class="b" id="drf">Devolver</button>` : ""}
      ${canVoid ? `<button class="b danger" id="dv">Anular</button>` : ""}</div>`, { wide: true });
    $("#dp", m.el).onclick = () => B.printUrl(`/pos/invoices/${id}/ticket?copy=true`).catch((e) => toast(e.message, true));
    if (canF3) $("#df3", m.el).onclick = () => { m.close(); fullInvoice(inv); };
    if (canRefund) $("#drf", m.el).onclick = () => { m.close(); refund(inv); };
    if (canVoid) $("#dv", m.el).onclick = async () => {
      const reason = prompt("Motivo de la anulación (p. ej. «cobrado dos veces»):");
      if (!reason || reason.trim().length < 3) return;
      try { await api(`/pos/invoices/${id}/void`, { body: { reason } }); toast("Ticket anulado"); m.close(); refreshSession(); }
      catch (e) { toast(e.message, true); }
    };
  }
  function refund(inv) {
    const qty = new Map(inv.lines.map((l) => [l.id, parseFloat(l.refundable)]));
    let method = inv.payments[0] ? inv.payments[0].method : "cash";
    const reasons = ["Error en el pedido", "Producto en mal estado", "El cliente se ha ido"];
    const m = modal(`<h2>Devolución de ${esc(inv.full_number)}</h2><p class="muted">Sale como factura rectificativa (R5). El ticket original no se toca.</p>
      <div style="margin:12px 0">${inv.lines.filter((l) => parseFloat(l.refundable) > 0).map((l) => `<div class="kv"><span>${esc(l.description)} <small class="muted">(${esc(l.refundable)} máx.)</small></span>
        <span class="row"><button class="b" data-d="${l.id}:-1">−</button><b data-v="${l.id}" style="min-width:24px;text-align:center">${l.refundable}</b><button class="b" data-d="${l.id}:1">+</button></span></div>`).join("")}</div>
      <div class="seg" id="rm">${["cash", "card", "bizum"].map((x) => `<button data-m="${x}" aria-pressed="${x === method}">${PAY[x]}</button>`).join("")}</div>
      <p class="section-title">Motivo</p><div class="row">${reasons.map((r) => `<button class="b" data-r="${esc(r)}">${esc(r)}</button>`).join("")}</div>
      <label class="f" style="margin-top:10px"><input id="rr" maxlength="255" placeholder="Otro motivo"></label>
      <button class="b danger big full" id="rok">Devolver</button>`, { wide: true });
    m.el.addEventListener("click", async (e) => {
      const d = e.target.closest("[data-d]");
      if (d) {
        const [id, delta] = d.dataset.d.split(":"); const max = parseFloat(inv.lines.find((l) => l.id === id).refundable);
        qty.set(id, Math.max(0, Math.min(max, qty.get(id) + Number(delta)))); $(`[data-v="${id}"]`, m.el).textContent = qty.get(id);
      }
      const mb = e.target.closest("[data-m]"); if (mb) { method = mb.dataset.m; $$("#rm [data-m]", m.el).forEach((x) => x.setAttribute("aria-pressed", String(x === mb))); }
      const rb = e.target.closest("[data-r]"); if (rb) $("#rr", m.el).value = rb.dataset.r;
      if (e.target.closest("#rok")) {
        const items = [...qty.entries()].filter(([, q]) => q > 0).map(([line_id, quantity]) => ({ line_id, quantity }));
        const reason = $("#rr", m.el).value.trim();
        if (!items.length || reason.length < 3) { toast("Elige qué devolver y el motivo", true); return; }
        try {
          const r = await api(`/pos/invoices/${inv.id}/refund`, { body: { items, method, reason } });
          m.close(); toast(`Devolución ${r.full_number}: ${money(r.total)}`); B.printUrl(`/pos/invoices/${r.id}/ticket`).catch(() => {}); refreshSession();
        } catch (err) { toast(err.message, true); }
      }
    });
  }
  function fullInvoice(inv) {
    const m = modal(`<h2>Factura con NIF</h2><p class="muted">Sustituye al ${esc(inv.full_number)} (factura F3).</p>
      <form><label class="f">NIF / CIF<input name="nif" required maxlength="20" autocapitalize="characters"></label>
      <label class="f">Nombre o razón social<input name="name" required maxlength="150"></label>
      <label class="f">Dirección<input name="address" maxlength="255"></label>
      <button class="b primary big full">Emitir factura</button></form>`);
    $("form", m.el).onsubmit = async (e) => {
      e.preventDefault(); const f = e.target;
      try {
        const r = await api("/pos/invoices/full-invoice", { body: { invoice_ids: [inv.id], nif: f.nif.value, name: f.name.value, address: f.address.value || null } });
        m.close(); toast("Factura " + r.full_number); B.printUrl(`/pos/invoices/${r.id}/ticket`).catch(() => {});
      } catch (err) { toast(err.message, true); }
    };
  }

  /* ---------------------------------------------------------------- caja */
  async function refreshSession() {
    try { session = (await api("/pos/session")).session; } catch (e) { session = null; }
    $("#sess").textContent = session ? `Caja abierta · ${session.tickets} tickets · ${money(session.net_sales)}` : "Caja cerrada";
    banners();
  }
  $("#b-cash").onclick = openCash;
  function openCash() {
    if (!session) {
      const m = modal(`<h2>Abrir caja</h2><p class="muted">¿Con cuánto cambio empiezas?</p><div class="display"><span>Fondo</span><b id="of">0,00 €</b></div><div id="ok"></div>
        <button class="b ok big full" id="oo" style="margin-top:10px">Abrir caja</button>`);
      const kp = keypad($("#ok", m.el), "", (v) => { $("#of", m.el).textContent = money(kcents(v)); });
      $("#oo", m.el).onclick = async () => {
        try { session = (await api("/pos/session/open", { body: { opening_float: dec(kcents(kp.get())) } })).session; m.close(); toast("Caja abierta"); refreshSession(); }
        catch (e) { toast(e.message, true); }
      };
      return;
    }
    const s = session;
    const m = modal(`<h2>Caja · informe X</h2><p class="muted">Abierta por ${esc(s.opened_by)} · ${new Date(s.opened_at).toLocaleString("es-ES")}</p>
      <div style="margin:12px 0">
      <div class="kv"><span>Tickets</span><b>${s.tickets}</b></div><div class="kv"><span>Ventas</span><b>${money(s.gross_sales)}</b></div>
      <div class="kv"><span>Devoluciones</span><b>${money(s.refunds)}</b></div><div class="kv"><span><b>Neto</b></span><b>${money(s.net_sales)}</b></div>
      ${Object.entries(s.payments).map(([k, v]) => `<div class="kv"><span>${PAY[k] || k}</span><b>${money(v)}</b></div>`).join("")}
      ${Object.entries(s.channels).map(([k, v]) => `<div class="kv"><span>${k === "pos" ? "Barra" : "QR / web"} (${v.tickets})</span><b>${money(v.total)}</b></div>`).join("")}
      <div class="kv"><span>Debe haber en el cajón</span><b>${money(s.expected_cash)}</b></div></div>
      <div class="grid2"><button class="b" data-mv="in">Entrada de efectivo</button><button class="b" data-mv="out">Salida de efectivo</button>
      <button class="b" id="cx">Imprimir X</button><button class="b danger" id="cz">Cerrar caja (Z)</button></div>`, { wide: true });
    m.el.addEventListener("click", (e) => {
      const mv = e.target.closest("[data-mv]"); if (mv) { m.close(); movement(mv.dataset.mv); }
    });
    $("#cx", m.el).onclick = () => B.printUrl(`/pos/sessions/${s.session_id}/z-report`).catch((e) => toast(e.message, true));
    $("#cz", m.el).onclick = () => { m.close(); closeCash(); };
  }
  function movement(kind) {
    const m = modal(`<h2>${kind === "in" ? "Entrada" : "Salida"} de efectivo</h2><div class="display"><span>Importe</span><b id="mi">0,00 €</b></div><div id="mk"></div>
      <label class="f" style="margin-top:10px">Motivo<input id="mr" maxlength="255" placeholder="${kind === "in" ? "Cambio del banco" : "Pago al proveedor de pan"}"></label>
      <button class="b primary big full" id="mok">Guardar</button>`);
    const kp = keypad($("#mk", m.el), "", (v) => { $("#mi", m.el).textContent = money(kcents(v)); });
    $("#mok", m.el).onclick = async () => {
      try { session = (await api("/pos/session/movements", { body: { kind, amount: dec(kcents(kp.get())), reason: $("#mr", m.el).value.trim() } })).session; m.close(); toast("Guardado"); refreshSession(); }
      catch (e) { toast(e.message, true); }
    };
  }
  function closeCash() {
    const dens = ["500", "200", "100", "50", "20", "10", "5", "2", "1", "0.50", "0.20", "0.10", "0.05", "0.02", "0.01"];
    const expected = cents(session.expected_cash);
    const m = modal(`<h2>Cierre de caja (Z)</h2><p class="muted">Cuenta billetes y monedas del cajón.</p>
      <div class="den" style="margin:12px 0">${dens.map((d) => `<label>${money(cents(d))}<input type="number" min="0" inputmode="numeric" data-den="${d}" value=""></label>`).join("")}</div>
      <div class="kv"><span>Contado</span><b id="zc">0,00 €</b></div><div class="kv"><span>Debe haber</span><b>${money(expected)}</b></div>
      <div class="kv"><span>Descuadre</span><b id="zd" class="diff"></b></div>
      <label class="f" style="margin-top:10px">Notas<input id="zn" maxlength="500"></label>
      <button class="b danger big full" id="zok">Cerrar caja e imprimir Z</button>`, { wide: true });
    const counted = () => $$("[data-den]", m.el).reduce((s, i) => s + Math.round(parseFloat(i.dataset.den) * 100) * (parseInt(i.value, 10) || 0), 0);
    const upd = () => { const c = counted(); $("#zc", m.el).textContent = money(c); const d = c - expected; const el = $("#zd", m.el); el.textContent = money(d); el.className = "diff " + (d === 0 ? "ok" : "bad"); };
    m.el.addEventListener("input", upd); upd();
    $("#zok", m.el).onclick = async () => {
      if (!(await confirmBox("Cerrar caja", "Después no se puede cobrar hasta abrir otra vez.", "Cerrar caja", true))) return;
      const breakdown = Object.fromEntries($$("[data-den]", m.el).filter((i) => parseInt(i.value, 10) > 0).map((i) => [i.dataset.den, parseInt(i.value, 10)]));
      try {
        const r = await api("/pos/session/close", { body: Object.keys(breakdown).length ? { breakdown, notes: $("#zn", m.el).value || null } : { counted_cash: "0", notes: $("#zn", m.el).value || null } });
        m.close(); toast(`Caja cerrada · Z ${r.z_report.z_number} · descuadre ${money(r.z_report.difference)}`);
        B.printUrl(`/pos/sessions/${r.session_id}/z-report`).catch(() => {});
        refreshSession();
      } catch (e) { toast(e.message, true); }
    };
  }

  /* ---------------------------------------------------------------- gestión (encargado) */
  if (me.is_manager) $("#b-manage").onclick = () => {
    const m = modal(`<h2>Gestión</h2>
      <p class="section-title">Pedidos online</p><div class="grid2">${[15, 30, 60].map((n) => `<button class="b" data-pause="${n}">Pausar ${n} min</button>`).join("")}<button class="b ok" data-pause="0">Reanudar</button></div>
      <p class="section-title">Oferta del día (sale arriba de la carta)</p>
      <label class="f"><input id="of" maxlength="280" placeholder="Ej.: Menú dürüm + bebida a 7 € hasta las 17:00"></label>
      <div class="grid2"><button class="b" data-offer="6">Publicar 6 h</button><button class="b" data-offer="24">Publicar 24 h</button></div>
      <p class="section-title">Local</p>
      <div class="grid2"><button class="b" id="g-soldout">Agotados</button><button class="b" id="g-qr">Hoja de QR para imprimir</button>
      <button class="b" id="g-pair">Emparejar otra tablet</button><button class="b" id="g-chain">Comprobar registros fiscales</button></div>`, { wide: true });
    m.el.addEventListener("click", async (e) => {
      const p = e.target.closest("[data-pause]");
      if (p) { try { await api(`/my/venues/${cid}/pause`, { body: { minutes: Number(p.dataset.pause) } }); toast(Number(p.dataset.pause) ? "Pedidos online en pausa" : "Pedidos online activos"); } catch (err) { toast(err.message, true); } }
      const o = e.target.closest("[data-offer]");
      if (o) { try { await api(`/my/venues/${cid}/offer`, { body: { text: $("#of", m.el).value.trim() || null, hours: Number(o.dataset.offer) } }); toast("Oferta publicada"); } catch (err) { toast(err.message, true); } }
    });
    $("#g-qr", m.el).onclick = () => B.openHtml(`/my/venues/${cid}/qr-sheet`).catch((e) => toast(e.message, true));
    $("#g-chain", m.el).onclick = async () => {
      try { const r = await api(`/my/venues/${cid}/pos/fiscal-records/verify`); toast(r.ok ? `Cadena íntegra: ${r.records} registros sin alterar` : "¡Atención! " + r.errors[0], !r.ok); }
      catch (err) { toast(err.message, true); }
    };
    $("#g-pair", m.el).onclick = async () => {
      try {
        const r = await api(`/my/venues/${cid}/pos/pairing-codes`, { body: { register_id: me.register.id, device_name: "Tablet" } });
        modal(`<h2>Código de emparejamiento</h2><p class="muted">Ábrelo en la otra tablet (/app/tpv o /app/cocina). Caduca a las ${new Date(r.expires_at).toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}.</p>
          <p style="font-size:3rem;font-weight:900;letter-spacing:.12em;text-align:center;margin:20px 0" class="num">${esc(r.code)}</p>`);
      } catch (err) { toast(err.message, true); }
    };
    $("#g-soldout", m.el).onclick = () => {
      m.close();
      const mm = modal(`<h2>Agotados</h2><p class="muted">Lo que apagues desaparece de la web al momento.</p>
        ${menu.map((c) => `<p class="section-title">${esc(c.name)}</p>${c.products.map((p) => `<label class="toggle"><span>${esc(p.name)}</span><input type="checkbox" data-av="${p.id}" ${p.available ? "checked" : ""}></label>`).join("")}`).join("")}`, { wide: true, onClose: loadMenu });
      mm.el.addEventListener("change", async (e) => {
        const i = e.target.closest("[data-av]"); if (!i) return;
        try { await api(`/my/venues/${cid}/menu/products/${i.dataset.av}/availability`, { method: "PATCH", body: { is_available: i.checked } }); }
        catch (err) { i.checked = !i.checked; toast(err.message, true); }
      });
    };
  };
  $("#b-out").onclick = async () => { if (await confirmBox("Salir", "Se cierra tu sesión en este TPV (el ticket en curso se guarda).", "Salir")) B.logout(); };

  /* ---------------------------------------------------------------- arranque */
  renderTicket();
  try { await loadMenu(); } catch (e) { toast(e.message, true); }
  await refreshSession();
  refreshUnpaid();
  setInterval(refreshUnpaid, 60000);
})();

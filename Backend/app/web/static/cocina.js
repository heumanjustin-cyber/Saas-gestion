/* BUHOS · pantalla de cocina: pedidos en vivo, tiempos, estados, comanda, pausa y agotados. */
(async () => {
  "use strict";
  const B = window.BUHOS;
  const { $, $$, esc, api, toast, modal } = B;
  const root = $("#app");
  const me = await B.login(root, { title: "Cocina", subtitle: "Empareja la pantalla de cocina con tu local.", deviceName: "Cocina" });
  const cid = me.company.id;
  const orders = new Map();
  const seen = new Set();
  let sound = B.LS.get("kds_sound") !== false;
  let autoPrint = B.LS.get("kds_autoprint") === true;
  let firstLoad = true;

  root.innerHTML = `
    <div class="bar">
      <div><h1>${esc(me.company.name)} · Cocina</h1><div class="who">${esc(me.name)}</div></div>
      <span class="live" id="live"><i></i><span>Conectando…</span></span>
      <span class="sp"></span>
      <span class="num" id="clock" style="font-weight:800"></span>
      <button class="b" id="pause">Pausar pedidos</button>
      <button class="b" id="soldout">Agotados</button>
      <button class="b" id="settings" aria-label="Ajustes">⚙</button>
    </div>
    <div class="board">
      <section class="col"><h2>Nuevos <span id="c-new">0</span></h2><div class="cards" id="col-new"></div></section>
      <section class="col"><h2>En cocina <span id="c-cook">0</span></h2><div class="cards" id="col-cook"></div></section>
      <section class="col"><h2>Listos <span id="c-ready">0</span></h2><div class="cards" id="col-ready"></div></section>
    </div>`;

  /* ---------------------------------------------------------------- aviso sonoro */
  let audio;
  function chime() {
    if (!sound) return;
    try {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      [0, 0.22, 0.44].forEach((t, i) => {
        const o = audio.createOscillator(); const g = audio.createGain();
        o.type = "triangle"; o.frequency.value = [880, 1175, 1568][i];
        o.connect(g); g.connect(audio.destination);
        g.gain.setValueAtTime(0.0001, audio.currentTime + t);
        g.gain.exponentialRampToValueAtTime(0.5, audio.currentTime + t + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, audio.currentTime + t + 0.3);
        o.start(audio.currentTime + t); o.stop(audio.currentTime + t + 0.32);
      });
    } catch (e) { /* el navegador bloquea el audio hasta el primer toque */ }
    if (navigator.vibrate) navigator.vibrate([200, 100, 200]);
  }
  document.addEventListener("pointerdown", () => { if (!audio && sound) { try { audio = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { /* sin audio */ } } }, { once: true });

  /* ---------------------------------------------------------------- pintar */
  const WHERE = (o) => o.fulfillment === "dine_in" ? (o.table || "En sala")
    : o.fulfillment === "delivery" ? "🛵 Domicilio" : "🛍 Recoger" + (o.customer_name ? " · " + o.customer_name : "");
  function age(o) {
    const mins = Math.floor((Date.now() - new Date(o.created_at).getTime()) / 60000);
    return { mins, label: mins < 1 ? "ahora" : mins + " min" };
  }
  function card(o) {
    const a = age(o);
    const cls = a.mins >= 20 ? "late" : a.mins >= 10 ? "warn" : "";
    const lines = o.lines.map((l) => `<li><b>${l.quantity} × ${esc(l.name)}</b>
      ${l.modifiers.length ? `<div class="mods">${esc(l.modifiers.map((m) => m.name).join(" · "))}</div>` : ""}
      ${l.removed.map((r) => `<div class="no">${esc(r)}</div>`).join("")}
      ${l.note ? `<div class="mods">«${esc(l.note)}»</div>` : ""}</li>`).join("");
    const sched = o.scheduled_for ? `<div class="meta">⏰ Para las ${new Date(o.scheduled_for).toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}</div>` : "";
    const deliv = o.fulfillment === "delivery" ? `<div class="meta">${esc(o.delivery_address || "")} · ${esc(o.customer_phone || "")}</div>` : "";
    const chan = o.channel === "pos" ? "" : `<span class="chip qr">${o.channel === "qr" ? "QR" : "Web"}</span>`;
    let acts = "";
    if (o.status === "pending") {
      acts = `<div class="eta">${[10, 15, 20, 30].map((m) => `<button class="b ok" data-act="accepted" data-eta="${m}">${m}′</button>`).join("")}</div>
        <button class="b danger" data-act="reject">Rechazar</button><button class="b" data-print>🖨</button>`;
    } else if (o.status === "accepted") {
      acts = `<button class="b" data-act="preparing">Empezar</button><button class="b ok" data-act="ready">¡Listo!</button><button class="b" data-print>🖨</button>`;
    } else if (o.status === "preparing") {
      acts = `<button class="b ok big" data-act="ready">¡Listo!</button><button class="b" data-print>🖨</button>`;
    } else if (o.status === "ready") {
      acts = `<button class="b primary big" data-act="completed">Entregado</button><button class="b" data-act="preparing">↩</button>`;
    }
    return `<article class="ticket ${seen.has(o.id) ? "" : "new"}" data-id="${o.id}">
      <header><span class="n">${esc(o.number)}</span><span class="where">${esc(WHERE(o))}</span>${chan}<span class="age ${cls}">${a.label}</span></header>
      <ul>${lines}</ul>${o.customer_note ? `<p class="note">${esc(o.customer_note)}</p>` : ""}${sched}${deliv}
      <div class="acts">${acts}</div></article>`;
  }
  function render() {
    const list = [...orders.values()].sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
    const cols = { new: [], cook: [], ready: [] };
    for (const o of list) {
      if (o.status === "pending") cols.new.push(o);
      else if (o.status === "accepted" || o.status === "preparing") cols.cook.push(o);
      else if (o.status === "ready") cols.ready.push(o);
    }
    for (const [k, arr] of Object.entries(cols)) {
      $("#col-" + k).innerHTML = arr.length ? arr.map(card).join("") : `<p class="empty">Nada por aquí</p>`;
      $("#c-" + k).textContent = String(arr.length);
    }
    for (const o of list) seen.add(o.id);
    document.title = (cols.new.length ? `(${cols.new.length}) ` : "") + "Cocina · BUHOS";
  }
  function upsert(o, fromStream) {
    const prev = orders.get(o.id);
    if (["completed", "rejected", "cancelled"].includes(o.status)) orders.delete(o.id); else orders.set(o.id, o);
    if (fromStream && !prev && o.status === "pending" && !firstLoad) {
      chime(); toast(`Pedido nuevo ${o.number} · ${WHERE(o)}`);
      if (autoPrint) B.printUrl(`/my/venues/${cid}/orders/${o.id}/kitchen-ticket`).catch(() => {});
    }
  }

  /* ---------------------------------------------------------------- en vivo */
  const live = $("#live");
  B.sse(`/my/venues/${cid}/orders/stream`, (ev, data) => {
    if (ev === "snapshot") { orders.clear(); data.forEach((o) => upsert(o, false)); firstLoad = false; }
    else if (ev === "order") upsert(data, true);
    render();
  }, (st) => {
    live.className = "live " + (st === "on" ? "on" : st === "off" ? "off" : "");
    $("span", live).textContent = st === "on" ? "En directo" : st === "off" ? "Sin conexión" : "Conectando…";
  });
  setInterval(() => { $("#clock").textContent = new Date().toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" }); render(); }, 30000);
  $("#clock").textContent = new Date().toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });

  /* ---------------------------------------------------------------- acciones */
  async function setStatus(id, status, extra = {}) {
    try { upsert(await api(`/my/venues/${cid}/orders/${id}/status`, { body: { status, ...extra } }), false); render(); }
    catch (e) { toast(e.message, true); }
  }
  root.addEventListener("click", async (e) => {
    const t = e.target.closest("[data-id]");
    const act = e.target.closest("[data-act]");
    if (t && e.target.closest("[data-print]")) { B.printUrl(`/my/venues/${cid}/orders/${t.dataset.id}/kitchen-ticket`).catch((err) => toast(err.message, true)); return; }
    if (!t || !act) return;
    if (act.dataset.act === "reject") return reject(t.dataset.id);
    setStatus(t.dataset.id, act.dataset.act, act.dataset.eta ? { eta_minutes: Number(act.dataset.eta) } : {});
  });
  function reject(id) {
    const reasons = ["Nos hemos quedado sin ese producto", "Cocina cerrada", "Fuera de la zona de reparto", "No podemos atenderlo ahora"];
    const m = modal(`<h2>Rechazar pedido ${esc(orders.get(id).number)}</h2><p class="muted">El cliente verá el motivo en su móvil.</p>
      <div style="display:grid;gap:8px;margin-top:14px">${reasons.map((r) => `<button class="b" data-r="${esc(r)}">${esc(r)}</button>`).join("")}</div>
      <label class="f" style="margin-top:12px">Otro motivo<input id="rr" maxlength="255"></label>
      <div class="row end"><button class="b danger" data-r="">Rechazar</button></div>`);
    m.el.addEventListener("click", (e) => {
      const b = e.target.closest("[data-r]"); if (!b) return;
      const reason = b.dataset.r || $("#rr", m.el).value.trim();
      if (!reason) { toast("Escribe el motivo", true); return; }
      m.close(); setStatus(id, "rejected", { reason });
    });
  }
  $("#pause").onclick = () => {
    const m = modal(`<h2>Pausar pedidos online</h2><p class="muted">La web dejará de aceptar pedidos durante ese tiempo. Los de barra siguen igual.</p>
      <div class="grid2" style="margin-top:14px">${[15, 30, 60, 120].map((n) => `<button class="b big" data-min="${n}">${n} min</button>`).join("")}</div>
      <button class="b ok full big" style="margin-top:10px" data-min="0">Reanudar ya</button>`);
    m.el.addEventListener("click", async (e) => {
      const b = e.target.closest("[data-min]"); if (!b) return;
      try {
        const r = await api(`/my/venues/${cid}/pause`, { body: { minutes: Number(b.dataset.min) } });
        $("#pause").textContent = r.ordering_paused_until ? "En pausa hasta " + new Date(r.ordering_paused_until).toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" }) : "Pausar pedidos";
        $("#pause").classList.toggle("danger", !!r.ordering_paused_until);
        m.close();
      } catch (err) { toast(err.message, true); }
    });
  };
  $("#soldout").onclick = async () => {
    let menu;
    try { menu = await api("/pos/catalog"); } catch (e) { toast(e.message, true); return; }
    const m = modal(`<h2>Agotados</h2><p class="muted">Lo que apagues desaparece de la web al momento.</p>
      ${menu.map((c) => `<p class="section-title">${esc(c.name)}</p>${c.products.map((p) => `<label class="toggle"><span>${esc(p.name)}</span>
        <input type="checkbox" data-p="${p.id}" ${p.available ? "checked" : ""}></label>`).join("")}`).join("")}`, { wide: true });
    m.el.addEventListener("change", async (e) => {
      const i = e.target.closest("[data-p]"); if (!i) return;
      try { await api(`/my/venues/${cid}/menu/products/${i.dataset.p}/availability`, { method: "PATCH", body: { is_available: i.checked } }); toast(i.checked ? "Disponible" : "Agotado"); }
      catch (err) { i.checked = !i.checked; toast(err.message, true); }
    });
  };
  $("#settings").onclick = () => {
    const m = modal(`<h2>Ajustes de esta pantalla</h2>
      <label class="toggle"><span>Sonido al entrar un pedido</span><input type="checkbox" id="s-sound" ${sound ? "checked" : ""}></label>
      <label class="toggle"><span>Imprimir la comanda sola al entrar</span><input type="checkbox" id="s-print" ${autoPrint ? "checked" : ""}></label>
      <button class="b full" style="margin-top:10px" id="s-test">Probar sonido</button>
      <button class="b ghost full" style="margin-top:10px" id="s-out">Cerrar sesión</button>`);
    $("#s-sound", m.el).onchange = (e) => { sound = e.target.checked; B.LS.set("kds_sound", sound); };
    $("#s-print", m.el).onchange = (e) => { autoPrint = e.target.checked; B.LS.set("kds_autoprint", autoPrint); };
    $("#s-test", m.el).onclick = () => { const s = sound; sound = true; chime(); sound = s; };
    $("#s-out", m.el).onclick = () => B.logout();
  };
})();

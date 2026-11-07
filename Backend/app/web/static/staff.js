/* BUHOSS · base común del TPV y la cocina: acceso, API, eventos en vivo, ventanas e impresión. */
window.BUHOS = (() => {
  "use strict";
  const P = "buhos-staff:";
  const LS = {
    get(k) { try { return JSON.parse(localStorage.getItem(P + k)); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(P + k, JSON.stringify(v)); } catch (e) { /* sin almacenamiento */ } },
    del(k) { try { localStorage.removeItem(P + k); } catch (e) { /* sin almacenamiento */ } },
  };
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const cents = (v) => Math.round(parseFloat(v || "0") * 100);
  const eur = (c) => (typeof c === "string" ? cents(c) : c) / 100;
  const money = (v) => eur(v).toLocaleString("es-ES", { style: "currency", currency: "EUR" });
  const dec = (c) => (c / 100).toFixed(2);
  const state = { token: LS.get("pos_token"), device: LS.get("device"), me: null };

  class ApiError extends Error { constructor(status, msg) { super(msg); this.status = status; } }

  async function api(path, opts = {}) {
    const headers = { Accept: "application/json" };
    if (opts.body !== undefined) headers["Content-Type"] = "application/json";
    if (opts.auth !== false && state.token) headers.Authorization = "Bearer " + state.token;
    if (opts.device && state.device) headers["X-Device-Token"] = state.device.token;
    if (opts.bearer) headers.Authorization = "Bearer " + opts.bearer;
    let r;
    try {
      r = await fetch(path, { method: opts.method || (opts.body !== undefined ? "POST" : "GET"), headers,
                              body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined });
    } catch (e) { throw new ApiError(0, "Sin conexión con el servidor. Revisa el wifi."); }
    if (opts.raw) { if (!r.ok) throw new ApiError(r.status, "Error " + r.status); return r; }
    const data = r.status === 204 ? null : await r.json().catch(() => null);
    if (!r.ok) {
      const d = data && data.detail;
      const msg = typeof d === "string" ? d : (d && d.message) || (Array.isArray(d) ? d.map((x) => x.msg).join(". ") : "Error " + r.status);
      if (r.status === 401 && opts.auth !== false && !opts.bearer) { logout(); }
      throw new ApiError(r.status, msg);
    }
    return data;
  }

  /* ---------------------------------------------------------------- avisos y ventanas */
  let tt;
  function toast(msg, bad) {
    let el = $("#b-toast");
    if (!el) { el = document.createElement("div"); el.id = "b-toast"; el.className = "toast"; el.setAttribute("role", "status"); document.body.appendChild(el); }
    el.textContent = msg; el.classList.toggle("bad", !!bad); el.hidden = false;
    clearTimeout(tt); tt = setTimeout(() => { el.hidden = true; }, bad ? 4000 : 2200);
  }
  function modal(html, opts = {}) {
    const wrap = document.createElement("div");
    wrap.className = "modal-wrap";
    wrap.innerHTML = `<div class="modal ${opts.wide ? "wide" : ""}" role="dialog" aria-modal="true"><button class="x" data-close aria-label="Cerrar">×</button>${html}</div>`;
    document.body.appendChild(wrap);
    const close = () => { if (wrap.isConnected) { wrap.remove(); if (opts.onClose) opts.onClose(); } };
    wrap.addEventListener("click", (e) => { if (e.target === wrap || e.target.closest("[data-close]")) close(); });
    const onKey = (e) => { if (e.key === "Escape") { close(); removeEventListener("keydown", onKey); } };
    addEventListener("keydown", onKey);
    return { el: $(".modal", wrap), close };
  }
  function confirmBox(title, text, okLabel = "Confirmar", danger = false) {
    return new Promise((resolve) => {
      const m = modal(`<h2>${esc(title)}</h2><p class="muted" style="margin:8px 0 18px">${esc(text)}</p>
        <div class="row end"><button class="b" data-close>Cancelar</button><button class="b ${danger ? "danger" : "primary"}" data-ok>${esc(okLabel)}</button></div>`,
        { onClose: () => resolve(false) });
      $("[data-ok]", m.el).onclick = () => { resolve(true); m.close(); };
    });
  }

  /* ---------------------------------------------------------------- impresión (térmica 80 mm vía navegador) */
  function printHtml(html) {
    const f = document.createElement("iframe");
    f.style.cssText = "position:fixed;right:0;bottom:0;width:1px;height:1px;border:0;opacity:0";
    document.body.appendChild(f);
    f.onload = () => { try { f.contentWindow.focus(); f.contentWindow.print(); } catch (e) { toast("No se pudo imprimir", true); } setTimeout(() => f.remove(), 60000); };
    f.srcdoc = html;
  }
  async function printUrl(path) {
    const r = await api(path, { raw: true });
    printHtml(await r.text());
  }
  async function openHtml(path) {
    const r = await api(path, { raw: true });
    const url = URL.createObjectURL(new Blob([await r.text()], { type: "text/html" }));
    window.open(url, "_blank", "noopener");
  }

  /* ---------------------------------------------------------------- eventos en vivo (SSE con cabecera) */
  function sse(path, onEvent, onStatus) {
    let stopped = false; let delay = 1500; let ctrl = null;
    async function connect() {
      while (!stopped) {
        onStatus && onStatus("connecting");
        try {
          ctrl = new AbortController();
          const r = await fetch(path, { headers: { Authorization: "Bearer " + state.token, Accept: "text/event-stream" }, signal: ctrl.signal });
          if (r.status === 401) { logout(); return; }
          if (!r.ok || !r.body) throw new Error("http " + r.status);
          onStatus && onStatus("on"); delay = 1500;
          const reader = r.body.getReader(); const dec = new TextDecoder(); let buf = "";
          for (;;) {
            const { value, done } = await reader.read();
            if (done) break;
            buf += dec.decode(value, { stream: true });
            let i;
            while ((i = buf.indexOf("\n\n")) >= 0) {
              const block = buf.slice(0, i); buf = buf.slice(i + 2);
              let ev = "message"; let data = "";
              for (const line of block.split("\n")) {
                if (line.startsWith("event:")) ev = line.slice(6).trim();
                else if (line.startsWith("data:")) data += line.slice(5).trim();
              }
              if (data) { try { onEvent(ev, JSON.parse(data)); } catch (e) { console.warn(e); } }
            }
          }
        } catch (e) { if (stopped) return; }
        onStatus && onStatus("off");
        await new Promise((res) => setTimeout(res, delay));
        delay = Math.min(delay * 2, 15000);
      }
    }
    connect();
    return () => { stopped = true; if (ctrl) ctrl.abort(); };
  }

  /* ---------------------------------------------------------------- acceso */
  function logout(forgetDevice) {
    LS.del("pos_token"); state.token = null;
    if (forgetDevice) { LS.del("device"); state.device = null; }
    location.reload();
  }
  function setToken(t) { state.token = t; LS.set("pos_token", t); }

  async function login(root, opts = {}) {
    if (state.token) {
      try { state.me = await api("/pos/me"); return state.me; } catch (e) { setToken(null); LS.del("pos_token"); }
    }
    return new Promise((resolve) => {
      const done = async (token) => { setToken(token); state.me = await api("/pos/me"); root.innerHTML = ""; resolve(state.me); };
      const card = (inner) => { root.innerHTML = `<div class="login"><div class="card">${inner}</div></div>`; return $(".card", root); };

      function showStaff() {
        api("/pos/staff", { device: true, auth: false }).then((staff) => {
          const c = card(`<h2>${esc(state.device.company.name)}</h2><p>${esc(state.device.register.name)} · ¿Quién eres?</p>
            ${staff.length ? `<div class="staff">${staff.map((s) => `<button data-emp="${s.employee_id}" data-name="${esc(s.name)}">${esc(s.name)}</button>`).join("")}</div>`
              : `<p class="err">Aún no hay nadie con PIN. El dueño lo crea desde el panel (personal del TPV).</p>`}
            <div class="row" style="margin-top:18px"><button class="b ghost" data-owner>Cuenta del dueño</button><button class="b ghost" data-unpair>Desemparejar</button></div>`);
          c.onclick = (e) => {
            const b = e.target.closest("[data-emp]");
            if (b) showPin(b.dataset.emp, b.dataset.name);
            if (e.target.closest("[data-owner]")) showOwner();
            if (e.target.closest("[data-unpair]")) confirmBox("Desemparejar", "Esta tablet dejará de funcionar hasta emparejarla de nuevo.", "Desemparejar", true).then((ok) => ok && logout(true));
          };
        }).catch((e) => {
          if (e.status === 401) { LS.del("device"); state.device = null; showStart(e.message); } else card(`<p class="err">${esc(e.message)}</p><button class="b" onclick="location.reload()">Reintentar</button>`);
        });
      }
      function showPin(emp, name) {
        let pin = "";
        const c = card(`<h2>Hola, ${esc(name)}</h2><p>Escribe tu PIN</p><div class="dots" id="dots"></div><div id="perr"></div>
          <div class="pin">${[1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => `<button data-d="${n}">${n}</button>`).join("")}
          <button data-back aria-label="Borrar">⌫</button><button data-d="0">0</button><button data-ok class="b primary">OK</button></div>
          <button class="b ghost full" style="margin-top:12px" data-staff>Volver</button>`);
        const dots = () => { $("#dots", c).innerHTML = Array.from({ length: Math.max(4, pin.length) }, (_, i) => `<i class="${i < pin.length ? "on" : ""}"></i>`).join(""); };
        dots();
        const submit = async () => {
          if (pin.length < 4) return;
          try { const r = await api("/pos/login", { body: { employee_id: emp, pin }, device: true, auth: false }); await done(r.access_token); }
          catch (e) { pin = ""; dots(); $("#perr", c).innerHTML = `<p class="err">${esc(e.message)}</p>`; if (navigator.vibrate) navigator.vibrate(120); }
        };
        c.onclick = (e) => {
          const d = e.target.closest("[data-d]");
          if (d && pin.length < 6) { pin += d.dataset.d; dots(); if (pin.length === 6) submit(); }
          if (e.target.closest("[data-back]")) { pin = pin.slice(0, -1); dots(); }
          if (e.target.closest("[data-ok]")) submit();
          if (e.target.closest("[data-staff]")) showStaff();
        };
        const onKey = (e) => {
          if (!c.isConnected) { removeEventListener("keydown", onKey); return; }
          if (/^\d$/.test(e.key) && pin.length < 6) { pin += e.key; dots(); }
          if (e.key === "Backspace") { pin = pin.slice(0, -1); dots(); }
          if (e.key === "Enter") submit();
        };
        addEventListener("keydown", onKey);
      }
      function showOwner(errMsg) {
        const c = card(`<h2>Cuenta del dueño</h2><p>Entra con tu email de BUHOSS.</p>${errMsg ? `<p class="err">${esc(errMsg)}</p>` : ""}
          <form><label class="f">Email<input name="email" type="email" autocomplete="username" required></label>
          <label class="f">Contraseña<input name="password" type="password" autocomplete="current-password" required></label>
          <button class="b primary full">Entrar</button></form>
          <button class="b ghost full" style="margin-top:10px" data-back>Volver</button>`);
        $("[data-back]", c).onclick = () => (state.device ? showStaff() : showStart());
        $("form", c).onsubmit = async (e) => {
          e.preventDefault();
          const f = e.target;
          try {
            const r = await api("/login", { body: { email: f.email.value, password: f.password.value }, auth: false });
            if (!r || !r.access_token) throw new Error((r && r.error) || "Email o contraseña incorrectos");
            const user = r.access_token;
            const companies = await api("/my-companies", { bearer: user });
            if (!companies.length) throw new Error("Tu cuenta no tiene ningún local todavía.");
            const pick = (list, label, render) => new Promise((res) => {
              if (list.length === 1) return res(list[0]);
              const cc = card(`<h2>${label}</h2>${list.map((x, i) => `<button class="list-item" data-i="${i}"><span class="grow"><b>${esc(render(x))}</b></span></button>`).join("")}`);
              cc.onclick = (ev) => { const b = ev.target.closest("[data-i]"); if (b) res(list[Number(b.dataset.i)]); };
            });
            const company = await pick(companies, "¿Qué local?", (x) => x.name);
            let registers = await api(`/my/venues/${company.id}/pos/registers`, { bearer: user });
            registers = registers.filter((x) => x.is_active);
            if (!registers.length) registers = [await api(`/my/venues/${company.id}/pos/registers`, { bearer: user, body: { name: "Caja 1" } })];
            const reg = await pick(registers, "¿Qué caja?", (x) => x.name);
            const s = await api(`/my/venues/${company.id}/pos/owner-session`, { bearer: user, body: { register_id: reg.id } });
            await done(s.access_token);
          } catch (err) { showOwner(err.message); }
        };
      }
      function showStart(errMsg) {
        const c = card(`<h2>${esc(opts.title || "BUHOSS")}</h2><p>${esc(opts.subtitle || "Empareja esta pantalla con tu local.")}</p>
          ${errMsg ? `<p class="err">${esc(errMsg)}</p>` : ""}
          <div class="tabs"><button aria-pressed="true" data-tab="pair">Emparejar tablet</button><button aria-pressed="false" data-tab="owner">Cuenta del dueño</button></div>
          <form data-pair><label class="f">Código de emparejamiento<input name="code" autocomplete="off" autocapitalize="characters" maxlength="12" required placeholder="Ej.: K7M2PQ9X"></label>
          <label class="f">Nombre de esta pantalla<input name="name" maxlength="80" value="${esc(opts.deviceName || "Tablet")}"></label>
          <button class="b primary full">Emparejar</button></form>
          <p class="muted" style="margin-top:14px;font-size:.85rem">El código lo genera el dueño en el panel (TPV → Emparejar). Caduca en 15 minutos y vale una vez.</p>`);
        c.onclick = (e) => { const t = e.target.closest("[data-tab]"); if (t && t.dataset.tab === "owner") showOwner(); };
        $("[data-pair]", c).onsubmit = async (e) => {
          e.preventDefault();
          try {
            const r = await api("/pos/pair", { body: { code: e.target.code.value.trim().toUpperCase(), device_name: e.target.name.value }, auth: false });
            state.device = { token: r.device_token, id: r.device_id, company: r.company, register: r.register };
            LS.set("device", state.device);
            showStaff();
          } catch (err) { showStart(err.message); }
        };
      }
      if (state.device) showStaff(); else showStart();
    });
  }

  return { $, $$, esc, cents, money, dec, api, toast, modal, confirmBox, printHtml, printUrl, openHtml, sse, login, logout, state, LS };
})();

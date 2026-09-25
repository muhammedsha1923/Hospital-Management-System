/* Hospital Management System — progressive enhancement only. Pages work without JavaScript. */
(function () {
  "use strict";
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const csrf = () => (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || ($("input[name=csrfmiddlewaretoken]") || {}).value;

  function toast(message, isError) {
    const t = document.createElement("div");
    t.className = "toast" + (isError ? " error" : "");
    t.setAttribute("role", "status");
    t.textContent = message;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3500);
  }

  // Mobile navigation
  const menuBtn = $("#menu-btn");
  if (menuBtn) {
    menuBtn.addEventListener("click", () => {
      const open = document.body.classList.toggle("nav-open");
      menuBtn.setAttribute("aria-expanded", open);
    });
    document.addEventListener("click", (e) => {
      if (document.body.classList.contains("nav-open") && !e.target.closest(".sidebar") && e.target !== menuBtn) {
        document.body.classList.remove("nav-open");
      }
    });
  }

  // Dismissible alerts (success messages fade after a few seconds)
  $$(".alert").forEach((a) => {
    const close = $("button", a);
    if (close) close.addEventListener("click", () => a.remove());
    if (a.classList.contains("alert-success")) setTimeout(() => a.remove(), 6000);
  });

  // Confirmation dialogs: <form data-confirm="Are you sure?"> or <a/button data-confirm>
  document.addEventListener("submit", (e) => {
    const msg = e.target.dataset && e.target.dataset.confirm;
    if (msg && !window.confirm(msg)) { e.preventDefault(); e.stopImmediatePropagation(); }
  }, true);
  document.addEventListener("click", (e) => {
    const el = e.target.closest("a[data-confirm], button[data-confirm]");
    if (el && !window.confirm(el.dataset.confirm)) e.preventDefault();
    if (e.target.closest("[data-print]")) window.print();
  });

  // Live table filtering: <input data-filter-table="#tbl"> and <select data-filter-table="#tbl" data-filter-attr="status">
  function applyFilters(tableSel) {
    const table = $(tableSel);
    if (!table) return;
    const text = ($(`input[data-filter-table="${tableSel}"]`) || { value: "" }).value.trim().toLowerCase();
    const selects = $$(`select[data-filter-table="${tableSel}"]`);
    let shown = 0;
    $$("tbody tr[data-search]", table).forEach((row) => {
      let ok = !text || row.dataset.search.includes(text);
      selects.forEach((s) => { if (s.value && row.dataset[s.dataset.filterAttr] !== s.value) ok = false; });
      row.hidden = !ok;
      if (ok) shown++;
    });
    const empty = $(`[data-empty-for="${tableSel}"]`);
    if (empty) empty.hidden = shown > 0;
  }
  $$("[data-filter-table]").forEach((el) => {
    const sel = el.dataset.filterTable;
    el.addEventListener(el.tagName === "SELECT" ? "change" : "input", () => applyFilters(sel));
  });

  // Dynamic appointment status updates (falls back to normal form post without JS)
  document.addEventListener("submit", async (e) => {
    const form = e.target.closest("form.js-status-form");
    if (!form || e.defaultPrevented) return;
    e.preventDefault();
    const box = form.closest(".appt-actions");
    try {
      const res = await fetch(form.action, { method: "POST", body: new FormData(form),
        headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrf() } });
      const data = await res.json();
      toast(data.message, !data.ok);
      if (data.ok) {
        box.innerHTML = data.actions_html;
        const holder = box.closest("[data-appt]");
        const badge = holder && $(".appt-badge", holder);
        if (badge) { badge.textContent = data.label; badge.className = "badge appt-badge badge-" + data.status.toLowerCase(); }
        if (holder) { holder.dataset.status = data.status; }
      }
    } catch (err) { form.submit(); }
  });

  // Appointment form: date/time validation, department → doctor filtering, free-slot picker
  const apptForm = $("#appointment-form");
  if (apptForm) {
    const dept = $("#id_department"), doctor = $("#id_doctor"), date = $("#id_date"), time = $("#id_time");
    const slotBox = $("#slot-box"), hint = $("#time-hint");
    const editingId = apptForm.dataset.editing || "";
    const today = new Date(); today.setMinutes(today.getMinutes() - today.getTimezoneOffset());
    date.min = today.toISOString().slice(0, 10);

    function filterDoctors() {
      const d = dept.value; let firstVisible = null;
      $$("option", doctor).forEach((o) => {
        if (!o.value) return;
        const match = !d || o.dataset.department === d;
        o.hidden = !match; o.disabled = !match;
        if (match && !firstVisible) firstVisible = o;
      });
      const cur = doctor.selectedOptions[0];
      if (cur && cur.value && cur.disabled) doctor.value = "";
    }
    async function loadSlots() {
      if (!doctor.value || !date.value) { slotBox.innerHTML = ""; return; }
      slotBox.innerHTML = '<span class="muted small">Checking availability…</span>';
      try {
        const res = await fetch(`${apptForm.dataset.slotsUrl}?doctor=${doctor.value}&date=${date.value}&exclude=${editingId}`);
        const data = await res.json();
        slotBox.innerHTML = "";
        if (!data.slots || !data.slots.length) { slotBox.innerHTML = '<span class="muted small">No slots on this day.</span>'; return; }
        data.slots.forEach((s) => {
          const b = document.createElement("button");
          b.type = "button"; b.className = "slot" + (time.value === s.time ? " selected" : ""); b.textContent = s.time; b.disabled = !s.free;
          b.addEventListener("click", () => { time.value = s.time; $$(".slot", slotBox).forEach((x) => x.classList.remove("selected")); b.classList.add("selected"); validateTime(); });
          slotBox.appendChild(b);
        });
        if (!data.slots.some((s) => s.free)) slotBox.insertAdjacentHTML("beforeend", '<span class="muted small">Fully booked — try another day.</span>');
      } catch (err) { slotBox.innerHTML = ""; }
    }
    function validateTime() {
      time.setCustomValidity(""); hint.textContent = "";
      if (!date.value || !time.value) return;
      const chosen = new Date(`${date.value}T${time.value}`);
      if (chosen <= new Date()) { const m = "Choose a date and time in the future."; time.setCustomValidity(m); hint.textContent = m; }
    }
    dept.addEventListener("change", () => { filterDoctors(); loadSlots(); });
    doctor.addEventListener("change", () => {
      const o = doctor.selectedOptions[0];
      if (o && o.dataset.department && dept.value !== o.dataset.department) dept.value = o.dataset.department;
      loadSlots();
    });
    date.addEventListener("change", () => { validateTime(); loadSlots(); });
    time.addEventListener("input", () => { validateTime(); $$(".slot", slotBox).forEach((x) => x.classList.toggle("selected", x.textContent === time.value)); });
    apptForm.addEventListener("submit", (e) => { validateTime(); if (!apptForm.checkValidity()) { e.preventDefault(); apptForm.reportValidity(); } });
    filterDoctors(); loadSlots();
  }

  // Dynamic formsets (bill items, prescriptions)
  $$("[data-formset]").forEach((fs) => {
    const prefix = fs.dataset.formset;
    const total = $(`#id_${prefix}-TOTAL_FORMS`), tpl = $(`#${prefix}-empty`), list = $(".formset-list", fs);
    const add = $("[data-formset-add]", fs);
    if (add) add.addEventListener("click", () => {
      const idx = parseInt(total.value, 10);
      list.insertAdjacentHTML("beforeend", tpl.innerHTML.replace(/__prefix__/g, idx));
      total.value = idx + 1; recalcBill();
    });
    fs.addEventListener("change", (e) => {
      if (e.target.matches("input[type=checkbox][name$=DELETE]")) e.target.closest(".formset-row").classList.toggle("deleted", e.target.checked);
      recalcBill();
    });
    fs.addEventListener("input", recalcBill);
  });

  // Live totals on the bill form
  function recalcBill() {
    const out = $("#bill-totals"); if (!out) return;
    let sub = 0;
    $$(".formset-row").forEach((row) => {
      if (row.classList.contains("deleted")) return;
      const q = parseFloat(($("input[name$=quantity]", row) || {}).value) || 0;
      const p = parseFloat(($("input[name$=unit_price]", row) || {}).value) || 0;
      sub += q * p;
    });
    const disc = parseFloat(($("#id_discount") || {}).value) || 0;
    $("#t-sub").textContent = sub.toFixed(2);
    $("#t-total").textContent = Math.max(sub - disc, 0).toFixed(2);
  }
  const disc = $("#id_discount"); if (disc) disc.addEventListener("input", recalcBill);
  recalcBill();
})();

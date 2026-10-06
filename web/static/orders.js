'use strict';
(() => {
  const $ = (id) => document.getElementById(id);
  const node = (tag, text, className) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (className) n.className = className; return n; };
  const date = (value) => value ? new Date(value).toLocaleString('en-GB', {dateStyle: 'medium', timeStyle: 'short'}) : 'Unknown';
  const age = (seconds) => seconds < 3600 ? Math.floor(seconds / 60) + ' minutes' : seconds < 86400 ? Math.floor(seconds / 3600) + ' hours' : Math.floor(seconds / 86400) + ' days';
  const showError = (message) => { $('orders-error').textContent = message; $('orders-error').hidden = false; };
  let sequence = 0;
  async function api(path) {
    const response = await fetch(path, {credentials: 'same-origin', cache: 'no-store', redirect: 'error'});
    if (response.status === 401) { location.replace('/login'); throw new Error('Please sign in.'); }
    if (!response.ok) throw new Error(response.status === 403 ? 'Your account scope is not available for this sample.' : 'Order evidence is temporarily unavailable. Please try again.');
    return response.json();
  }
  function lineTable(lines) {
    const wrap = node('div', undefined, 'table-scroll'); const table = node('table', undefined, 'line-table');
    const head = node('thead'); const tr = node('tr');
    ['Line ref', 'Position', 'SKU / description', 'Captured quantity', 'Unit text', 'Captured price'].forEach((label) => { const th = node('th', label); th.scope = 'col'; tr.append(th); });
    head.append(tr); table.append(head); const body = node('tbody');
    lines.forEach((line) => {
      const row = node('tr'); row.append(node('td', line.unique_number), node('td', line.item_number));
      const product = node('td'); product.append(node('strong', line.sku || 'Unspecified'), node('span', line.description || 'No description captured', 'line-description')); row.append(product);
      [line.captured_quantity, line.captured_unit_text, line.captured_price].forEach((value) => row.append(node('td', value === null || value === '' ? 'Unknown' : value)));
      body.append(row);
    });
    table.append(body); wrap.append(table); return wrap;
  }
  function render(value) {
    const order = value.order; const root = $('order-detail'); root.replaceChildren();
    const heading = node('div', undefined, 'order-heading'); const title = node('div');
    title.append(node('p', 'ACCOUNT ' + order.account_reference, 'eyebrow'), node('h2', 'Order ' + order.order_number));
    heading.append(title, node('span', 'Source captured', 'capture-badge')); root.append(heading);
    const context = node('div', undefined, 'order-context');
    [['Source order date', order.source_order_date || 'Unknown'], ['Latest input capture', date(order.source_observed_at)], ['Oldest input age', age(order.source_age_seconds)], ['Freshness', 'Unknown · cadence pending']].forEach(([label, text]) => { const item = node('div'); item.append(node('span', label), node('strong', text)); context.append(item); }); root.append(context);
    const states = node('div', undefined, 'state-grid');
    ['Commercial', 'Fulfilment', 'Invoice', 'Payment', 'Promise'].forEach((label) => { const item = node('div'); item.append(node('span', label), node('strong', 'Unknown'), node('small', 'Evidence pending')); states.append(item); }); root.append(states);
    const selected = value.history.find((r) => r.selected);
    root.append(node('h3', 'Lines in the selected capture'));
    root.append(node('p', 'Captured numeric values are shown without rounding. Currency and unit rules are not yet accepted; no totals are calculated.', 'muted numeric-note'));
    if (selected) root.append(lineTable(selected.lines));
    root.append(node('h3', 'Retained capture history'), node('p', value.history.length + ' captures · Each entry records source evidence, with its original line identities. This is not a complete operational event history.', 'muted'));
    const timeline = node('div', undefined, 'timeline');
    value.history.forEach((revision) => {
      const detail = node('details', undefined, 'timeline-entry'); const summary = node('summary'); const label = node('div');
      label.append(node('strong', date(revision.source_observed_at)), node('span', (revision.selected ? 'Selected capture · ' : '') + revision.line_count + ' lines', 'muted'));
      const c = revision.captured_changes;
      const change = c.basis === 'FIRST_RETAINED_CAPTURE' ? 'First retained capture' : c.added + ' added · ' + c.removed + ' removed · ' + c.moved + ' moved · ' + c.values_changed + ' values changed';
      summary.append(label, node('span', change, 'change-summary')); detail.append(summary);
      detail.append(node('p', 'Input window: ' + date(revision.oldest_input_at) + ' to ' + date(revision.source_observed_at) + '. Membership changes describe captures; they do not establish cancellation or fulfilment.', 'muted'));
      detail.append(lineTable(revision.lines)); detail.append(node('p', 'Snapshot ' + revision.source_snapshot_id + ' · ' + revision.translator_version + ' · ' + revision.keyset_basis, 'provenance')); timeline.append(detail);
    }); root.append(timeline);
    root.append(node('p', 'Partial coverage · Retained captures only · ERP and current Control remain the operational authority.', 'provenance'));
  }
  async function selectOrder(id, updateLocation = true) {
    const ticket = ++sequence; $('orders-error').hidden = true;
    document.querySelectorAll('.order-choice').forEach((button) => { const selected = button.dataset.id === id; button.classList.toggle('selected', selected); button.setAttribute('aria-current', selected ? 'true' : 'false'); });
    $('order-detail').replaceChildren(node('p', 'Loading order evidence…', 'muted'));
    try {
      const value = await api('/api/orders/' + encodeURIComponent(id)); if (ticket !== sequence) return; render(value);
      if (updateLocation) history.replaceState(null, '', '/orders?order=' + encodeURIComponent(id));
    } catch (error) { if (ticket === sequence) showError(error.message); }
  }
  async function load() {
    try {
      const session = await api('/api/session'); $('account-name').textContent = session.user.display_name || 'Your workspace';
      const value = await api('/api/orders'); $('population').textContent = value.population_count + ' orders in this saved sample · Partial coverage'; $('order-count').textContent = value.population_count;
      value.orders.forEach((order) => { const button = node('button', undefined, 'order-choice'); button.type = 'button'; button.dataset.id = order.order_id; button.append(node('strong', 'Order ' + order.order_number), node('span', order.account_reference), node('small', order.line_count + ' lines · captured ' + date(order.source_observed_at))); button.addEventListener('click', () => void selectOrder(order.order_id)); $('order-list').append(button); });
      const requested = new URLSearchParams(location.search).get('order');
      if (requested && value.orders.some((order) => order.order_id === requested)) await selectOrder(requested, false);
      else if (value.orders.length) await selectOrder(value.orders[0].order_id);
    } catch (error) { showError(error.message); }
  }
  $('logout').addEventListener('click', async () => { $('logout').disabled = true; try { const response = await fetch('/auth/logout', {method: 'POST', credentials: 'same-origin', cache: 'no-store', redirect: 'error', headers: {'Content-Type': 'application/json'}, body: '{}'}); if (!response.ok) throw new Error('Sign out is temporarily unavailable.'); location.replace('/login'); } catch (error) { showError(error.message); $('logout').disabled = false; } });
  void load();
})();

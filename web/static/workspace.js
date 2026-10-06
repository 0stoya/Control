'use strict';
(() => {
  const $ = (id) => document.getElementById(id);
  async function load() {
    try {
      const response = await fetch('/api/session', {credentials: 'same-origin', cache: 'no-store', redirect: 'error'});
      if (response.status === 401) { location.replace('/login'); return; }
      if (!response.ok) throw new Error('Your workspace is temporarily unavailable. Please try again.');
      const value = await response.json();
      const name = typeof value.user.display_name === 'string' ? value.user.display_name : 'Your workspace';
      $('account-name').textContent = name;
      $('greeting').textContent = 'Welcome, ' + name;
      const profiles = {purchasing: 'Purchasing', sales: 'Sales', planning: 'Planning', operations: 'Operations'};
      $('profile').textContent = profiles[value.user.operational_profile] || 'Your operational workspace';
    } catch (error) { $('workspace-error').textContent = error.message; $('workspace-error').hidden = false; }
  }
  $('logout').addEventListener('click', async () => {
    $('logout').disabled = true;
    try {
      const response = await fetch('/auth/logout', {method: 'POST', credentials: 'same-origin', cache: 'no-store', redirect: 'error', headers: {'Content-Type': 'application/json'}, body: '{}'});
      if (!response.ok) throw new Error('Sign out is temporarily unavailable. Please try again.');
      location.replace('/login');
    } catch (error) { $('workspace-error').textContent = error.message; $('workspace-error').hidden = false; $('logout').disabled = false; }
  });
  void load();
})();

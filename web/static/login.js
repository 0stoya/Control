'use strict';
(() => {
  const $ = (id) => document.getElementById(id);
  let stage = 'LOGIN';
  let busy = false;
  const message = (text = '') => { $('error').textContent = text; $('error').hidden = !text; };
  async function call(path, data) {
    const response = await fetch('/auth/' + path, {
      method: data === undefined ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store',
      headers: data === undefined ? {} : {'Content-Type': 'application/json'},
      body: data === undefined ? undefined : JSON.stringify(data), redirect: 'error'
    });
    const value = await response.json();
    if (!response.ok) throw new Error(typeof value.detail === 'string' ? value.detail : 'Sign-in could not be completed. Please try again.');
    return value;
  }
  function show(next) {
    stage = next;
    $('login-form').hidden = next !== 'LOGIN';
    $('password-form').hidden = next !== 'PASSWORD_CHANGE';
    $('enrol-panel').hidden = next !== 'TOTP_ENROLL';
    $('code-form').hidden = !['TOTP_ENROLL', 'TOTP_VERIFY'].includes(next);
    $('recovery-panel').hidden = next !== 'RECOVERY';
    $('restart').hidden = next === 'LOGIN' || next === 'RECOVERY';
    const copy = {
      LOGIN: ['Welcome to Control', 'Sign in with your existing Control account.'],
      PASSWORD_CHANGE: ['Choose your password', 'Your account requires a new password before continuing.'],
      TOTP_ENROLL: ['Set up your authenticator', 'Add this account to your authenticator, then enter its code.'],
      TOTP_VERIFY: ['Verify your sign-in', 'Enter your authenticator code or an unused recovery code.'],
      RECOVERY: ['Save your recovery codes', 'Keep these somewhere secure. Each code works once.']
    }[next];
    if (!copy) throw new Error('The sign-in stage was not recognised.');
    $('heading').textContent = copy[0]; $('intro').textContent = copy[1];
    if (next === 'TOTP_VERIFY') $('code').focus();
  }
  function next(value) {
    if (value.state === 'AUTHENTICATED') { location.replace('/'); return; }
    if (value.state !== 'PREAUTH' || !['PASSWORD_CHANGE', 'TOTP_ENROLL', 'TOTP_VERIFY'].includes(value.stage)) throw new Error('The sign-in response was not recognised.');
    show(value.stage);
  }
  async function run(action) {
    if (busy) return;
    busy = true; message();
    document.querySelectorAll('button').forEach((button) => { button.disabled = true; });
    try { await action(); } catch (error) { message(error instanceof Error ? error.message : 'Sign-in is temporarily unavailable.'); }
    finally {
      busy = false;
      document.querySelectorAll('button').forEach((button) => { button.disabled = false; });
      $('finish-enrol').disabled = !$('saved-codes').checked;
    }
  }
  $('login-form').addEventListener('submit', (event) => {
    event.preventDefault(); const username = $('username').value.trim(); const password = $('password').value;
    $('password').value = ''; void run(async () => next(await call('login', {username, password})));
  });
  $('password-form').addEventListener('submit', (event) => {
    event.preventDefault(); const password = $('new-password').value;
    if (password !== $('confirm-password').value) { message('The passwords do not match.'); return; }
    $('new-password').value = ''; $('confirm-password').value = '';
    void run(async () => next(await call('password/change', {password})));
  });
  $('prepare-enrol').addEventListener('click', () => void run(async () => {
    const value = await call('totp/setup', {});
    if (typeof value.secret !== 'string' || !value.secret) throw new Error('Authenticator setup is unavailable.');
    $('setup-key').textContent = value.secret; $('qr').src = '/auth/totp/qr'; $('enrol-details').hidden = false;
  }));
  $('code-form').addEventListener('submit', (event) => {
    event.preventDefault(); const code = $('code').value.trim(); $('code').value = '';
    void run(async () => {
      const value = await call(stage === 'TOTP_ENROLL' ? 'totp/confirm' : 'totp/verify', {code});
      if (stage !== 'TOTP_ENROLL') { next(value); return; }
      if (value.state !== 'AUTHENTICATED' || !Array.isArray(value.recovery_codes) || !value.recovery_codes.length) throw new Error('Recovery codes were not returned.');
      $('setup-key').textContent = ''; $('qr').removeAttribute('src');
      $('recovery-codes').replaceChildren(...value.recovery_codes.map((text) => { const element = document.createElement('code'); element.textContent = text; return element; }));
      show('RECOVERY');
    });
  });
  $('saved-codes').addEventListener('change', () => { $('finish-enrol').disabled = !$('saved-codes').checked; });
  $('finish-enrol').addEventListener('click', () => { if ($('saved-codes').checked) location.replace('/'); });
  $('restart').addEventListener('click', () => void run(async () => { await call('logout', {}); location.replace('/login'); }));
  void run(async () => {
    try { next(await call('challenge')); }
    catch (error) { if (error.message === 'Authentication required') show('LOGIN'); else throw error; }
  });
})();

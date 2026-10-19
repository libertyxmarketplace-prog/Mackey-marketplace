// Asset detail pages and creator-supplied livery codes.
function parseLiveryCodes(value) {
  return value.split(/\r?\n/).map(line => line.trim()).filter(Boolean).map(line => {
    const separator = line.indexOf(':');
    if (separator < 1) throw new Error('Enter codes as Label: Asset ID');
    return { label: line.slice(0, separator).trim(), code: line.slice(separator + 1).trim() };
  }).filter(item => item.label && item.code).slice(0, 20);
}
function renderCodeRows(asset) {
  const codes = Array.isArray(asset.codes) ? asset.codes : [];
  if (!codes.length) return '<div class="lx-no-codes">No livery codes have been provided for this listing.</div>';
  return `<div class="lx-code-list">${codes.map(({label, code}) => `<div class="lx-code-row"><span>${esc(label)}</span><code>${esc(code)}</code><button type="button" class="lx-copy" data-copy-code="${esc(code)}" aria-label="Copy ${esc(label)} code">Copy ↗</button></div>`).join('')}</div>`;
}
function detailPage(asset) {
  const kind = asset.kind || 'police';
  const price = Number(asset.price) === 0 ? 'Free' : '$' + Number(asset.price).toFixed(2);
  const claimText = asset.serverId ? (Number(asset.price)===0 ? 'Claim free asset' : 'Checkout unavailable') : 'Showcase listing';
  return `<div class="lx-detail-header"><button class="lx-back" data-detail-back>← Back to marketplace</button><span>ASSET DETAILS / ${esc(asset.department)}</span></div>
    <div class="lx-detail-layout"><div class="lx-detail-main"><div class="lx-detail-hero ${esc(kind)}">${asset.preview ? `<img class="lx-detail-image" src="${asset.preview}" alt="${esc(asset.title)} preview">` : ""}<span>${esc(asset.department)}</span><div class="lx-hero-caption">${esc(asset.title)}</div></div>
    <h1>${esc(asset.title)}</h1><p class="lx-muted">Created by ${esc(asset.creator)} · ${esc(asset.department)}</p>
    <section class="lx-detail-box"><h3>Description</h3><p>${esc(asset.desc || 'No description provided.')}</p></section>
    <section class="lx-detail-box"><h3>⌘ &nbsp; CODES</h3><p class="lx-muted">Creator-provided Roblox asset IDs. Use the copy button for each entry.</p>${renderCodeRows(asset)}</section></div>
    <aside class="lx-detail-side"><section class="lx-detail-box"><span class="lx-muted">Price</span><h2>${price}</h2><button class="btn primary lx-wide" ${!asset.serverId || Number(asset.price)!==0?'disabled':''} data-get="${asset.id}">${claimText}</button><button class="btn secondary lx-wide" data-save="${asset.id}">♡ Save listing</button><small>${asset.serverId ? 'Uploaded by a community creator.' : 'Example listing. No downloadable file attached.'}</small></section>
    <section class="lx-detail-box"><span class="lx-muted">CREATED BY</span><h3>${esc(asset.creator)}</h3><hr><p>Department: ${esc(asset.department)}</p><p>Type: Digital asset</p></section></aside></div>`;
}
(function () {
  const page = document.createElement('section');
  page.className = 'page inner-page lx-detail-page';
  page.id = 'page-listing';
  page.innerHTML = '<div id="lxDetailContent"></div>';
  document.querySelector('main').append(page);
  let lastAsset = null;
  const originalView = window.viewAsset;
  window.viewAsset = function (id) {
    const asset = allAssets().find(item => String(item.id) === String(id));
    if (!asset) return originalView(id);
    lastAsset = asset;
    document.getElementById('lxDetailContent').innerHTML = detailPage(asset);
    go('listing');
    history.replaceState(null, '', '#listing-' + encodeURIComponent(id));
  };
  document.addEventListener('click', async event => {
    const back = event.target.closest('[data-detail-back]');
    if (back) { go('marketplace'); history.replaceState(null, '', '#marketplace'); return; }
    const copy = event.target.closest('[data-copy-code]');
    if (!copy) return;
    const value = copy.dataset.copyCode;
    try {
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(value);
      else {
        const input = document.createElement('textarea'); input.value = value;
        input.style.position = 'fixed'; input.style.opacity = '0'; document.body.append(input);
        input.select();
        if (!document.execCommand('copy')) throw Error('Clipboard unavailable');
        input.remove();
      }
      copy.textContent = 'Copied ✓'; setTimeout(() => copy.textContent = 'Copy ↗', 1600);
    } catch { showToast('Copy unavailable; select the code manually.'); }
  });
  // The existing filter handler uses the exact Fire & Rescue label.
  // Normalize alternate spellings to prevent empty department results.
  document.querySelectorAll('[data-department]').forEach(button => {
    if (/fire/i.test(button.dataset.department)) button.dataset.department = 'Fire & Rescue';
  });
  document.getElementById('uploadForm').addEventListener('submit', event => {
    try { parseLiveryCodes(document.getElementById('uploadCodes').value); }
    catch (error) { event.preventDefault(); event.stopImmediatePropagation(); showToast(error.message); }
  }, true);
})();

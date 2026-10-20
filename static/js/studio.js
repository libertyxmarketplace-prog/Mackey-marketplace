// Creator Studio tools. These use the same account session as the marketplace.
(() => {
  const list = document.getElementById('dashboardListings');
  const count = document.getElementById('realListings');
  const api = async (path, body) => {
    const response = await fetch('/api/' + path, {
      credentials: 'same-origin',
      method: body ? 'POST' : 'GET',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Something went wrong');
    return result;
  };
  const escapeText = value => String(value).replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
  async function updateStudio() {
    try {
      const [profile, result] = await Promise.all([api('me'), api('listings')]);
      if (!profile.user) return;
      const mine = result.listings.filter(item => item.owner === profile.user.id);
      count.textContent = mine.length;
      list.innerHTML = mine.length ? mine.map(item => `
        <div class="studio-row">
          <div><strong>${escapeText(item.title)}</strong><small>${escapeText(item.department)} · ${item.price ? '$' + Number(item.price).toFixed(2) : 'Free'}</small></div>
          <button class="studio-delete" data-delete-listing="${item.id}" type="button">Remove</button>
        </div>`).join('') : '<div class="studio-empty">You have not published any assets yet. Create your first listing to get started.</div>';
    } catch (error) { list.textContent = 'Unable to load listings: ' + error.message; }
  }
  document.addEventListener('click', async event => {
    const deleteButton = event.target.closest('[data-delete-listing]');
    if (deleteButton) {
      if (!confirm('Remove this listing? This cannot be undone.')) return;
      deleteButton.disabled = true;
      try { await api('delete-listing', { id: Number(deleteButton.dataset.deleteListing) }); await updateStudio(); location.reload(); }
      catch (error) { alert(error.message); deleteButton.disabled = false; }
    }
    if (event.target.closest('[data-page="dashboard"]')) setTimeout(updateStudio, 200);
  });
  document.addEventListener('submit', event => {
    if (event.target.id === 'uploadForm') setTimeout(updateStudio, 1200);
  });
  setTimeout(updateStudio, 700);
})();

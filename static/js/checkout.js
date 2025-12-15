(() => {
  const provinceSelect = document.getElementById('province-select');
  const citySelect = document.getElementById('city-select');
  const summaryEl = document.getElementById('checkout-summary');

  const shippingFeeEl = document.getElementById('shipping-fee');
  const shippingFeeOriginalEl = document.getElementById('shipping-fee-original');
  const shippingFreeBadgeEl = document.getElementById('shipping-free-badge');
  const shippingHintEl = document.getElementById('shipping-hint');
  const finalTotalEl = document.getElementById('final-total');

  const modal = document.getElementById('phone-verify-modal');

  const formatNumber = (value) => {
    const numberValue = Number(value);
    if (!Number.isFinite(numberValue)) return String(value ?? '');
    try {
      return numberValue.toLocaleString('fa-IR');
    } catch {
      return String(numberValue);
    }
  };

  const parseNumber = (value) => {
    const numberValue = Number(String(value ?? '').replace(/,/g, ''));
    return Number.isFinite(numberValue) ? numberValue : 0;
  };

  const setModalOpen = (open) => {
    if (!modal) return;
    modal.classList.toggle('open', Boolean(open));
    modal.setAttribute('aria-hidden', open ? 'false' : 'true');
    document.body.classList.toggle('modal-open', Boolean(open));
  };

  const closeModal = () => setModalOpen(false);

  if (modal) {
    const closeButtons = modal.querySelectorAll('[data-modal-close]');
    closeButtons.forEach((btn) => btn.addEventListener('click', closeModal));
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeModal();
    });
    if (modal.dataset.open === '1') setModalOpen(true);
  }

  const populateProvinces = () => {
    const locations = window.IRAN_LOCATIONS;
    if (!provinceSelect || !locations || !Array.isArray(locations.provinces)) return;
    const selected = provinceSelect.dataset.selected || '';

    for (const province of locations.provinces) {
      const option = document.createElement('option');
      option.value = province;
      option.textContent = province;
      if (province === selected) option.selected = true;
      provinceSelect.appendChild(option);
    }
  };

  const populateCounties = () => {
    const locations = window.IRAN_LOCATIONS;
    if (!provinceSelect || !citySelect || !locations || !locations.countiesByProvince) return;

    const province = provinceSelect.value || '';
    const selectedCity = citySelect.dataset.selected || '';

    citySelect.innerHTML = '';

    if (!province) {
      const placeholder = document.createElement('option');
      placeholder.value = '';
      placeholder.textContent = 'ابتدا استان را انتخاب کنید';
      citySelect.appendChild(placeholder);
      citySelect.disabled = true;
      return;
    }

    const counties = locations.countiesByProvince[province] || [];

    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = 'انتخاب کنید';
    citySelect.appendChild(placeholder);

    for (const county of counties) {
      const option = document.createElement('option');
      option.value = county;
      option.textContent = county;
      if (county === selectedCity) option.selected = true;
      citySelect.appendChild(option);
    }

    citySelect.disabled = false;
  };

  const updateTotals = () => {
    if (!summaryEl || !shippingFeeEl || !finalTotalEl) return;

    const provinceSelected = Boolean(provinceSelect && provinceSelect.value);

    const subtotal = parseNumber(summaryEl.dataset.subtotal);
    const shippingFeePerItem = parseNumber(summaryEl.dataset.shippingFeePerItem);
    const itemCount = parseNumber(summaryEl.dataset.itemCount);
    const freeThreshold = parseNumber(summaryEl.dataset.freeThreshold);

    let shippingApplied = 0;
    let shippingTotalFull = 0;
    let isFree = false;

    if (provinceSelected) {
      isFree = freeThreshold > 0 && subtotal >= freeThreshold;
      shippingTotalFull = shippingFeePerItem * itemCount;
      shippingApplied = isFree ? 0 : shippingTotalFull;
    }

    const finalTotal = subtotal + shippingApplied;

    shippingFeeEl.textContent = formatNumber(shippingApplied);
    finalTotalEl.textContent = formatNumber(finalTotal);

    if (shippingHintEl) shippingHintEl.classList.toggle('hidden', provinceSelected);

    if (shippingFeeOriginalEl) {
      shippingFeeOriginalEl.textContent = formatNumber(shippingTotalFull);
      shippingFeeOriginalEl.classList.toggle('hidden', !isFree);
    }
    if (shippingFreeBadgeEl) {
      shippingFreeBadgeEl.classList.toggle('hidden', !isFree);
    }
  };

  populateProvinces();
  populateCounties();
  updateTotals();

  if (provinceSelect) {
    provinceSelect.addEventListener('change', () => {
      citySelect && (citySelect.dataset.selected = '');
      populateCounties();
      updateTotals();
    });
  }
})();

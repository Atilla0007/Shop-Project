(() => {
  const provinceSelect = document.getElementById('province-select');
  const citySelect = document.getElementById('city-select');
  const summaryEl = document.getElementById('checkout-summary');

  const shippingFeeEl = document.getElementById('shipping-fee');
  const shippingFeeOriginalEl = document.getElementById('shipping-fee-original');
  const shippingFreeBadgeEl = document.getElementById('shipping-free-badge');
  const shippingHintEl = document.getElementById('shipping-hint');
  const finalTotalEl = document.getElementById('final-total');
  const subtotalEl = document.getElementById('checkout-subtotal');

  const discountInput = document.getElementById('discount_code');
  const discountApplyBtn = document.getElementById('discount-apply-btn');
  const discountAppliedInput = document.getElementById('discount_code_applied');
  const discountFeedbackEl = document.getElementById('discount-feedback');
  const discountRowEl = document.getElementById('discount-row');
  const discountAmountEl = document.getElementById('discount-amount');
  const discountPercentEl = document.getElementById('discount-percent');
  const subtotalLabelEl = document.getElementById('subtotal-label');

  const modal = document.getElementById('phone-verify-modal');

  const getCookie = (name) => {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === name + '=') {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  };

  const formatNumber = (value) => {
    const numberValue = Number(value);
    if (!Number.isFinite(numberValue)) return String(value ?? '');
    try {
      return numberValue.toLocaleString('fa-IR').replaceAll('٬', '،').replaceAll(',', '،');
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

    if (subtotalEl) subtotalEl.textContent = formatNumber(subtotal);
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

  const setDiscountFeedback = (message, type) => {
    if (!discountFeedbackEl) return;
    if (!message) {
      discountFeedbackEl.textContent = '';
      discountFeedbackEl.classList.add('hidden');
      discountFeedbackEl.classList.remove('ok', 'error');
      return;
    }
    discountFeedbackEl.textContent = message;
    discountFeedbackEl.classList.remove('hidden');
    discountFeedbackEl.classList.toggle('ok', type === 'ok');
    discountFeedbackEl.classList.toggle('error', type === 'error');
  };

  const updateDiscountUI = ({ percent, amount }) => {
    const p = Number(percent || 0);
    const a = Number(amount || 0);

    if (discountRowEl) discountRowEl.classList.toggle('hidden', !(a > 0 && p > 0));
    if (discountPercentEl) discountPercentEl.textContent = String(p || 0);
    if (discountAmountEl) discountAmountEl.textContent = `-${formatNumber(a)}`;
    if (subtotalLabelEl) subtotalLabelEl.textContent = a > 0 ? 'جمع بعد از تخفیف' : 'جمع قابل پرداخت کالاها';
  };

  const normalizeCode = (raw) => String(raw || '').trim().toUpperCase().replace(/\s+/g, '');

  const applyDiscount = async () => {
    if (!summaryEl || !discountInput || !discountApplyBtn || !discountAppliedInput) return;
    const previewUrl = summaryEl.dataset.discountPreviewUrl;
    if (!previewUrl) return;

    const code = normalizeCode(discountInput.value);
    const csrftoken = getCookie('csrftoken');

    const originalText = discountApplyBtn.textContent;
    discountApplyBtn.disabled = true;
    discountApplyBtn.textContent = '...';

    try {
      const body = new URLSearchParams();
      body.set('code', code);

      const response = await fetch(previewUrl, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrftoken || '',
          'X-Requested-With': 'XMLHttpRequest',
          'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        },
        credentials: 'same-origin',
        body: body.toString(),
      });

      const data = await response.json().catch(() => null);
      if (!data || data.ok !== true) {
        const msg = (data && data.message) || 'کد تخفیف نامعتبر است.';
        setDiscountFeedback(msg, 'error');
        return;
      }

      const itemsSubtotal = parseNumber(data.items_subtotal ?? summaryEl.dataset.itemsSubtotal);
      const discountPercent = parseNumber(data.percent || 0);
      const discountAmount = parseNumber(data.amount || 0);
      const subtotal = parseNumber(data.subtotal ?? itemsSubtotal);
      const appliedCode = String(data.code || '');

      summaryEl.dataset.itemsSubtotal = String(itemsSubtotal);
      summaryEl.dataset.subtotal = String(subtotal);
      discountAppliedInput.value = appliedCode;
      discountInput.value = appliedCode;

      updateDiscountUI({ percent: discountPercent, amount: discountAmount });
      updateTotals();
      setDiscountFeedback(String(data.message || 'کد تخفیف اعمال شد.'), 'ok');
    } catch {
      setDiscountFeedback('خطا در بررسی کد تخفیف. لطفاً دوباره تلاش کنید.', 'error');
    } finally {
      discountApplyBtn.disabled = false;
      discountApplyBtn.textContent = originalText;
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

  if (discountApplyBtn) {
    discountApplyBtn.addEventListener('click', applyDiscount);
  }
  if (discountInput) {
    discountInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        applyDiscount();
      }
    });
  }
})();

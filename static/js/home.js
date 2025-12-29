(() => {
  const initToggle = (toggle, target, openText, closeText, onUpdate) => {
    if (!toggle || !target) {
      return;
    }

    const updateText = () => {
      const isOpen = target.classList.contains('is-open');
      toggle.textContent = isOpen ? closeText : openText;
      toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      if (typeof onUpdate === 'function') {
        onUpdate(isOpen);
      }
    };

    toggle.addEventListener('click', () => {
      target.classList.toggle('is-open');
      updateText();
      if (target.classList.contains('is-open')) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });

    updateText();
  };

  initToggle(
    document.querySelector('[data-home-more-toggle]'),
    document.querySelector('[data-home-more]'),
    'مشاهده ادامه محتوا',
    'بستن ادامه محتوا'
  );

  const productsToggle = document.querySelector('[data-home-products-toggle]');
  const productsExtra = document.querySelector('[data-home-products-extra]');
  const productsTopAnchor = document.querySelector('[data-home-products-toggle-anchor="top"]');
  const productsBottomAnchor = document.querySelector('[data-home-products-toggle-anchor="bottom"]');

  initToggle(
    productsToggle,
    productsExtra,
    'نمایش محصولات بیشتر',
    'بستن محصولات بیشتر',
    (isOpen) => {
      if (!productsToggle || !productsTopAnchor || !productsBottomAnchor) {
        return;
      }
      const targetAnchor = isOpen ? productsBottomAnchor : productsTopAnchor;
      if (productsToggle.parentElement !== targetAnchor) {
        targetAnchor.appendChild(productsToggle);
      }
    }
  );
})();

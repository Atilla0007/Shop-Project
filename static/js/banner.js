(() => {
  const banner = document.querySelector('.top-banner');
  if (!banner) return;

  const code = banner.dataset.bannerCode || '';
  const copyBtn = banner.querySelector('[data-banner-copy]');
  if (!copyBtn || !code) return;

  const originalText = copyBtn.textContent;

  const setTempText = (text) => {
    copyBtn.textContent = text;
    window.clearTimeout(copyBtn._t);
    copyBtn._t = window.setTimeout(() => {
      copyBtn.textContent = originalText;
    }, 1400);
  };

  copyBtn.addEventListener('click', async () => {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(code);
      } else {
        const input = document.createElement('input');
        input.value = code;
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        input.remove();
      }
      setTempText('کپی شد');
    } catch {
      setTempText('کپی نشد');
    }
  });
})();


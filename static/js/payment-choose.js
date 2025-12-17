document.addEventListener("DOMContentLoaded", () => {
  const choiceRoot = document.querySelector("[data-payment-choice]");
  const continueButton = document.querySelector("[data-payment-continue]");
  if (!choiceRoot || !continueButton) return;

  const radios = Array.from(
    choiceRoot.querySelectorAll('input[type="radio"][name="payment_method"]')
  );

  const sync = () => {
    const selected = radios.find((r) => r.checked && !r.disabled);
    const url = selected?.dataset?.url || "";
    continueButton.disabled = !url;
    continueButton.dataset.url = url;
  };

  for (const radio of radios) {
    radio.addEventListener("change", sync);
  }

  continueButton.addEventListener("click", () => {
    const url = continueButton.dataset.url;
    if (!url) return;
    window.location.assign(url);
  });

  sync();
});


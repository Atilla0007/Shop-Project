document.addEventListener("DOMContentLoaded", () => {
  const choiceRoot = document.querySelector("[data-payment-choice]");
  const continueButton = document.querySelector("[data-payment-continue]");
  if (!choiceRoot || !continueButton) return;

  const inputs = Array.from(choiceRoot.querySelectorAll('input[name="payment_method"]'));

  const sync = () => {
    const selected = inputs.find((r) => r.checked && !r.disabled);
    const url = selected?.dataset?.url || "";
    continueButton.disabled = !url;
    continueButton.dataset.url = url;
  };

  for (const input of inputs) {
    input.addEventListener("change", () => {
      if (input.checked) {
        for (const other of inputs) {
          if (other !== input) other.checked = false;
        }
      }
      sync();
    });
  }

  continueButton.addEventListener("click", () => {
    const url = continueButton.dataset.url;
    if (!url) return;
    window.location.assign(url);
  });

  sync();
});

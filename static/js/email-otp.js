(() => {
  const root = document.querySelector("[data-otp-inputs]");
  if (!root) return;

  const inputs = Array.from(root.querySelectorAll("input"));
  if (!inputs.length) return;

  const focusIndex = (idx) => {
    const el = inputs[idx];
    if (el) el.focus();
  };

  const sanitize = (value) => (value || "").replace(/\D/g, "");

  inputs.forEach((input, idx) => {
    input.addEventListener("input", (e) => {
      const digits = sanitize(e.target.value);

      if (digits.length <= 1) {
        e.target.value = digits;
        if (digits && idx < inputs.length - 1) focusIndex(idx + 1);
        return;
      }

      // Paste / multi-digit input: spread across inputs.
      const all = digits.split("");
      for (let i = 0; i < inputs.length; i++) {
        inputs[i].value = all[i] || "";
      }
      const nextEmpty = inputs.findIndex((el) => !el.value);
      focusIndex(nextEmpty === -1 ? inputs.length - 1 : nextEmpty);
    });

    input.addEventListener("keydown", (e) => {
      if (e.key === "Backspace" && !input.value && idx > 0) {
        inputs[idx - 1].value = "";
        focusIndex(idx - 1);
      }
      if (e.key === "ArrowLeft" && idx > 0) focusIndex(idx - 1);
      if (e.key === "ArrowRight" && idx < inputs.length - 1) focusIndex(idx + 1);
    });
  });

  focusIndex(0);
})();


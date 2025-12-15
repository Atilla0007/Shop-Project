(() => {
  const root = document.querySelector("[data-otp-inputs]");
  if (!root) return;

  const inputs = Array.from(root.querySelectorAll("input"));
  if (!inputs.length) return;

  const form = root.closest("form");
  let isSubmitting = false;

  const focusIndex = (idx) => {
    const el = inputs[idx];
    if (el) el.focus();
  };

  const sanitize = (value) => (value || "").replace(/\D/g, "");

  const firstEmptyIndex = () => inputs.findIndex((el) => !el.value);

  const allFilled = () => inputs.every((el) => (el.value || "").length === 1);

  const ensureInlineErrorBox = () => {
    if (!form) return null;
    let box = form.querySelector("[data-inline-otp-error]");
    if (box) return box;
    box = document.createElement("div");
    box.className = "otp-error";
    box.setAttribute("data-inline-otp-error", "1");
    const info = form.querySelector(".info");
    if (info && info.parentNode) {
      info.parentNode.insertBefore(box, info.nextSibling);
    } else {
      form.insertBefore(box, form.firstChild);
    }
    return box;
  };

  const showInlineError = (msg) => {
    const box = ensureInlineErrorBox();
    if (!box) return;
    box.textContent = msg;
    box.style.display = "";
  };

  const clearInlineError = () => {
    if (!form) return;
    const box = form.querySelector("[data-inline-otp-error]");
    if (box) box.remove();
  };

  const submitIfReady = () => {
    if (!form || isSubmitting) return;
    if (!allFilled()) return;
    clearInlineError();
    isSubmitting = true;
    form.submit();
  };

  inputs.forEach((input, idx) => {
    input.addEventListener("input", (e) => {
      const digits = sanitize(e.target.value);

      if (digits.length <= 1) {
        e.target.value = digits;
        if (digits && idx < inputs.length - 1) focusIndex(idx + 1);
        submitIfReady();
        return;
      }

      // Paste / multi-digit input: spread across inputs.
      const all = digits.split("");
      for (let i = 0; i < inputs.length; i++) {
        inputs[i].value = all[i] || "";
      }
      const nextEmpty = inputs.findIndex((el) => !el.value);
      focusIndex(nextEmpty === -1 ? inputs.length - 1 : nextEmpty);
      submitIfReady();
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

  if (form) {
    form.addEventListener("submit", (e) => {
      if (isSubmitting) return;
      if (allFilled()) return;
      e.preventDefault();
      showInlineError("رمز غلط است.");
      const idx = firstEmptyIndex();
      if (idx !== -1) focusIndex(idx);
    });
  }

  focusIndex(0);
})();

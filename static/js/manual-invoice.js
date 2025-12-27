(() => {
        const root = document.querySelector(".container[data-shipping-fee-per-item]");
        const itemsBody = document.getElementById("itemsBody");
        const calcTotalsBtn = document.getElementById("calcTotalsBtn");
        const productSelect = document.getElementById("productSelect");
        const addProductBtn = document.getElementById("addProductBtn");

        const pdfEndpoint = root?.dataset.pdfEndpoint || "";
        const defaultTitle = root?.dataset.invoiceTitle || "پیش‌فاکتور";
        const defaultInvoiceNumber = root?.dataset.invoiceNumber || "#000000";

        const getCookie = (name) => {
          const value = `; ${document.cookie}`;
          const parts = value.split(`; ${name}=`);
          if (parts.length === 2) return parts.pop().split(";").shift();
          return "";
        };

        const addRowBtn = document.getElementById("addRowBtn");

        const digitsMap = {
          "0": "۰",
          "1": "۱",
          "2": "۲",
          "3": "۳",
          "4": "۴",
          "5": "۵",
          "6": "۶",
          "7": "۷",
          "8": "۸",
          "9": "۹",
        };

        const toPersianDigits = (value) =>
          String(value ?? "").replace(/[0-9]/g, (d) => digitsMap[d] || d);

        const parseNumber = (raw) => {
          if (raw == null) return 0;
          let s = String(raw)
            .replaceAll("تومان", "")
            .replaceAll("٬", "")
            .replaceAll("،", "")
            .replace(/\s+/g, "")
            .trim();
          s = s
            .replace(/[۰-۹]/g, (d) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d)))
            .replace(/[٠-٩]/g, (d) => String("٠١٢٣٤٥٦٧٨٩".indexOf(d)));
          const n = Number(s);
          return Number.isFinite(n) ? n : 0;
        };

        const formatMoneyToman = (n) => {
          const num = Number(n);
          if (!Number.isFinite(num)) return "۰ تومان";
          const withCommas = Math.round(num).toLocaleString("en-US").replaceAll(",", "،");
          return `${toPersianDigits(withCommas)} تومان`;
        };

        const setCell = (id, value) => {
          const el = document.getElementById(id);
          if (!el) return;
          el.textContent = value;
        };

        const newRow = () => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td>
              <h4 contenteditable="true" data-placeholder="نام کالا"></h4>
              <p
                contenteditable="true"
                data-role="desc"
                data-hide-empty="1"
                data-placeholder="توضیح کوتاه (اختیاری)"
                style="color: var(--muted); margin-top: 4px"
              ></p>
            </td>
            <td contenteditable="true" data-role="qty">۱</td>
            <td contenteditable="true" data-role="price">۰</td>
            <td class="no-print actions-col">
              <button class="remove-row" type="button" title="حذف ردیف">×</button>
            </td>
          `;
          return tr;
        };

        if (addRowBtn && itemsBody) {
          addRowBtn.addEventListener("click", () => {
            itemsBody.appendChild(newRow());
          });
        }

        const normalizeMoneyCell = (cell) => {
          const n = parseNumber(cell.textContent);
          cell.textContent = formatMoneyToman(n);
        };

        const normalizeQtyCell = (cell) => {
          const n = Math.max(1, Math.round(parseNumber(cell.textContent)));
          cell.textContent = toPersianDigits(String(n));
        };

        const computeTotals = () => {
          if (!itemsBody) return;
          const discountEl = document.getElementById("footerDiscount");
          const shippingEl = document.getElementById("footerShipping");
          const rows = Array.from(itemsBody.querySelectorAll("tr"));
          let itemsSubtotal = 0;
          let totalQty = 0;

          for (const row of rows) {
            const qtyCell = row.querySelector('[data-role="qty"]');
            const priceCell = row.querySelector('[data-role="price"]');
            const qty = qtyCell ? Math.max(0, Math.round(parseNumber(qtyCell.textContent))) : 0;
            const price = priceCell ? Math.max(0, parseNumber(priceCell.textContent)) : 0;
            totalQty += qty;
            itemsSubtotal += qty * price;
          }

          const perItemFee = root ? parseNumber(root.dataset.shippingFeePerItem) : 0;
          const freeThreshold = root ? parseNumber(root.dataset.freeShippingMinTotal) : 0;
          const shippingFull = perItemFee * totalQty;
          const autoShipping = freeThreshold > 0 && itemsSubtotal >= freeThreshold ? 0 : shippingFull;

          const discount = parseNumber(discountEl?.textContent || 0);
          const shippingManual = shippingEl ? parseNumber(shippingEl.textContent) : 0;
          const shippingIsManual = shippingEl && (shippingEl.dataset.userEdited === "1" || shippingManual !== 0);
          const shipping = shippingIsManual ? Math.max(0, shippingManual) : autoShipping;
          const grandTotal = Math.max(0, itemsSubtotal - discount) + shipping;

          setCell("summaryItemsSubtotal", formatMoneyToman(itemsSubtotal));
          setCell("summaryGrandTotal", formatMoneyToman(grandTotal));
          setCell("footerItemsSubtotal", formatMoneyToman(itemsSubtotal));
          setCell("footerGrandTotal", formatMoneyToman(grandTotal));
          if (discountEl) discountEl.textContent = formatMoneyToman(discount);
          if (shippingEl) shippingEl.textContent = formatMoneyToman(shipping);

          // normalize numeric cells in rows
          for (const row of rows) {
            const qtyCell = row.querySelector('[data-role="qty"]');
            const priceCell = row.querySelector('[data-role="price"]');
            if (qtyCell) normalizeQtyCell(qtyCell);
            if (priceCell) normalizeMoneyCell(priceCell);
          }
        };

        if (calcTotalsBtn) {
          calcTotalsBtn.addEventListener("click", computeTotals);
        }

        const downloadPdf = async () => {
          try {
            computeTotals();

            const titleSpans = document.querySelectorAll(".inv-title h1 span[contenteditable]");
            const titleText = (titleSpans?.[0]?.textContent || "").trim() || defaultTitle;
            const invoiceNumber = (titleSpans?.[1]?.textContent || "").trim() || defaultInvoiceNumber;

            const issueDate = (document.querySelector(".inv-header table tr:nth-child(1) td")?.textContent || "").trim();
            const dueDate = (document.querySelector(".inv-header table tr:nth-child(2) td")?.textContent || "").trim();

            const buyerLines = Array.from(document.querySelectorAll(".inv-header ul li[contenteditable]"))
              .map((li) => (li.textContent || "").trim())
              .filter(Boolean);

            const rows = Array.from(itemsBody ? itemsBody.querySelectorAll("tr") : []);
            const items = rows
              .map((row) => {
                const name = (row.querySelector("h4[contenteditable]")?.textContent || "").trim();
                const desc = (row.querySelector('[data-role="desc"]')?.textContent || "").trim();
                const qty = Math.max(0, Math.round(parseNumber(row.querySelector('[data-role="qty"]')?.textContent || "")));
                const price = Math.max(0, parseNumber(row.querySelector('[data-role="price"]')?.textContent || ""));
                return { name, desc, qty, price };
              })
              .filter((it) => it.name || it.desc || it.qty > 0 || it.price > 0);

            const titleCompact = titleText.replace(/\s+/g, "");
            const includeSignatures =
              root?.dataset.includeSignatures === "1" ||
              (titleCompact.includes("فاکتور") && !titleCompact.includes("پیش"));
            const buyerSignature = (document.querySelector('[data-role="buyer-signature"]')?.textContent || "").trim();
            const sellerSignature = (document.querySelector('[data-role="seller-signature"]')?.textContent || "").trim();
            const notes = (document.querySelector('[data-role="invoice-notes"]')?.textContent || "").trim();

            const payload = {
              title: titleText,
              invoice_number: invoiceNumber,
              issue_date: issueDate,
              due_date: dueDate,
              buyer_lines: buyerLines,
              items,
              items_subtotal: parseNumber(document.getElementById("footerItemsSubtotal")?.textContent || 0),
              discount: parseNumber(document.getElementById("footerDiscount")?.textContent || 0),
              shipping: parseNumber(document.getElementById("footerShipping")?.textContent || 0),
              grand_total: parseNumber(document.getElementById("footerGrandTotal")?.textContent || 0),
              include_signatures: includeSignatures,
              buyer_signature: buyerSignature,
              seller_signature: sellerSignature,
              notes,
            };

            const btn = document.getElementById("printBtn");
            if (btn) btn.setAttribute("disabled", "disabled");

            const resp = await fetch(pdfEndpoint, {
              method: "POST",
              credentials: "same-origin",
              headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
              },
              body: JSON.stringify(payload),
            });

            if (!resp.ok) {
              alert("خطا در تولید PDF.");
              return;
            }

            const blob = await resp.blob();
            const digits = String(invoiceNumber || "").replace(/\D/g, "");
            const filename = digits ? digits.padStart(6, "0") : "manual-invoice";

            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `${filename}.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
          } catch (e) {
            alert("خطا در تولید PDF.");
          } finally {
            const btn = document.getElementById("printBtn");
            if (btn) btn.removeAttribute("disabled");
          }
        };

        const printBtn = document.getElementById("printBtn");
        if (printBtn) printBtn.addEventListener("click", downloadPdf);

        const addProductFromSelection = () => {
          if (!itemsBody || !productSelect) return;
          const opt = productSelect.options[productSelect.selectedIndex];
          if (!opt || !opt.value) return;
          const name = opt.dataset.name || opt.textContent || "";
          const price = opt.dataset.price || "0";

          const tr = newRow();
          const nameEl = tr.querySelector("h4[contenteditable]");
          const priceEl = tr.querySelector('[data-role="price"]');
          const qtyEl = tr.querySelector('[data-role="qty"]');
          if (nameEl) nameEl.textContent = String(name).trim();
          if (qtyEl) qtyEl.textContent = "۱";
          if (priceEl) priceEl.textContent = String(price);
          itemsBody.appendChild(tr);

          // Normalize and recompute totals
          if (priceEl) normalizeMoneyCell(priceEl);
          if (qtyEl) normalizeQtyCell(qtyEl);
          computeTotals();

          productSelect.value = "";
        };

        if (addProductBtn) addProductBtn.addEventListener("click", addProductFromSelection);
        if (productSelect) {
          productSelect.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addProductFromSelection();
            }
          });
        }

        const footerDiscountEl = document.getElementById("footerDiscount");
        if (footerDiscountEl) footerDiscountEl.addEventListener("input", () => (footerDiscountEl.dataset.userEdited = "1"));

        const footerShippingEl = document.getElementById("footerShipping");
        if (footerShippingEl) footerShippingEl.addEventListener("input", () => (footerShippingEl.dataset.userEdited = "1"));

        const hideEmptyInPrint = () => {
          document.querySelectorAll("[data-hide-empty]").forEach((el) => {
            const text = (el.textContent || "").trim();
            const empty = text.length === 0;
            el.classList.toggle("hide-in-print", empty);
          });

          document.querySelectorAll("#itemsBody tr").forEach((row) => {
            const name = (row.querySelector("h4[contenteditable]")?.textContent || "").trim();
            const qtyText = (row.querySelector('[data-role=\"qty\"]')?.textContent || "").trim();
            const priceText = (row.querySelector('[data-role=\"price\"]')?.textContent || "").trim();
            const desc = (row.querySelector('[data-role=\"desc\"]')?.textContent || "").trim();

            const qtyNum = parseNumber(qtyText);
            const priceNum = parseNumber(priceText);

            // Consider "empty row" as: no name/desc + default/zero numbers.
            const empty = !name && !desc && priceNum === 0 && (qtyNum === 0 || qtyNum === 1);
            row.classList.toggle("hide-in-print", empty);
          });
        };

        window.addEventListener("beforeprint", hideEmptyInPrint);

        document.addEventListener("click", (e) => {
          const btn = e.target.closest && e.target.closest(".remove-row");
          if (!btn) return;
          const row = btn.closest("tr");
          if (row && itemsBody && itemsBody.children.length > 1) row.remove();
        });

        document.addEventListener(
          "blur",
          (e) => {
            const el = e.target;
            if (!el || !(el instanceof HTMLElement)) return;
            if (el.matches && el.matches('[data-role="price"]')) normalizeMoneyCell(el);
            if (el.matches && el.matches('[data-role="qty"]')) normalizeQtyCell(el);
            if (el.id === "footerDiscount") normalizeMoneyCell(el);
            if (el.id === "footerShipping") normalizeMoneyCell(el);
          },
          true,
        );
      })();

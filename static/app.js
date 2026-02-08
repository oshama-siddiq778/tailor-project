const tabButtons = document.querySelectorAll(".tab-btn");
const tabPanels = document.querySelectorAll(".tab-panel");

tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    tabButtons.forEach((b) => b.classList.remove("active"));
    tabPanels.forEach((panel) => panel.classList.remove("active"));
    btn.classList.add("active");
    const target = btn.getAttribute("data-tab");
    document
      .querySelector(`.tab-panel[data-panel="${target}"]`)
      .classList.add("active");
  });
});

const addItemBtn = document.getElementById("add-item");
if (addItemBtn) {
  addItemBtn.addEventListener("click", () => {
    const wrapper = document.getElementById("items");
    if (!wrapper) {
      return;
    }
    const rawOptions = wrapper.getAttribute("data-item-options") || "";
    const options = rawOptions.split("|").filter(Boolean);
    const optionHtml = options.length
      ? options.map((opt) => `<option value="${opt}">${opt}</option>`).join("")
      : "<option value=\"\">Select</option>";
    const row = document.createElement("div");
    row.className = "table-row";
    row.innerHTML = `
      <div>
        <select name="item_type">
          ${optionHtml}
        </select>
      </div>
      <div><input type="number" name="item_qty" value="1" min="1" /></div>
      <div><input type="text" name="item_notes" placeholder="Style, fabric, etc." /></div>
      <div><button type="button" class="btn ghost item-delete" aria-label="Remove item">×</button></div>
    `;
    wrapper.appendChild(row);
  });
}

let activeMeasureInput = null;

function wireMeasureInputs(container) {
  container.querySelectorAll(".measure-input").forEach((input) => {
    input.addEventListener("focus", () => {
      activeMeasureInput = input;
    });
  });

  container.querySelectorAll(".fraction-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      if (!activeMeasureInput) {
        return;
      }
      const fraction = chip.getAttribute("data-value");
      const current = activeMeasureInput.value.trim();
      if (!current) {
        activeMeasureInput.value = fraction;
        activeMeasureInput.focus();
        return;
      }
      if (current.includes(fraction)) {
        activeMeasureInput.focus();
        return;
      }
      activeMeasureInput.value = `${current} ${fraction}`.trim();
      activeMeasureInput.focus();
    });
  });

  container.querySelectorAll(".subcategory-select").forEach((select) => {
    const block = select.closest(".measurement-block");
    const fieldsWrap = block ? block.querySelector(".measurement-fields") : null;
    const emptyNote = block ? block.querySelector(".measurement-empty") : null;
    const renderFields = () => {
      if (!fieldsWrap) {
        return;
      }
      const map = window.measurementFieldMap || {};
      const subId = select.value || "";
      const fields = subId && map[subId] ? map[subId] : [];
      fieldsWrap.innerHTML = "";
      fieldsWrap.classList.remove("grid", "four");
      if (!fields.length) {
        if (emptyNote) {
          emptyNote.style.display = "";
        }
        return;
      }
      if (emptyNote) {
        emptyNote.style.display = "none";
      }
      fieldsWrap.classList.add("grid", "four");
      fields.forEach((field) => {
        const label = document.createElement("label");
        label.innerHTML = `
          <span class="field-label" data-field-key="${field.key}">${field.label}</span>
          <input class="measure-input" type="text" name="measure_${field.key}" />
        `;
        fieldsWrap.appendChild(label);
      });
    };
    select.addEventListener("change", renderFields);
    renderFields();
  });
}

document.querySelectorAll(".tab-panel").forEach((panel) => {
  wireMeasureInputs(panel);
});

document.querySelectorAll(".add-measure").forEach((button) => {
  button.addEventListener("click", () => {
    const target = button.getAttribute("data-target");
    const list = document.querySelector(`.measurement-list[data-kind="${target}"]`);
    const template = document.getElementById(`measure-template-${target}`);
    if (!list || !template) {
      return;
    }
    const clone = template.content.cloneNode(true);
    list.appendChild(clone);
    wireMeasureInputs(list);
  });
});

document.addEventListener("click", (event) => {
  const itemBtn = event.target.closest(".item-delete");
  if (itemBtn) {
    const row = itemBtn.closest(".table-row");
    if (row) {
      row.remove();
    }
  }
  const measureBtn = event.target.closest(".measure-delete");
  if (measureBtn) {
    const block = measureBtn.closest(".measurement-block");
    if (block) {
      block.remove();
    }
  }
});


const statusCard = document.querySelector(".chart-card");
if (statusCard && window.Chart) {
  const statusChartEl = document.getElementById("statusChart");
  if (statusChartEl) {
    const pending = Number(statusCard.dataset.pending || 0);
    const progress = Number(statusCard.dataset.progress || 0);
    const ready = Number(statusCard.dataset.ready || 0);
    const completed = Number(statusCard.dataset.completed || 0);
    new Chart(statusChartEl, {
      type: "doughnut",
      data: {
        labels: ["Pending", "In progress", "Ready", "Completed"],
        datasets: [
          {
            data: [pending, progress, ready, completed],
            backgroundColor: ["#c9896c", "#a54628", "#f0b59f", "#3f3028"],
            borderWidth: 0,
          },
        ],
      },
      options: {
        plugins: {
          legend: { position: "bottom" },
        },
        cutout: "65%",
      },
    });
  }
}

const teamCard = document.querySelector('.chart-card[data-shirt]');
if (teamCard && window.Chart) {
  const teamChartEl = document.getElementById("teamChart");
  if (teamChartEl) {
    const shirt = Number(teamCard.dataset.shirt || 0);
    const pant = Number(teamCard.dataset.pant || 0);
    new Chart(teamChartEl, {
      type: "bar",
      data: {
        labels: ["Shirt team", "Pant team"],
        datasets: [
          {
            label: "Active orders",
            data: [shirt, pant],
            backgroundColor: ["#a54628", "#2f3a3a"],
            borderRadius: 12,
          },
        ],
      },
      options: {
        plugins: {
          legend: { display: false },
        },
        scales: {
          y: { beginAtZero: true, ticks: { stepSize: 1 } },
        },
      },
    });
  }
}



const toggleBtn = document.getElementById("menuToggle");
const sidebar = document.getElementById("sidebar");
const main = document.querySelector(".main-content");

if (toggleBtn && sidebar && main) {
  toggleBtn.addEventListener("click", () => {
    sidebar.classList.toggle("closed");
    main.classList.toggle("full");
  });
}

document.querySelectorAll(".table-wrap").forEach((wrap) => {
  const filters = Array.from(wrap.querySelectorAll(".table-filters input"));
  const rows = Array.from(wrap.querySelectorAll(".table-row")).filter(
    (row) => !row.classList.contains("table-head")
  );
  if (!filters.length || !rows.length) {
    return;
  }

  const filterSpec = filters.map((input, index) => {
    const col = Number(input.dataset.col ?? index);
    return { input, col };
  });

  const applyFilters = () => {
    rows.forEach((row) => {
      let visible = true;
      for (const spec of filterSpec) {
        const value = spec.input.value.trim().toLowerCase();
        if (!value) {
          continue;
        }
        const cells = row.querySelectorAll(":scope > div");
        const cell = cells[spec.col];
        let text = cell ? cell.textContent.toLowerCase() : "";
        if (cell) {
          const input = cell.querySelector("input, select");
          if (input) {
            text += ` ${input.value.toLowerCase()}`;
          }
        }
        if (!text.includes(value)) {
          visible = false;
          break;
        }
      }
      row.style.display = visible ? "" : "none";
    });
  };

  filters.forEach((input) => {
    input.addEventListener("input", applyFilters);
  });
});

const inventoryTable = document.getElementById("inventory-table");
const inventoryFilters = document.querySelectorAll(".inventory-filters input");
if (inventoryTable && inventoryFilters.length) {
  const rows = Array.from(inventoryTable.querySelectorAll("tbody tr"));
  const applyInventoryFilters = () => {
    rows.forEach((row) => {
      const cells = row.querySelectorAll("td");
      if (!cells.length) {
        return;
      }
      let visible = true;
      inventoryFilters.forEach((input) => {
        const value = input.value.trim().toLowerCase();
        if (!value) {
          return;
        }
        const col = Number(input.dataset.col || 0);
        const text = cells[col] ? cells[col].textContent.toLowerCase() : "";
        if (!text.includes(value)) {
          visible = false;
        }
      });
      row.style.display = visible ? "" : "none";
    });
  };
  inventoryFilters.forEach((input) => {
    input.addEventListener("input", applyInventoryFilters);
  });
}

const vendorTable = document.getElementById("vendor-table");
const vendorFilters = document.querySelectorAll(".vendor-filters input");
if (vendorTable && vendorFilters.length) {
  const rows = Array.from(vendorTable.querySelectorAll("tbody tr"));
  const applyVendorFilters = () => {
    rows.forEach((row) => {
      const cells = row.querySelectorAll("td");
      if (!cells.length) {
        return;
      }
      let visible = true;
      vendorFilters.forEach((input) => {
        const value = input.value.trim().toLowerCase();
        if (!value) {
          return;
        }
        const col = Number(input.dataset.col || 0);
        const text = cells[col] ? cells[col].textContent.toLowerCase() : "";
        if (!text.includes(value)) {
          visible = false;
        }
      });
      row.style.display = visible ? "" : "none";
    });
  };
  vendorFilters.forEach((input) => {
    input.addEventListener("input", applyVendorFilters);
  });
}

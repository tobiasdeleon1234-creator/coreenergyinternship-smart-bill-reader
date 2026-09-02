const MAX_BYTES = 10 * 1024 * 1024;
const ALLOWED_TYPES = new Set(["image/png", "image/jpeg", "application/pdf"]);

const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const fileRow = document.getElementById("file-row");
const fileName = document.getElementById("file-name");
const fileSize = document.getElementById("file-size");
const clearFile = document.getElementById("clear-file");
const analyzeButton = document.getElementById("analyze-button");
const loading = document.getElementById("loading");
const errorBox = document.getElementById("error");
const results = document.getElementById("results");
const resetButton = document.getElementById("reset-button");

let selectedFile = null;

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

function clearError() {
  errorBox.textContent = "";
  errorBox.classList.add("hidden");
}

function chooseFile(file) {
  clearError();
  results.classList.add("hidden");

  if (!file) return;
  if (!ALLOWED_TYPES.has(file.type)) {
    selectedFile = null;
    analyzeButton.disabled = true;
    fileRow.classList.add("hidden");
    showError("Unsupported file type. Please choose a PNG, JPG/JPEG, or PDF.");
    return;
  }
  if (file.size > MAX_BYTES) {
    selectedFile = null;
    analyzeButton.disabled = true;
    fileRow.classList.add("hidden");
    showError("That file is larger than 10 MB. Please upload a smaller copy.");
    return;
  }

  selectedFile = file;
  fileName.textContent = file.name;
  fileSize.textContent = formatBytes(file.size);
  fileRow.classList.remove("hidden");
  analyzeButton.disabled = false;
}

function resetUpload() {
  selectedFile = null;
  fileInput.value = "";
  fileRow.classList.add("hidden");
  analyzeButton.disabled = true;
  loading.classList.add("hidden");
  results.classList.add("hidden");
  clearError();
}

function confidenceText(value) {
  if (typeof value !== "number") return "";
  return `Estimated confidence: ${Math.round(value * 100)}%`;
}

function moneyLike(value) {
  if (value === null || value === undefined) return "—";
  return Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function renderResults(data) {
  document.getElementById("vendor-name").textContent = data.vendor_name ?? "—";
  document.getElementById("invoice-date").textContent = data.invoice_date ?? "—";
  document.getElementById("total-amount").textContent = moneyLike(data.total_amount);
  document.getElementById("tax-amount").textContent = moneyLike(data.tax_amount);

  const c = data.estimated_confidence || {};
  document.getElementById("vendor-confidence").textContent = confidenceText(c.vendor_name);
  document.getElementById("date-confidence").textContent = confidenceText(c.invoice_date);
  document.getElementById("total-confidence").textContent = confidenceText(c.total_amount);
  document.getElementById("tax-confidence").textContent = confidenceText(c.tax_amount);
  document.getElementById("line-confidence").textContent = confidenceText(c.line_items);

  const body = document.getElementById("line-items-body");
  body.innerHTML = "";

  if (!data.line_items || data.line_items.length === 0) {
    const row = document.createElement("tr");
    row.innerHTML = '<td colspan="2" class="empty-row">No readable line items were found.</td>';
    body.appendChild(row);
  } else {
    data.line_items.forEach((item) => {
      const row = document.createElement("tr");
      const desc = document.createElement("td");
      const amount = document.createElement("td");
      desc.textContent = item.description || "—";
      amount.textContent = moneyLike(item.amount);
      row.append(desc, amount);
      body.appendChild(row);
    });
  }

  results.classList.remove("hidden");
  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

dropZone.addEventListener("click", () => fileInput.click());
dropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    fileInput.click();
  }
});
fileInput.addEventListener("change", () => chooseFile(fileInput.files[0]));
clearFile.addEventListener("click", resetUpload);
resetButton.addEventListener("click", resetUpload);

["dragenter", "dragover"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("dragover");
  });
});
["dragleave", "drop"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragover");
  });
});
dropZone.addEventListener("drop", (event) => chooseFile(event.dataTransfer.files[0]));

analyzeButton.addEventListener("click", async () => {
  if (!selectedFile) return;

  clearError();
  results.classList.add("hidden");
  loading.classList.remove("hidden");
  analyzeButton.disabled = true;

  const formData = new FormData();
  formData.append("file", selectedFile);

  try {
    const response = await fetch("/api/extract", { method: "POST", body: formData });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(payload.detail || "The document could not be processed.");
    }

    renderResults(payload);
  } catch (error) {
    showError(error.message || "Something went wrong. Please try again.");
  } finally {
    loading.classList.add("hidden");
    analyzeButton.disabled = !selectedFile;
  }
});

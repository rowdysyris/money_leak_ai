import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import apiClient, { getFriendlyErrorMessage } from "../api/client";
import AppLayout from "../components/AppLayout";
import AppIcon from "../components/ui/AppIcon";
import EmptyState from "../components/ui/EmptyState";
import ErrorBanner from "../components/ui/ErrorBanner";
import WarningBanner from "../components/ui/WarningBanner";
import { useToast } from "../components/ui/Toast";
import { PROFILE_TYPES } from "../constants/categories";
import { formatCurrency, formatDate } from "../utils/formatters";
import { useAuth } from "../context/AuthContext";

const BANK_PRESETS = [
  ["auto", "Auto-detect bank"],
  ["generic", "Generic fallback"],
  ["sbi", "SBI"],
  ["hdfc", "HDFC Bank"],
  ["icici", "ICICI Bank"],
  ["axis", "Axis Bank"],
  ["kotak", "Kotak Mahindra Bank"],
  ["canara", "Canara Bank"],
  ["union", "Union Bank"],
  ["paytm", "Paytm Payments Bank"]
];
const MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024;

function formatFileSize(size) {
  const bytes = Number(size ?? 0);
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 KB";
  }
  return bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : `${Math.ceil(bytes / 1024)} KB`;
}

/**
 * Return true when a filename is an accepted spreadsheet format.
 */
function isAcceptedFile(filename) {
  return /\.(csv|xlsx|xls)$/i.test(filename ?? "");
}

/**
 * Render a compact transaction preview table after upload.
 */
function PreviewTable({ rows }) {
  const safeRows = Array.isArray(rows) ? rows : [];
  if (safeRows.length === 0) {
    return <EmptyState icon="receipt" title="No preview rows" description="The parser did not return previewable transactions." />;
  }
  return (
    <div className="table-scroll overflow-x-auto rounded-3xl border border-slate-200">
      <table className="min-w-[760px] w-full bg-white text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">Date</th>
            <th className="px-4 py-3">Merchant</th>
            <th className="px-4 py-3">Description</th>
            <th className="px-4 py-3 text-right">Amount</th>
            <th className="px-4 py-3">Type</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {safeRows.map((row, index) => (
            <tr key={`${row?.transaction_date ?? "row"}-${index}`}>
              <td className="px-4 py-3 font-medium text-slate-700">{formatDate(row?.transaction_date)}</td>
              <td className="px-4 py-3 font-bold text-slate-950">{row?.merchant ?? "Unknown"}</td>
              <td className="max-w-xs px-4 py-3 text-slate-500"><span className="line-clamp-2">{row?.description ?? "—"}</span></td>
              <td className="px-4 py-3 text-right font-black">{formatCurrency(row?.amount)}</td>
              <td className="px-4 py-3 capitalize">{row?.transaction_type ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Render the bank statement upload workflow.
 */
export default function Upload() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [profileType, setProfileType] = useState("Student");
  const [city, setCity] = useState("");
  const [bankPreset, setBankPreset] = useState("auto");
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [columnMapping, setColumnMapping] = useState({});
  const [error, setError] = useState("");
  const fileInputRef = useRef(null);
  const { user } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();

  /**
   * Validate and store an uploaded file.
   */
  function handleFile(file) {
    setResult(null);
    setColumnMapping({});
    setError("");
    if (!file) {
      return;
    }
    if (/\.pdf$/i.test(file.name)) {
      const message = "PDF isn't supported yet. Export your statement from your banking app as CSV or Excel.";
      setError(message);
      showToast({ type: "error", message });
      return;
    }
    if (!isAcceptedFile(file.name)) {
      const message = "Only CSV and Excel files are supported.";
      setError(message);
      showToast({ type: "error", message });
      return;
    }
    if (file.size > MAX_UPLOAD_SIZE_BYTES) {
      const message = "File is larger than the 10 MB upload limit.";
      setError(message);
      showToast({ type: "error", message });
      return;
    }
    setSelectedFile(file);
  }


  /**
   * Validate and store multiple uploaded statement files.
   */
  function handleMultipleFiles(files) {
    setResult(null);
    setError("");
    const incomingFiles = Array.from(files || []);
    const validFiles = incomingFiles.filter((file) => isAcceptedFile(file.name) && !/\.pdf$/i.test(file.name) && file.size <= MAX_UPLOAD_SIZE_BYTES);
    if (validFiles.length !== incomingFiles.length) {
      showToast({ type: "error", message: "Some files were skipped. Use CSV or Excel files up to 10 MB each." });
    }
    setSelectedFiles(validFiles);
  }

  /**
   * Upload the selected file to the backend parser endpoint.
   */
  async function handleUpload(manualMapping = null) {
    if (!selectedFile) {
      showToast({ type: "error", message: "Choose a CSV or Excel file first." });
      return;
    }
    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("bank_preset", bankPreset);
    if (manualMapping) {
      formData.append("column_mapping", JSON.stringify(manualMapping));
    }
    setUploading(true);
    setProgress(15);
    setError("");
    try {
      const response = await apiClient.post("/api/statements/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: function onUploadProgress(event) {
          const percentage = event.total ? Math.round((event.loaded * 80) / event.total) : 40;
          setProgress(Math.min(90, Math.max(20, percentage)));
        }
      });
      setProgress(100);
      const responseData = response?.data?.data ?? null;
      setResult(responseData);
      if (responseData?.requires_column_mapping) {
        setColumnMapping(responseData?.parser_metadata?.column_map ?? {});
        showToast({ type: "info", message: "Confirm the detected columns to continue." });
      } else {
        showToast({ type: "success", message: "Statement processed successfully." });
      }
    } catch (requestError) {
      const message = getFriendlyErrorMessage(requestError);
      setError(message);
      showToast({ type: "error", message });
    } finally {
      setUploading(false);
    }
  }


  /**
   * Upload multiple selected files and merge them into one combined statement.
   */
  async function handleMultipleUpload() {
    if (selectedFiles.length === 0) {
      showToast({ type: "error", message: "Choose two or more CSV or Excel files first." });
      return;
    }
    const formData = new FormData();
    selectedFiles.forEach((file) => formData.append("files", file));
    formData.append("bank_preset", bankPreset);
    setUploading(true);
    setProgress(15);
    setError("");
    try {
      const response = await apiClient.post("/api/statements/upload-multiple", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: function onUploadProgress(event) {
          const percentage = event.total ? Math.round((event.loaded * 80) / event.total) : 40;
          setProgress(Math.min(90, Math.max(20, percentage)));
        }
      });
      setProgress(100);
      setResult(response?.data?.data ?? null);
      showToast({ type: "success", message: "Multiple statements merged successfully." });
    } catch (requestError) {
      const message = getFriendlyErrorMessage(requestError);
      setError(message);
      showToast({ type: "error", message });
    } finally {
      setUploading(false);
    }
  }

  return (
    <AppLayout title="Upload Statement" subtitle="Upload a CSV or Excel export. The parser handles messy bank formats and keeps bad rows isolated.">
      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm lg:row-span-3">
          {error ? <ErrorBanner message={error} /> : null}
          <div
            onDrop={(event) => { event.preventDefault(); handleFile(event.dataTransfer.files?.[0]); }}
            onDragOver={(event) => event.preventDefault()}
            className="mt-4 flex min-h-[260px] cursor-pointer flex-col items-center justify-center rounded-3xl border-2 border-dashed border-blue-200 bg-blue-50/50 px-6 text-center"
            onClick={() => fileInputRef.current?.click()}
          >
            <input ref={fileInputRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={(event) => handleFile(event.target.files?.[0])} />
            <div className="icon-well grid h-16 w-16 place-items-center"><AppIcon name="upload" size={28} /></div>
            <h2 className="mt-4 text-2xl font-black text-slate-950">Drop your CSV or Excel file here</h2>
            <p className="mt-2 text-sm text-slate-500">Accepted formats: .csv, .xlsx, .xls</p>
            {selectedFile ? <p className="mt-4 rounded-full bg-white px-4 py-2 text-sm font-bold text-blue-600">{selectedFile.name} · {formatFileSize(selectedFile.size)}</p> : null}
          </div>

          {uploading ? (
            <div className="mt-5 rounded-3xl bg-slate-50 p-4">
              <div className="flex justify-between text-sm font-bold text-slate-700"><span>Processing your transactions...</span><span>{progress}%</span></div>
              <div className="mt-3 h-3 overflow-hidden rounded-full bg-slate-200">
                <div className="h-full rounded-full bg-blue-500 transition-all" style={{ width: `${progress}%` }} />
              </div>
            </div>
          ) : null}

          <div className="mt-5 flex flex-col gap-3 sm:flex-row">
            <button type="button" onClick={() => handleUpload()} disabled={uploading || !selectedFile} className="rounded-2xl bg-blue-500 px-5 py-3 font-black text-white hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-50">
              Upload and Analyze
            </button>
            {result?.statement_id ? (
              <button type="button" onClick={() => navigate("/dashboard")} className="rounded-2xl border border-slate-200 px-5 py-3 font-black text-slate-800 hover:bg-slate-50">View Dashboard</button>
            ) : null}
          </div>
        </section>

        <section className="rounded-3xl border border-blue-200 bg-white p-5 shadow-sm lg:col-span-1">
          <h2 className="text-lg font-black text-slate-950">Multi-statement upload</h2>
          <p className="mt-2 text-sm text-slate-500">Upload several monthly files together. MoneyLeak AI merges them, removes duplicate rows, and enables month comparison.</p>
          <input type="file" multiple accept=".csv,.xlsx,.xls" onChange={(event) => handleMultipleFiles(event.target.files)} className="mt-4 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm" />
          {selectedFiles.length > 0 ? (
            <div className="mt-4 rounded-2xl bg-blue-50 p-4 text-sm font-semibold text-blue-800">
              {selectedFiles.length} file(s) selected: {selectedFiles.map((file) => file.name).join(", ")}
            </div>
          ) : null}
          <button type="button" onClick={handleMultipleUpload} disabled={uploading || selectedFiles.length === 0} className="mt-4 w-full rounded-2xl bg-slate-950 px-5 py-3 font-black text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50">
            Upload Multiple and Compare Months
          </button>
        </section>

        <aside className="space-y-4">
          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-black text-slate-950">Upload context</h2>
            <label className="mt-4 block text-sm font-bold text-slate-700">Profile selector
              <select value={profileType || user?.profile_type || "Student"} onChange={(event) => setProfileType(event.target.value)} className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3">
                {PROFILE_TYPES.map((profile) => <option key={profile} value={profile}>{profile}</option>)}
              </select>
            </label>
            <label className="mt-4 block text-sm font-bold text-slate-700">City optional
              <input value={city} onChange={(event) => setCity(event.target.value)} className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3" placeholder={user?.city ?? "Bhopal"} />
            </label>
            <label className="mt-4 block text-sm font-bold text-slate-700">Bank parser preset
              <select value={bankPreset} onChange={(event) => setBankPreset(event.target.value)} className="mt-2 w-full rounded-2xl border border-slate-200 px-4 py-3">
                {BANK_PRESETS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
          </section>
          <section className="rounded-3xl border border-green-200 bg-green-50 p-5 text-green-800">
            <h2 className="font-black">Privacy</h2>
            <p className="mt-2 text-sm">Your file is processed securely and raw data is deleted after analysis.</p>
          </section>
        </aside>
      </div>

      {result ? (
        <section className="mt-6 space-y-5 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          {result?.requires_column_mapping ? (
            <div className="rounded-3xl border border-amber-200 bg-amber-50 p-5">
              <h2 className="text-lg font-black text-amber-950">Confirm statement columns</h2>
              <p className="mt-1 text-sm text-amber-800">Mapping confidence is below 70%. Match the fields to headers from your file before processing.</p>
              <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {["date", "description", "amount", "debit", "credit"].map((field) => (
                  <label key={field} className="text-sm font-bold capitalize text-slate-700">{field}
                    <select
                      aria-label={`Map ${field} column`}
                      value={columnMapping?.[field] ?? ""}
                      onChange={(event) => setColumnMapping((previous) => ({ ...previous, [field]: event.target.value || null }))}
                      className="mt-2 w-full rounded-2xl border border-amber-200 bg-white px-4 py-3"
                    >
                      <option value="">Not mapped</option>
                      {(result?.parser_metadata?.source_columns ?? []).map((column) => <option key={`${field}-${column}`} value={column}>{column}</option>)}
                    </select>
                  </label>
                ))}
              </div>
              <button
                type="button"
                onClick={() => handleUpload(columnMapping)}
                disabled={uploading || !columnMapping?.date || !columnMapping?.description || (!columnMapping?.amount && !columnMapping?.debit && !columnMapping?.credit)}
                className="mt-5 rounded-2xl bg-amber-600 px-5 py-3 font-black text-white hover:bg-amber-700 disabled:opacity-50"
              >
                Confirm mapping and process
              </button>
            </div>
          ) : null}
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="rounded-2xl bg-slate-50 p-4"><p className="text-sm text-slate-500">Processed rows</p><p className="text-2xl font-black text-slate-950">{result?.processed_rows ?? 0}</p></div>
            <div className="rounded-2xl bg-slate-50 p-4"><p className="text-sm text-slate-500">Skipped rows</p><p className="text-2xl font-black text-red-500">{result?.skipped_rows ?? 0}</p></div>
            <div className="rounded-2xl bg-slate-50 p-4"><p className="text-sm text-slate-500">Period</p><p className="text-sm font-black text-slate-950">{formatDate(result?.statement_period?.start)} – {formatDate(result?.statement_period?.end)}</p></div>
          </div>
          {result?.parser_metadata?.bank_preset ? (
            <div className="rounded-2xl border border-blue-100 bg-blue-50 p-4 text-sm text-blue-900">
              <p className="font-black">Detected bank: {result.parser_metadata.bank_preset.display_name}</p>
              <p className="mt-1 font-semibold">Confidence: {Math.round((result.parser_metadata.bank_preset.confidence ?? 0) * 100)}% via {result.parser_metadata.bank_preset.source}</p>
            </div>
          ) : null}
          {Array.isArray(result?.files) && result.files.length > 0 ? (
            <div className="overflow-x-auto rounded-2xl border border-slate-200">
              <table className="min-w-[640px] w-full bg-white text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="px-4 py-3">File</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Bank</th><th className="px-4 py-3">Rows</th></tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {result.files.map((fileResult) => (
                    <tr key={fileResult.filename}>
                      <td className="px-4 py-3 font-bold">{fileResult.filename}</td>
                      <td className="px-4 py-3">{fileResult.success ? "Processed" : "Failed"}</td>
                      <td className="px-4 py-3">{fileResult.metadata?.bank_preset?.display_name ?? "Generic fallback"}</td>
                      <td className="px-4 py-3">{fileResult.processed_rows ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          <WarningBanner warnings={result?.warnings ?? []} />
          <PreviewTable rows={result?.preview ?? []} />
        </section>
      ) : null}
    </AppLayout>
  );
}

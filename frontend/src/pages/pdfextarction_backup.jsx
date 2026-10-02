import { useState } from "react";
import { Link } from "react-router-dom";

function PDFExtraction() {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [extractSummary, setExtractSummary] = useState(null);
  const [progressStatus, setProgressStatus] = useState("");

  const handleFiles = (e) => {
    const selected = Array.from(e.target.files);
    setFiles(selected);
    setMessage("");
    setExtractSummary(null);
  };

  const removeFile = (index) => {
    setFiles(files.filter((_, i) => i !== index));
    setMessage("");
    setExtractSummary(null);
  };

  const handleExtraction = async () => {
    if (files.length === 0) {
      alert("Please select at least one PDF");
      return;
    }

    setLoading(true);
    setMessage("");
    setExtractSummary(null);
    setProgressStatus("Uploading catalog PDF(s)...");

    try {
      // ==========================================
      // STEP 1: Upload PDFs
      // ==========================================
      const formData = new FormData();
      files.forEach((file) => {
        formData.append("pdfs", file);
      });

      const uploadResponse = await fetch("http://localhost:5000/api/upload", {
        method: "POST",
        body: formData,
      });

      const uploadData = await uploadResponse.json();
      console.log("Upload Result:", uploadData);

      if (!uploadResponse.ok) {
        throw new Error(uploadData.message || "PDF upload failed");
      }

      // ==========================================
      // STEP 2: Extract Products with AI
      // ==========================================
      setProgressStatus(`Processing ${uploadData.totalFiles} catalog(s) with AI engine...`);

      const fileNames = uploadData.files.map((f) => f.filename);

      const extractResponse = await fetch("http://localhost:5000/api/ai-extract", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ filenames: fileNames }),
      });

      const extractData = await extractResponse.json();
      console.log("AI Extraction Result:", extractData);

      if (!extractResponse.ok) {
        throw new Error(extractData.message || "AI extraction failed");
      }

      setExtractSummary(extractData);
      setMessage(
        `Successfully extracted ${extractData.totalProducts} product(s) across ${extractData.successfulFiles} catalog(s)!`
      );
    } catch (err) {
      console.error("Extraction error:", err);
      setMessage(`Extraction Error: ${err.message}`);
    } finally {
      setLoading(false);
      setProgressStatus("");
    }
  };

  return (
    <div>
      {/* TOPBAR */}
      <div className="topbar">
        <div>
          <p className="eyebrow">AI DOCUMENT INTELLIGENCE</p>
          <h1>PDF Extraction</h1>
        </div>

        <div className="top-actions">
          <button className="icon-button" title="Help">?</button>

          <div className="profile">
            <div className="avatar">K</div>
            <div>
              <strong>Admin</strong>
              <span>Workspace</span>
            </div>
          </div>
        </div>
      </div>

      {/* PAGE HEADER */}
      <div className="extraction-header">
        <div>
          <span className="hero-badge">✦ AI EXTRACTION ENGINE v4.5</span>

          <h2>
            Extract ceramic & bathware
            <span> product intelligence.</span>
          </h2>

          <p>
            Upload one or multiple ceramic, bathware, faucet, and sanitaryware catalogs.
            Ceramic AI will automatically identify product codes, names, finishes, dimensions,
            prices, and crop high-resolution product images.
          </p>
        </div>

        <div className="extraction-stat">
          <span>SUPPORTED</span>
          <strong>Multi-PDF</strong>
          <small>Batch Extraction Active</small>
        </div>
      </div>

      {/* UPLOAD CARD */}
      <section className="workspace extraction-workspace">
        <div className="section-heading">
          <div>
            <span className="step-label">STEP 01</span>
            <h3>Select product catalogs</h3>
          </div>

          <span className="file-limit">PDF • Multi-file support</span>
        </div>

        <label className="big-dropzone">
          <input
            type="file"
            accept=".pdf"
            multiple
            hidden
            onChange={handleFiles}
          />

          <div className="big-upload-icon">↑</div>

          <h3>Drop your ceramic & bathware catalogs here</h3>

          <p>
            Drag & drop multiple PDF files or
            <span> browse files</span>
          </p>

          <small>Select multiple catalogs to process together</small>
        </label>

        {/* FILE LIST */}
        {files.length > 0 && (
          <div className="files-panel">
            <div className="files-header">
              <strong>
                {files.length} document{files.length > 1 ? "s" : ""} selected
              </strong>
              <span>Ready for AI processing</span>
            </div>

            {files.map((file, index) => (
              <div className="file-row" key={index}>
                <div className="file-left">
                  <div className="pdf-icon">PDF</div>
                  <div>
                    <strong>{file.name}</strong>
                    <span>{(file.size / 1024 / 1024).toFixed(2)} MB</span>
                  </div>
                </div>

                <button
                  className="remove-button"
                  onClick={() => removeFile(index)}
                  disabled={loading}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}

        {/* PROCESSING PREVIEW */}
        <div className="extraction-fields">
          <div className="section-heading">
            <div>
              <span className="step-label">STEP 02</span>
              <h3>AI extraction schema</h3>
            </div>

            <span className="ai-live">● ENGINE ONLINE</span>
          </div>

          <div className="field-chips">
            <span>Product Code / SKU</span>
            <span>Product Name</span>
            <span>Category</span>
            <span>Collection</span>
            <span>Finish & Texture</span>
            <span>Price / MRP (₹)</span>
            <span>Size & Dimensions</span>
            <span>Cropped Images</span>
            <span>Tile Surfaces</span>
            <span>Sanitaryware Specs</span>
          </div>
        </div>

        {/* ACTION */}
        <div className="action-area">
          <div className="processing-note">
            <span>✦</span>
            {loading
              ? progressStatus || "AI engine is analyzing catalogs..."
              : "AI will extract all products, specifications, and images in batch mode."}
          </div>

          <button
            className="process-button"
            disabled={files.length === 0 || loading}
            onClick={handleExtraction}
          >
            <span>✦</span>
            {loading ? "Processing Catalogs..." : "Start AI Extraction"}
            <span>→</span>
          </button>
        </div>

        {/* RESULT MESSAGE & SUMMARY */}
        {message && (
          <div
            style={{
              marginTop: "24px",
              padding: "20px",
              borderRadius: "12px",
              background: extractSummary ? "#0e1e17" : "#1a1616",
              border: extractSummary ? "1px solid #165b38" : "1px solid #6b2020",
              color: extractSummary ? "#4ade80" : "#f87171",
              fontWeight: "600",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span>{message}</span>
              {extractSummary && (
                <Link
                  to="/products"
                  style={{
                    background: "#22c55e",
                    color: "#000",
                    padding: "8px 16px",
                    borderRadius: "8px",
                    textDecoration: "none",
                    fontWeight: "700",
                    fontSize: "0.9rem",
                  }}
                >
                  View Extracted Products →
                </Link>
              )}
            </div>

            {extractSummary?.files && (
              <div style={{ marginTop: "15px", paddingTop: "12px", borderTop: "1px solid #233e30" }}>
                <small style={{ color: "#9ca3af", display: "block", marginBottom: "8px" }}>
                  Catalog Breakdown:
                </small>
                {extractSummary.files.map((fileRes, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: "0.85rem",
                      padding: "4px 0",
                      color: fileRes.success ? "#a7f3d0" : "#fca5a5",
                    }}
                  >
                    <span>📄 {fileRes.filename}</span>
                    <span>
                      {fileRes.success
                        ? `✓ ${fileRes.pythonResult?.totalProducts || 0} products`
                        : `✗ ${fileRes.error || "Failed"}`}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

export default PDFExtraction;
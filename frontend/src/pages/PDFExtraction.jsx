import { useState } from "react";

function PDFExtraction() {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const handleFiles = (e) => {
    const selected = Array.from(e.target.files);
    setFiles(selected);
    setMessage("");
  };

  const removeFile = (index) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  const handleExtraction = async () => {
  if (files.length === 0) {
    alert("Please select at least one PDF");
    return;
  }

  setLoading(true);
  setMessage("");

  try {
    // ==========================================
    // STEP 1: Upload PDFs
    // ==========================================

    const formData = new FormData();

    files.forEach((file) => {
      formData.append("pdfs", file);
    });

    const uploadResponse = await fetch(
      "http://localhost:5000/api/upload",
      {
        method: "POST",
        body: formData,
      }
    );

    const uploadData = await uploadResponse.json();

    console.log("Upload Result:", uploadData);

    if (!uploadResponse.ok) {
      throw new Error(
        uploadData.message || "PDF upload failed"
      );
    }

    // ==========================================
    // STEP 2: Extract Products
    // ==========================================

   // STEP 2: Extract Products

const extractResponse = await fetch(
  "http://localhost:5000/api/ai-extract",
  {
    method: "POST",
  }
);

const extractData = await extractResponse.json();

console.log("AI Extraction Result:", extractData);

if (!extractResponse.ok) {
  throw new Error(
    extractData.message || "AI extraction failed"
  );
}

setMessage(
  `AI extraction completed successfully! ${extractData.totalFiles} file(s) processed.`
);
  } finally {
    setLoading(false);
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
          <button className="icon-button">?</button>

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
          <span className="hero-badge">
            ✦ AI EXTRACTION ENGINE
          </span>

          <h2>
            Extract ceramic product
            <span> intelligence.</span>
          </h2>

          <p>
            Upload one or multiple ceramic catalogs. Ceramic AI
            will automatically identify product specifications,
            images and structured information.
          </p>
        </div>

        <div className="extraction-stat">
          <span>SUPPORTED</span>
          <strong>PDF</strong>
          <small>Multiple documents</small>
        </div>
      </div>

      {/* UPLOAD CARD */}
      <section className="workspace extraction-workspace">

        <div className="section-heading">
          <div>
            <span className="step-label">STEP 01</span>
            <h3>Select product catalogs</h3>
          </div>

          <span className="file-limit">
            PDF • Max 50 MB
          </span>
        </div>

        <label className="big-dropzone">

          <input
            type="file"
            accept=".pdf"
            multiple
            hidden
            onChange={handleFiles}
          />

          <div className="big-upload-icon">
            ↑
          </div>

          <h3>Drop your ceramic catalogs here</h3>

          <p>
            Drag & drop multiple PDF files or
            <span> browse files</span>
          </p>

          <small>
            You can upload multiple documents at once
          </small>

        </label>

        {/* FILE LIST */}
        {files.length > 0 && (
          <div className="files-panel">

            <div className="files-header">
              <strong>
                {files.length} document
                {files.length > 1 ? "s" : ""} selected
              </strong>

              <span>
                Ready for processing
              </span>
            </div>

            {files.map((file, index) => (
              <div className="file-row" key={index}>

                <div className="file-left">

                  <div className="pdf-icon">
                    PDF
                  </div>

                  <div>
                    <strong>{file.name}</strong>

                    <span>
                      {(file.size / 1024 / 1024).toFixed(2)} MB
                    </span>
                  </div>

                </div>

                <button
                  className="remove-button"
                  onClick={() => removeFile(index)}
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
              <h3>AI extraction profile</h3>
            </div>

            <span className="ai-live">
              ● AI READY
            </span>
          </div>

          <div className="field-chips">

            <span>Product Name</span>
            <span>Product Code</span>
            <span>Size</span>
            <span>Finish</span>
            <span>Color</span>
            <span>Design</span>
            <span>Thickness</span>
            <span>Surface</span>
            <span>Application</span>
            <span>Material</span>
            <span>Usage</span>
            <span>Packing</span>
            <span>Product Image</span>
            <span>OCR Data</span>

          </div>

        </div>

        {/* ACTION */}
        <div className="action-area">

          <div className="processing-note">
            <span>✦</span>

            AI will automatically analyze text, images and
            scanned pages.
          </div>

          <button
            className="process-button"
            disabled={files.length === 0 || loading}
            onClick={handleExtraction}
          >
            <span>✦</span>

            {loading
              ? "Extracting..."
              : "Start AI Extraction"}

            <span>→</span>
          </button>

        </div>

        {/* RESULT MESSAGE */}
        {message && (
          <div
            style={{
              marginTop: "20px",
              padding: "15px",
              borderRadius: "10px",
              background: "#f5f5f5",
              fontWeight: "600",
            }}
          >
            {message}
          </div>
        )}

      </section>
    </div>
  );
}

export default PDFExtraction;
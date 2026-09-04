import { useState } from "react";

function Settings() {
  const [ocr, setOcr] = useState(true);
  const [images, setImages] = useState(true);
  const [autoProcess, setAutoProcess] = useState(true);

  return (
    <div>
      <div className="topbar">
        <div>
          <p className="eyebrow">WORKSPACE CONFIGURATION</p>
          <h1>Settings</h1>
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

      <section className="settings-hero">
        <div>
          <span className="hero-badge">✦ CERAMIC AI ENGINE</span>

          <h2>
            Configure your
            <span> extraction workspace.</span>
          </h2>

          <p>
            Control how Ceramic AI reads, processes and structures
            your ceramic product catalogs.
          </p>
        </div>

        <div className="settings-engine">
          <div className="engine-ring"></div>
          <div className="engine-core">✦</div>
        </div>
      </section>

      <section className="settings-card">

        <div className="settings-heading">
          <div>
            <span className="step-label">01 • AI PROCESSING</span>
            <h3>Extraction preferences</h3>
          </div>

          <span className="settings-ready">
            ● Engine Ready
          </span>
        </div>

        <div className="setting-row">
          <div className="setting-icon">⌁</div>

          <div className="setting-content">
            <strong>OCR for scanned PDFs</strong>
            <p>
              Automatically detect text from scanned and image-based
              ceramic catalogs.
            </p>
          </div>

          <button
            className={ocr ? "toggle active" : "toggle"}
            onClick={() => setOcr(!ocr)}
          >
            <span></span>
          </button>
        </div>

        <div className="setting-row">
          <div className="setting-icon">▧</div>

          <div className="setting-content">
            <strong>Extract product images</strong>
            <p>
              Detect and extract product and design images from PDFs.
            </p>
          </div>

          <button
            className={images ? "toggle active" : "toggle"}
            onClick={() => setImages(!images)}
          >
            <span></span>
          </button>
        </div>

        <div className="setting-row">
          <div className="setting-icon">✦</div>

          <div className="setting-content">
            <strong>Automatic processing</strong>
            <p>
              Start AI extraction automatically after PDF upload.
            </p>
          </div>

          <button
            className={autoProcess ? "toggle active" : "toggle"}
            onClick={() => setAutoProcess(!autoProcess)}
          >
            <span></span>
          </button>
        </div>

      </section>

      <section className="settings-card">

        <div className="settings-heading">
          <div>
            <span className="step-label">02 • PRODUCT SCHEMA</span>
            <h3>AI extraction fields</h3>
          </div>
        </div>

        <div className="schema-grid">

          {[
            "Product Name",
            "Product Code",
            "Size",
            "Finish",
            "Color",
            "Design",
            "Surface",
            "Thickness",
            "Application",
            "Material",
            "Usage",
            "Packing",
          ].map((field) => (
            <div className="schema-item" key={field}>
              <span>✓</span>
              {field}
            </div>
          ))}

        </div>

      </section>

      <section className="settings-card">

        <div className="settings-heading">
          <div>
            <span className="step-label">03 • SYSTEM</span>
            <h3>Workspace information</h3>
          </div>
        </div>

        <div className="system-grid">

          <div>
            <span>PROCESSING ENGINE</span>
            <strong>AI Ceramic Extractor</strong>
          </div>

          <div>
            <span>PDF SUPPORT</span>
            <strong>Multiple Documents</strong>
          </div>

          <div>
            <span>OUTPUT FORMAT</span>
            <strong>Structured JSON</strong>
          </div>

          <div>
            <span>STORAGE</span>
            <strong>Local Processing</strong>
          </div>

        </div>

      </section>

      <footer>
        <span>© 2026 Ceramic AI</span>
        <span>AI-powered document intelligence</span>
      </footer>
    </div>
  );
}

export default Settings;
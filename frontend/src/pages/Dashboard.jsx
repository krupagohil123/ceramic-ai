import { Link } from "react-router-dom";

function Dashboard() {
  return (
    <div className="dashboard-page">

      {/* PAGE HEADER */}
      <div className="page-header">
        <div>
          <span className="eyebrow">CERAMIC INTELLIGENCE</span>

          <h1>
            Good morning, Admin.
          </h1>

          <p>
            Manage ceramic documents, AI extraction and product data
            from one workspace.
          </p>
        </div>

        <Link
          to="/pdf-extraction"
          className="dashboard-primary-btn"
        >
          <span>✦</span>
          New Extraction
          <span>→</span>
        </Link>
      </div>

      {/* HERO */}
      <section className="dashboard-hero">

        <div className="dashboard-hero-content">

          <span className="dashboard-ai-badge">
            ✦ AI DOCUMENT INTELLIGENCE
          </span>

          <h2>
            Transform ceramic
            <br />
            catalogs into <span>structured data.</span>
          </h2>

          <p>
            Upload multiple product catalogs and let Ceramic AI
            automatically detect specifications, images and product
            information.
          </p>

          <Link
            to="/pdf-extraction"
            className="hero-action"
          >
            Start extracting
            <span>→</span>
          </Link>

        </div>

        <div className="dashboard-visual">

          <div className="visual-circle visual-circle-1" />
          <div className="visual-circle visual-circle-2" />

          <div className="visual-tile">
            <span>◈</span>
          </div>

          <div className="floating-stat stat-top">
            <div className="floating-icon">PDF</div>

            <div>
              <strong>Catalog</strong>
              <small>Processing ready</small>
            </div>

            <span className="floating-check">✓</span>
          </div>

          <div className="floating-stat stat-bottom">

            <div className="floating-icon gold">
              ✦
            </div>

            <div>
              <strong>AI Extraction</strong>
              <small>Product intelligence</small>
            </div>

          </div>

        </div>

      </section>

      {/* STAT CARDS */}
      <section className="dashboard-stats">

        <div className="stat-card">

          <div className="stat-card-top">
            <span className="stat-label">
              DOCUMENTS
            </span>

            <span className="stat-icon">
              ◫
            </span>
          </div>

          <strong className="stat-number">
            0
          </strong>

          <span className="stat-description">
            Total PDFs processed
          </span>

        </div>

        <div className="stat-card">

          <div className="stat-card-top">
            <span className="stat-label">
              PRODUCTS
            </span>

            <span className="stat-icon">
              ▦
            </span>
          </div>

          <strong className="stat-number">
            0
          </strong>

          <span className="stat-description">
            Products extracted
          </span>

        </div>

        <div className="stat-card">

          <div className="stat-card-top">
            <span className="stat-label">
              SUCCESS RATE
            </span>

            <span className="stat-icon success">
              ✓
            </span>
          </div>

          <strong className="stat-number">
            0%
          </strong>

          <span className="stat-description">
            Successful extractions
          </span>

        </div>

        <div className="stat-card">

          <div className="stat-card-top">
            <span className="stat-label">
              AI STATUS
            </span>

            <span className="stat-icon live">
              ●
            </span>
          </div>

          <strong className="stat-number status-text">
            Ready
          </strong>

          <span className="stat-description">
            Extraction engine online
          </span>

        </div>

      </section>

      {/* LOWER GRID */}
      <section className="dashboard-grid">

        {/* QUICK ACTION */}
        <div className="dashboard-panel">

          <div className="panel-header">
            <div>
              <span className="panel-eyebrow">
                QUICK ACTION
              </span>

              <h3>
                Start a new workflow
              </h3>
            </div>
          </div>

          <div className="quick-actions">

            <Link
              to="/pdf-extraction"
              className="quick-action"
            >
              <div className="quick-icon">
                ↑
              </div>

              <div>
                <strong>
                  Upload PDF catalogs
                </strong>

                <span>
                  Process multiple documents with AI
                </span>
              </div>

              <span className="quick-arrow">
                →
              </span>
            </Link>

            <Link
              to="/products"
              className="quick-action"
            >
              <div className="quick-icon">
                ▦
              </div>

              <div>
                <strong>
                  View extracted products
                </strong>

                <span>
                  Browse structured ceramic data
                </span>
              </div>

              <span className="quick-arrow">
                →
              </span>
            </Link>

            <Link
              to="/history"
              className="quick-action"
            >
              <div className="quick-icon">
                ◷
              </div>

              <div>
                <strong>
                  Processing history
                </strong>

                <span>
                  Review previous extraction jobs
                </span>
              </div>

              <span className="quick-arrow">
                →
              </span>
            </Link>

          </div>

        </div>

        {/* AI PROFILE */}
        <div className="dashboard-panel ai-profile-panel">

          <div className="panel-header">

            <div>
              <span className="panel-eyebrow">
                EXTRACTION PROFILE
              </span>

              <h3>
                Ceramic Product AI
              </h3>
            </div>

            <span className="profile-ready">
              ● READY
            </span>

          </div>

          <p className="profile-description">
            The AI engine is configured to identify important ceramic
            product specifications from uploaded documents.
          </p>

          <div className="profile-fields">

            <span>Product Code</span>
            <span>Product Name</span>
            <span>Size</span>
            <span>Finish</span>
            <span>Color</span>
            <span>Design</span>
            <span>Thickness</span>
            <span>Application</span>

          </div>

          <div className="profile-footer">
            <span>
              + more attributes
            </span>

            <Link to="/pdf-extraction">
              Configure →
            </Link>
          </div>

        </div>

      </section>

    </div>
  );
}

export default Dashboard;
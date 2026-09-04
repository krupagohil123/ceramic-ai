import { useState } from "react";

function History() {
  const [filter, setFilter] = useState("All");

  const history = [
    {
      name: "Somany_Ceramic_Catalog.pdf",
      date: "23 Aug 2026 • 05:42 PM",
      products: 126,
      pages: 84,
      status: "Completed",
      time: "2m 18s",
    },
    {
      name: "Kajaria_Floor_Tiles.pdf",
      date: "23 Aug 2026 • 04:15 PM",
      products: 89,
      pages: 62,
      status: "Completed",
      time: "1m 46s",
    },
    {
      name: "Orientbell_Wall_Tiles.pdf",
      date: "23 Aug 2026 • 02:38 PM",
      products: 54,
      pages: 41,
      status: "Processing",
      time: "—",
    },
    {
      name: "Premium_Ceramic_Collection.pdf",
      date: "22 Aug 2026 • 06:20 PM",
      products: 0,
      pages: 37,
      status: "Failed",
      time: "—",
    },
  ];

  const filteredHistory =
    filter === "All"
      ? history
      : history.filter((item) => item.status === filter);

  return (
    <div className="history-page">

      {/* HERO */}
      <section className="history-hero">

        <div className="history-hero-content">

          <span className="hero-badge">
            ✦ PROCESSING CENTER
          </span>

          <h2>
            Every extraction,
            <span> in one place.</span>
          </h2>

          <p>
            Track your ceramic catalog processing activity,
            extracted products and document status.
          </p>

        </div>

        <div className="history-summary">

          <div>
            <strong>4</strong>
            <span>Documents</span>
          </div>

          <div>
            <strong>269</strong>
            <span>Products</span>
          </div>

        </div>

      </section>

      {/* HISTORY SECTION */}
      <section className="history-section">

        <div className="history-toolbar">

          <div>
            <span className="step-label">
              EXTRACTION LOG
            </span>

            <h3>Recent processing</h3>
          </div>

          <div className="history-filters">

            {["All", "Completed", "Processing", "Failed"].map(
              (item) => (
                <button
                  key={item}
                  className={
                    filter === item
                      ? "history-filter active"
                      : "history-filter"
                  }
                  onClick={() => setFilter(item)}
                >
                  {item}
                </button>
              )
            )}

          </div>

        </div>

        {/* HISTORY LIST */}
        <div className="history-list">

          {filteredHistory.map((item, index) => (

            <div className="history-item" key={index}>

              <div className="history-file-icon">
                PDF
              </div>

              <div className="history-file">
                <strong>{item.name}</strong>
                <span>{item.date}</span>
              </div>

              <div className="history-data">
                <span>PRODUCTS</span>
                <strong>
                  {item.products || "—"}
                </strong>
              </div>

              <div className="history-data">
                <span>PAGES</span>
                <strong>
                  {item.pages}
                </strong>
              </div>

              <div className="history-data">
                <span>PROCESS TIME</span>
                <strong>
                  {item.time}
                </strong>
              </div>

              <div>
                <span
                  className={`history-status ${item.status
                    .toLowerCase()
                    .replace(" ", "-")}`}
                >
                  <i></i>
                  {item.status}
                </span>
              </div>

              <button className="history-action">
                →
              </button>

            </div>

          ))}

        </div>

        {/* EMPTY STATE */}
        {filteredHistory.length === 0 && (
          <div className="history-empty">

            <div>◷</div>

            <h3>No processing records</h3>

            <p>
              Your extraction history will appear here.
            </p>

          </div>
        )}

        {/* FOOTER */}
        <div className="history-footer">

          <span>
            Showing {filteredHistory.length} processing records
          </span>

          <span>
            ✦ Ceramic AI Processing Engine
          </span>

        </div>

      </section>

    </div>
  );
}

export default History;
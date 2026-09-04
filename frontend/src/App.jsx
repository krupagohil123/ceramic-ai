import { BrowserRouter, Routes, Route, Link, useLocation } from "react-router-dom";

import Dashboard from "./pages/Dashboard";
import PDFExtraction from "./pages/PDFExtraction";
import Products from "./pages/Products";
import History from "./pages/History";
import Settings from "./pages/Settings";

import "./App.css";

function SidebarLink({ to, icon, children }) {
  const location = useLocation();

  const active =
    to === "/"
      ? location.pathname === "/"
      : location.pathname.startsWith(to);

  return (
    <Link to={to} className={`nav-item ${active ? "active" : ""}`}>
      <span className="nav-icon">{icon}</span>
      <span>{children}</span>
    </Link>
  );
}

function App() {
  return (
    <BrowserRouter>
      <div className="app">

        {/* SIDEBAR */}
        <aside className="sidebar">

          <div className="brand">
            <div className="brand-mark">
              <span>◈</span>
            </div>

            <div className="brand-text">
              <h2>Ceramic AI</h2>
              <span>DOCUMENT INTELLIGENCE</span>
            </div>
          </div>

          <div className="sidebar-label">
            WORKSPACE
          </div>

          <nav>

            <SidebarLink to="/" icon="⌂">
              Dashboard
            </SidebarLink>

            <SidebarLink to="/pdf-extraction" icon="◫">
              PDF Extraction
            </SidebarLink>

            <SidebarLink to="/products" icon="▦">
              Products
            </SidebarLink>

            <SidebarLink to="/history" icon="◷">
              Processing History
            </SidebarLink>

          </nav>

          <div className="sidebar-label system-label">
            SYSTEM
          </div>

          <nav>
            <SidebarLink to="/settings" icon="⚙">
              Settings
            </SidebarLink>
          </nav>

          <div className="sidebar-spacer" />

          <div className="engine-card">
            <div className="engine-top">
              <div className="engine-icon">✦</div>

              <div>
                <strong>AI Engine</strong>
                <span>Operational</span>
              </div>

              <span className="online-dot" />
            </div>

            <div className="engine-line">
              <span />
            </div>

            <small>
              Ready for document processing
            </small>
          </div>

          <div className="sidebar-footer">
            <span>v1.0.0</span>
            <span>© 2026 Ceramic AI</span>
          </div>

        </aside>

        {/* MAIN */}
        <main className="main">

          <header className="topbar">

            <div className="topbar-left">
              <span className="topbar-status">
                <span />
                Workspace online
              </span>
            </div>

            <div className="top-actions">

              <button className="icon-button" title="Help">
                ?
              </button>

              <div className="profile">

                <div className="avatar">
                  K
                </div>

                <div className="profile-info">
                  <strong>Admin</strong>
                  <span>Workspace</span>
                </div>

                <span className="profile-arrow">
                  ⌄
                </span>

              </div>

            </div>

          </header>

          <div className="content">

            <Routes>

              <Route
                path="/"
                element={<Dashboard />}
              />

              <Route
                path="/pdf-extraction"
                element={<PDFExtraction />}
              />

              <Route
                path="/products"
                element={<Products />}
              />

              <Route
                path="/history"
                element={<History />}
              />

              <Route
                path="/settings"
                element={<Settings />}
              />

            </Routes>

          </div>

        </main>

      </div>
    </BrowserRouter>
  );
}

export default App;
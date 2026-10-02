import { useEffect, useState } from "react";
import axios from "axios";

function Products() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");
  const [collection, setCollection] = useState("All");
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // ==========================================
  // Get products from backend
  // ==========================================
  useEffect(() => {
    const getProducts = async () => {
      try {
        setLoading(true);
        setError("");

        const response = await axios.get("http://localhost:5000/api/products", {
          timeout: 60000,
        });

        if (response.data.success && Array.isArray(response.data.products)) {
          const allProducts = response.data.products;
          setProducts(allProducts);

          if (allProducts.length === 0) {
            setError("No products found. Upload and extract catalogs from the PDF Extraction page.");
          }
        } else {
          setError(response.data.message || "Product data not found");
        }
      } catch (err) {
        console.error("Products API failed:", err);
        if (err.response) {
          setError(err.response.data?.message || `Backend error: ${err.response.status}`);
        } else if (err.request) {
          setError("Cannot reach backend server. Please ensure Node.js is running on port 5000.");
        } else {
          setError(err.message || "Failed to load products.");
        }
      } finally {
        setLoading(false);
      }
    };

    getProducts();
  }, []);

  // ==========================================
  // Filter products
  // ==========================================
  const filteredProducts = products.filter((product) => {
    const productName = product.productName || "";
    const productCode = product.productCode || "";
    const productColl = product.collection || "";

    const matchesSearch =
      productName.toLowerCase().includes(search.toLowerCase()) ||
      productCode.toLowerCase().includes(search.toLowerCase()) ||
      productColl.toLowerCase().includes(search.toLowerCase());

    const matchesCategory =
      category === "All" || product.category === category;

    const matchesCollection =
      collection === "All" || product.collection === collection;

    return matchesSearch && matchesCategory && matchesCollection;
  });

  // Dynamic filter options
  const categories = [
    "All",
    ...new Set(products.map((p) => p.category).filter(Boolean)),
  ];

  const collections = [
    "All",
    ...new Set(products.map((p) => p.collection).filter(Boolean)),
  ];

  // Export JSON
  const exportJSON = () => {
    const dataStr = JSON.stringify(products, null, 2);
    const blob = new Blob([dataStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `ceramic-products-${Date.now()}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <div className="products-loading">
        <h2>Loading extracted products...</h2>
        <p>Fetching structured catalog database from Ceramic AI.</p>
      </div>
    );
  }

  if (error && products.length === 0) {
    return (
      <div className="products-error">
        <h2>No Product Data</h2>
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div>
      {/* TOPBAR */}
      <div className="topbar">
        <div>
          <p className="eyebrow">CERAMIC & BATHWARE INTELLIGENCE</p>
          <h1>Products Library</h1>
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

      {/* HEADER CARD */}
      <section className="products-hero">
        <div>
          <span className="hero-badge">✦ EXTRACTED CATALOG DATABASE</span>

          <h2>
            Your ceramic & bathware
            <span> product library.</span>
          </h2>

          <p>
            Browse, search and export product data extracted from all uploaded catalogs.
            Includes product codes, MRP prices, dimensions, finishes, and cropped visuals.
          </p>
        </div>

        <div className="product-total">
          <span>TOTAL PRODUCTS</span>
          <strong>{products.length}</strong>
          <small>AI extracted records</small>
        </div>
      </section>

      {/* PRODUCTS SECTION */}
      <section className="products-section">
        <div className="products-toolbar">
          <div>
            <span className="step-label">CATALOG REPOSITORY</span>
            <h3>Extracted products ({filteredProducts.length})</h3>
          </div>

          <button className="export-button" onClick={exportJSON}>
            ↓ Export JSON
          </button>
        </div>

        {/* SEARCH + FILTERS */}
        <div className="product-filters" style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
          <div className="search-box" style={{ flex: "1", minWidth: "250px" }}>
            <span>⌕</span>
            <input
              type="text"
              placeholder="Search by code, product name, or collection..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            style={{ minWidth: "180px" }}
          >
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat === "All" ? "All Categories" : cat}
              </option>
            ))}
          </select>

          {collections.length > 2 && (
            <select
              value={collection}
              onChange={(e) => setCollection(e.target.value)}
              style={{ minWidth: "180px" }}
            >
              {collections.map((coll) => (
                <option key={coll} value={coll}>
                  {coll === "All" ? "All Collections" : `Collection: ${coll}`}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* TABLE */}
        <div className="products-table-wrapper">
          <table className="products-table">
            <thead>
              <tr>
                <th>PRODUCT & CODE</th>
                <th>CATEGORY & COLLECTION</th>
                <th>PRICE / MRP</th>
                <th>FINISH / COLOR</th>
                <th>SIZE / DIMENSIONS</th>
                <th>PAGE</th>
                <th>STATUS</th>
              </tr>
            </thead>

            <tbody>
              {filteredProducts.map((product, index) => (
                <tr key={index}>
                  {/* PRODUCT */}
                  <td>
                    <div className="product-name">
                      <div className="product-image">
                        {product.image ? (
                          <img
                            src={`http://localhost:5000/${product.image}`}
                            alt={product.productName || "Product"}
                            onError={(e) => {
                              e.currentTarget.style.display = "none";
                            }}
                          />
                        ) : (
                          <span>
                            {product.productCode
                              ? product.productCode.substring(0, 3)
                              : product.productName
                              ? product.productName.substring(0, 2).toUpperCase()
                              : "PR"}
                          </span>
                        )}
                      </div>

                      <div>
                        <strong>{product.productName || "Product"}</strong>
                        <span style={{ color: "#d4af37", fontWeight: "600", fontSize: "0.85rem" }}>
                          {product.productCode ? `Code: ${product.productCode}` : "No Code"}
                        </span>
                      </div>
                    </div>
                  </td>

                  {/* CATEGORY & COLLECTION */}
                  <td>
                    <div>
                      <span className="category-badge">
                        {product.category || "Ceramic"}
                      </span>
                      {product.collection && (
                        <small style={{ display: "block", marginTop: "4px", color: "#9ca3af" }}>
                          {product.collection}
                        </small>
                      )}
                    </div>
                  </td>

                  {/* PRICE / MRP */}
                  <td>
                    <strong style={{ color: "#22c55e", fontSize: "0.95rem" }}>
                      {product.price || "—"}
                    </strong>
                  </td>

                  {/* FINISH */}
                  <td>
                    {Array.isArray(product.finish) && product.finish.length > 0
                      ? product.finish.join(", ")
                      : product.color || "—"}
                  </td>

                  {/* SIZE */}
                  <td>
                    {Array.isArray(product.size) && product.size.length > 0
                      ? product.size.join(", ")
                      : product.size || "—"}
                  </td>

                  {/* PAGE */}
                  <td>
                    <span style={{ color: "#9ca3af", fontSize: "0.85rem" }}>
                      {Array.isArray(product.pages) && product.pages.length > 0
                        ? `p. ${product.pages.join(", ")}`
                        : "—"}
                    </span>
                  </td>

                  {/* STATUS */}
                  <td>
                    <span className="product-status">
                      <i></i>
                      Extracted
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* NO PRODUCTS FOUND */}
          {filteredProducts.length === 0 && (
            <div className="no-products">
              <div>⌕</div>
              <h3>No matching products found</h3>
              <p>Try clearing your search or category/collection filters.</p>
            </div>
          )}
        </div>

        {/* FOOTER */}
        <div className="products-footer">
          <span>
            Showing {filteredProducts.length} of {products.length} products
          </span>
          <span>✦ Powered by Ceramic AI Engine</span>
        </div>
      </section>
    </div>
  );
}

export default Products;
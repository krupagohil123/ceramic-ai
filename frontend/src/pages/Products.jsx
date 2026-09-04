import { useEffect, useState } from "react";
import axios from "axios";


function Products() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");
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

      const response = await axios.get(
        "http://localhost:5000/api/products",
        {
          timeout: 60000,
        }
      );

      console.log("Products Result:", response.data);
      console.log("SUCCESS:", response.data.success);
      console.log("TOTAL:", response.data.totalProducts);
      console.log("PRODUCTS ARRAY:", response.data.products);
      console.log(
        "IS ARRAY:",
        Array.isArray(response.data.products)
      );

      // /api/products directly returns products
   if (
  response.data.success &&
  Array.isArray(response.data.products)
) {
  const allProducts = response.data.products;

  console.log("Total Products:", response.data.totalProducts);
  console.log("All Products:", allProducts);

  setProducts(allProducts);

  if (allProducts.length === 0) {
    setError("No products found in extracted PDF");
  }
} else {
  setError(
    response.data.message ||
      "Product data not found"
  );
}
    } catch (err) {
      console.error(
        "Products API failed:",
        err
      );

      if (err.response) {
        setError(
          err.response.data?.message ||
            `Backend error: ${err.response.status}`
        );
      } else if (err.request) {
        setError(
          "Backend se response nahi aa raha. Node.js server check karo."
        );
      } else {
        setError(
          err.message ||
            "Failed to load products."
        );
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

    const matchesSearch =
      productName.toLowerCase().includes(search.toLowerCase()) ||
      productCode.toLowerCase().includes(search.toLowerCase());

    const matchesCategory =
      category === "All" || product.category === category;

    return matchesSearch && matchesCategory;
  });

  // ==========================================
  // Categories dynamically from backend
  // ==========================================

  const categories = [
    "All",
    ...new Set(
      products
        .map((product) => product.category)
        .filter(Boolean)
    ),
  ];

  // ==========================================
  // Loading
  // ==========================================

  if (loading) {
    return (
      <div className="products-loading">
        <h2>Loading products...</h2>
        <p>Ceramic AI is loading extracted products.</p>
      </div>
    );
  }

  // ==========================================
  // Error
  // ==========================================

  if (error) {
    return (
      <div className="products-error">
        <h2>Unable to load products</h2>
        <p>{error}</p>
      </div>
    );
  }

  // ==========================================
  // Export JSON
  // ==========================================

  const exportJSON = () => {
    const dataStr = JSON.stringify(products, null, 2);

    const blob = new Blob([dataStr], {
      type: "application/json",
    });

    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");

    link.href = url;
    link.download = "ceramic-products.json";

    document.body.appendChild(link);

    link.click();

    document.body.removeChild(link);

    URL.revokeObjectURL(url);
  };

  // ==========================================
  // UI
  // ==========================================

  return (
    <div>

      {/* TOPBAR */}

      <div className="topbar">

        <div>
          <p className="eyebrow">
            CERAMIC PRODUCT INTELLIGENCE
          </p>

          <h1>Products</h1>
        </div>

        <div className="top-actions">

          <button className="icon-button">
            ?
          </button>

          <div className="profile">

            <div className="avatar">
              K
            </div>

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

          <span className="hero-badge">
            ✦ EXTRACTED CATALOG
          </span>

          <h2>
            Your ceramic
            <span> product library.</span>
          </h2>

          <p>
            Browse, search and review product information
            extracted from your ceramic catalogs.
          </p>

        </div>


        <div className="product-total">

          <span>TOTAL PRODUCTS</span>

          <strong>
            {products.length}
          </strong>

          <small>
            AI extracted records
          </small>

        </div>

      </section>


      {/* PRODUCTS CARD */}

      <section className="products-section">

        <div className="products-toolbar">

          <div>

            <span className="step-label">
              PRODUCT DATABASE
            </span>

            <h3>
              Extracted products
            </h3>

          </div>


          <button
            className="export-button"
            onClick={exportJSON}
          >
            ↓ Export JSON
          </button>

        </div>


        {/* SEARCH + FILTER */}

        <div className="product-filters">

          <div className="search-box">

            <span>⌕</span>

            <input
              type="text"
              placeholder="Search product name or code..."
              value={search}
              onChange={(e) =>
                setSearch(e.target.value)
              }
            />

          </div>


          <select
            value={category}
            onChange={(e) =>
              setCategory(e.target.value)
            }
          >

            {categories.map((cat) => (
              <option
                key={cat}
                value={cat}
              >
                {cat === "All"
                  ? "All Categories"
                  : cat}
              </option>
            ))}

          </select>

        </div>


        {/* TABLE */}

        <div className="products-table-wrapper">

          <table className="products-table">

            <thead>

              <tr>

                <th>PRODUCT</th>

                <th>CATEGORY</th>

                <th>SIZE</th>

                <th>FINISH</th>

                <th>COLOR</th>

                <th>STATUS</th>

              </tr>

            </thead>


            <tbody>

              {filteredProducts.map(
                (product, index) => (

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
      {product.productName
        ? product.productName.substring(0, 2).toUpperCase()
        : "PR"}
    </span>
  )}
</div>

                        <div>

                          <strong>
                            {product.productName ||
                              "Unknown Product"}
                          </strong>

                          <span>
                            {product.productCode ||
                              "No Code"}
                          </span>

                        </div>

                      </div>

                    </td>


                    {/* CATEGORY */}

                    <td>

                      <span className="category-badge">

                        {product.category ||
                          "Unknown"}

                      </span>

                    </td>


                    {/* SIZE */}

                    <td>

                      {Array.isArray(
                        product.size
                      )
                        ? product.size.join(", ")
                        : product.size || "—"}

                    </td>


                    {/* FINISH */}

                    <td>

                      {Array.isArray(
                        product.finish
                      )
                        ? product.finish.join(", ")
                        : product.finish || "—"}

                    </td>


                    {/* COLOR */}

                    <td>

                      {product.color || "—"}

                    </td>


                    {/* STATUS */}

                    <td>

                      <span className="product-status">

                        <i></i>

                        Extracted

                      </span>

                    </td>

                  </tr>

                )
              )}

            </tbody>

          </table>


          {/* NO PRODUCTS */}

          {filteredProducts.length === 0 && (

            <div className="no-products">

              <div>⌕</div>

              <h3>
                No products found
              </h3>

              <p>
                Try changing your search
                or category filter.
              </p>

            </div>

          )}

        </div>


        {/* FOOTER */}

        <div className="products-footer">

          <span>
            Showing {filteredProducts.length} of{" "}
            {products.length} products
          </span>

          <span>
            ✦ Powered by Ceramic AI
          </span>

        </div>

      </section>

    </div>
  );
}

export default Products;
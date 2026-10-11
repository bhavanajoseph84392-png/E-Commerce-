import { useEffect, useState } from "react";
import { getProducts } from "./api";

function App() {
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadProducts(
    searchValue = search,
    categoryValue = category
  ) {
    try {
      setLoading(true);
      setError("");

      const data = await getProducts({
        search: searchValue,
        category: categoryValue,
      });

      if (!data.success) {
        throw new Error(data.message || "Unable to load products");
      }

      setProducts(Array.isArray(data.products) ? data.products : []);
      setCategories(Array.isArray(data.categories) ? data.categories : []);
    } catch (err) {
      console.error("Products API error:", err);

      const message =
        err.response?.data?.message ||
        err.message ||
        "Network Error";

      setError(message);
      setProducts([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadProducts("", "");
  }, []);

  function handleSearch(event) {
    event.preventDefault();
    loadProducts(search, category);
  }

  function handleCategoryChange(event) {
    const value = event.target.value;
    setCategory(value);
    loadProducts(search, value);
  }

  return (
    <div className="app">

      {/* NAVBAR */}
      <header className="navbar">
        <div className="brand">BuyNest</div>

        <nav>
          <a href="#products">Products</a>

          <a href="/user/login">
            Login
          </a>

          <a href="/user/register" className="register-btn">
            Register
          </a>
        </nav>
      </header>

      <main>

        {/* HERO SECTION */}
        <section className="hero">
          <p className="eyebrow">WELCOME TO BUYNEST</p>

          <h1>
            Shop smarter. Shop simpler.
          </h1>

          <p>
            Explore products, add them to your cart, and complete your
            purchase securely with Razorpay.
          </p>
        </section>

        {/* SEARCH */}
        <section className="controls">
          <form onSubmit={handleSearch} className="search-row">

            <input
              type="text"
              placeholder="Search products..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />

            <button type="submit">
              Search
            </button>

            <select
              value={category}
              onChange={handleCategoryChange}
            >
              <option value="">
                All Categories
              </option>

              {categories.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>

          </form>
        </section>

        {/* LOADING */}
        {loading && (
          <div className="message loading-message">
            Loading products...
          </div>
        )}

        {/* ERROR */}
        {!loading && error && (
          <div className="message error-message">

            <strong>
              Unable to load products
            </strong>

            <p>
              {error}
            </p>

            <button
              type="button"
              onClick={() => loadProducts(search, category)}
            >
              Retry
            </button>

          </div>
        )}

        {/* PRODUCTS */}
        {!loading && !error && (
          <section
            id="products"
            className="products-section"
          >

            <div className="section-heading">

              <h2>
                Products
              </h2>

              <span>
                {products.length} product(s)
              </span>

            </div>

            {products.length === 0 ? (

              <div className="empty-message">
                No products found.
              </div>

            ) : (

              <div className="product-grid">

                {products.map((product) => (

                  <article
                    className="product-card"
                    key={product.product_id}
                  >

                    {product.image ? (

                      <img
                        src={`/static/products/${product.image}`}
                        alt={product.name}
                        className="product-image"
                      />

                    ) : (

                      <div className="product-image placeholder">
                        No Image
                      </div>

                    )}

                    <div className="product-content">

                      <p className="category">
                        {product.category || "General"}
                      </p>

                      <h3>
                        {product.name}
                      </h3>

                      <p className="description">
                        {product.description ||
                          "No description available."}
                      </p>

                      <div className="product-footer">

                        <strong>
                          ₹{Number(product.price || 0).toFixed(2)}
                        </strong>

                        <span>
                          Stock: {product.stock ?? 0}
                        </span>

                      </div>

                    </div>

                  </article>

                ))}

              </div>

            )}

          </section>
        )}

      </main>
    </div>
  );
}

export default App;
import { useState, useEffect } from "react";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function App() {
  const [health, setHealth] = useState(null);
  const [items, setItems] = useState([]);
  const [newItem, setNewItem] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    checkHealth();
    fetchItems();
  }, []);

  const checkHealth = async () => {
    try {
      const res = await fetch(`${API_URL}/health`);
      const data = await res.json();
      setHealth(data);
    } catch (e) {
      setHealth({ status: "unreachable" });
    }
  };

  const fetchItems = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_URL}/api/items`);
      const data = await res.json();
      setItems(data);
    } catch (e) {
      setError("Failed to fetch items");
    } finally {
      setLoading(false);
    }
  };

  const createItem = async (e) => {
    e.preventDefault();
    if (!newItem.trim()) return;
    try {
      const res = await fetch(`${API_URL}/api/items`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newItem }),
      });
      const data = await res.json();
      setItems((prev) => [...prev, data]);
      setNewItem("");
    } catch (e) {
      setError("Failed to create item");
    }
  };

  const deleteItem = async (id) => {
    try {
      await fetch(`${API_URL}/api/items/${id}`, { method: "DELETE" });
      setItems((prev) => prev.filter((i) => i.id !== id));
    } catch (e) {
      setError("Failed to delete item");
    }
  };

  return (
    <div className="app">
      <header className="header">
        <div className="logo">
          <span className="logo-icon">⎈</span>
          <h1>K8s Skeleton App</h1>
        </div>
        <div className={`health-badge ${health?.status === "ok" ? "ok" : "error"}`}>
          <span className="dot" />
          {health?.status === "ok" ? `API OK · DB: ${health.db}` : "API Unreachable"}
        </div>
      </header>

      <main className="main">
        <section className="card">
          <h2>Items</h2>
          <form onSubmit={createItem} className="form">
            <input
              value={newItem}
              onChange={(e) => setNewItem(e.target.value)}
              placeholder="New item name..."
              className="input"
            />
            <button type="submit" className="btn">Add</button>
          </form>

          {error && <div className="error-msg">{error}</div>}

          {loading ? (
            <div className="loading">Loading...</div>
          ) : (
            <ul className="list">
              {items.length === 0 && <li className="empty">No items yet. Create one!</li>}
              {items.map((item) => (
                <li key={item.id} className="list-item">
                  <span>{item.name}</span>
                  <button onClick={() => deleteItem(item.id)} className="btn-delete">✕</button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card info-card">
          <h2>Pod Info</h2>
          {health && (
            <ul className="info-list">
              <li><span>Hostname</span><code>{health.hostname || "—"}</code></li>
              <li><span>Version</span><code>{health.version || "1.0.0"}</code></li>
              <li><span>Env</span><code>{health.env || "development"}</code></li>
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;

import FruitDetector from "./components/FruitDetector";
import "./App.css";

export default function App() {
  return (
    <div className="app-shell">
      <header className="site-header">
        <div className="site-brand"><span className="brand-mark">✦</span> Smart Orchard AI</div>
        <a href="/docs" target="_blank" rel="noreferrer">API docs ↗</a>
      </header>
      <main><FruitDetector /></main>
      <footer className="site-footer">YOLOv8s · 7 lớp trái cây · FastAPI + React</footer>
    </div>
  );
}

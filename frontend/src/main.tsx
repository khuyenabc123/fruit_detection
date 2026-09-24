// src/main.tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { ConfigProvider } from "antd";
import App from "./App.tsx";
import "antd/dist/reset.css"; // Global Ant Design styling reset
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: "#52c41a", // Fruit Green theme
          borderRadius: 8,
          fontFamily: "Inter, system-ui, Avenir, Helvetica, Arial, sans-serif",
        },
      }}
    >
      <App />
    </ConfigProvider>
  </React.StrictMode>,
);

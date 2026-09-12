// src/App.tsx
import React from "react";
import { Layout, Typography } from "antd";
import FruitDetector from "./components/FruitDetector";

const { Header, Content, Footer } = Layout;
const { Title } = Typography;

const App: React.FC = () => {
  return (
    <Layout style={{ minHeight: "100vh", backgroundColor: "#f0f2f5" }}>
      <Header
        style={{
          backgroundColor: "#001529",
          display: "flex",
          alignItems: "center",
          padding: "0 24px",
        }}
      >
        <Title level={4} style={{ color: "#ffffff", margin: 0 }}>
          🥭 Smart Orchard AI — Fruit Detection Portal
        </Title>
      </Header>

      <Content style={{ padding: "24px 50px" }}>
        <FruitDetector />
      </Content>

      <Footer style={{ textAlign: "center", color: "#888" }}>
        YOLOv8s Fruit Detection & Ripeness Assessment ©2026 — Powered by Ant
        Design & FastAPI
      </Footer>
    </Layout>
  );
};

export default App;

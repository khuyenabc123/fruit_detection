import React, { useState } from "react";
import {
  Card,
  Upload,
  Button,
  Row,
  Col,
  Statistic,
  Tag,
  Typography,
  Spin,
  Alert,
  Divider,
  Space,
  Badge,
  Descriptions,
} from "antd";
import {
  InboxOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import type { UploadProps } from "antd";

const { Title, Paragraph, Text } = Typography;
const { Dragger } = Upload;

interface DetectionItem {
  class_id: number;
  class_name: string;
  confidence: number;
  bbox: [number, number, number, number];
}

interface DetectionResponse {
  success: boolean;
  filename: string;
  total_count: number;
  counts: {
    mango_unripe: number;
    mango_ripe: number;
    dragonfruit_unripe: number;
    dragonfruit_ripe: number;
  };
  detections: DetectionItem[];
  annotated_image_base64: string;
}

const CLASS_CONFIG: Record<string, { label: string; color: string }> = {
  mango_unripe: { label: "Mango Unripe", color: "green" },
  mango_ripe: { label: "Mango Ripe", color: "gold" },
  dragonfruit_unripe: { label: "Dragon Fruit Unripe", color: "cyan" },
  dragonfruit_ripe: { label: "Dragon Fruit Ripe", color: "magenta" },
};

export const FruitDetector: React.FC = () => {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DetectionResponse | null>(null);

  const API_URL = "http://localhost:8000/detect";

  const handleUpload = async (file: File) => {
    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${API_URL}?conf_threshold=0.25`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(
          `Server returned HTTP ${response.status}: ${response.statusText}`,
        );
      }

      const data: DetectionResponse = await response.json();
      setResult(data);
    } catch (err: any) {
      setError(
        err.message ||
          "Failed to analyze image. Please ensure FastAPI backend is running on port 8000.",
      );
    } finally {
      setLoading(false);
    }
  };

  const uploadProps: UploadProps = {
    name: "file",
    multiple: false,
    showUploadList: false,
    beforeUpload: (file) => {
      const isImage = file.type.startsWith("image/");
      if (!isImage) {
        setError("Please upload a valid image file (JPG, PNG, WEBP).");
        return false;
      }
      handleUpload(file);
      return false;
    },
  };

  const resetAll = () => {
    setResult(null);
    setError(null);
  };

  return (
    <Card
      style={{
        maxWidth: 1100,
        margin: "24px auto",
        borderRadius: 12,
        boxShadow: "0 4px 20px rgba(0,0,0,0.08)",
      }}
    >
      <Title level={3} style={{ textAlign: "center", marginBottom: 8 }}>
        🥭 YOLOv8 Fruit Detection & Ripeness Assessment
      </Title>
      <Paragraph
        style={{ textAlign: "center", color: "#666", marginBottom: 24 }}
      >
        Upload an orchard photo to detect, count, and assess ripeness for
        Mangoes & Dragon Fruits in real-time.
      </Paragraph>

      {/* Upload Drag & Drop Zone */}
      {!result && !loading && (
        <Dragger
          {...uploadProps}
          style={{ padding: "32px 16px", borderRadius: 8 }}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined style={{ color: "#1890ff", fontSize: 48 }} />
          </p>
          <p
            className="ant-upload-text"
            style={{ fontSize: 16, fontWeight: 500 }}
          >
            Click or drag fruit image to this area to upload
          </p>
          <p className="ant-upload-hint" style={{ color: "#888" }}>
            Supports JPG, PNG, WEBP files. Trained on orchard canopy images.
          </p>
        </Dragger>
      )}

      {/* Error Alert */}
      {error && (
        <Alert
          message="Detection Error"
          description={error}
          type="error"
          showIcon
          action={
            <Button size="small" onClick={resetAll}>
              Retry
            </Button>
          }
          style={{ marginTop: 16 }}
        />
      )}

      {/* Loading Spinner */}
      {loading && (
        <div style={{ textAlign: "center", padding: "48px 0" }}>
          <Spin indicator={<SyncOutlined spin style={{ fontSize: 36 }} />} />
          <p style={{ marginTop: 16, fontSize: 16, color: "#555" }}>
            Running single-pass YOLOv8 inference & ripeness assessment...
          </p>
        </div>
      )}

      {/* Detection Results View */}
      {result && (
        <div>
          <Row
            justify="space-between"
            align="middle"
            style={{ marginBottom: 16 }}
          >
            <Col>
              <Space>
                <Tag
                  icon={<CheckCircleOutlined />}
                  color="success"
                  style={{ fontSize: 14, padding: "4px 10px" }}
                >
                  Analysis Complete
                </Tag>
                <Badge
                  count={`File: ${result.filename}`}
                  style={{ backgroundColor: "#52c41a" }}
                />
              </Space>
            </Col>
            <Col>
              <Button
                type="primary"
                icon={<ReloadOutlined />}
                onClick={resetAll}
              >
                Analyze Another Image
              </Button>
            </Col>
          </Row>

          <Divider />

          {/* Summary Statistics */}
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={6}>
              <Card
                size="small"
                style={{ textAlign: "center", backgroundColor: "#fafafa" }}
              >
                <Statistic
                  title="Total Fruits Found"
                  value={result.total_count}
                  valueStyle={{ color: "#1890ff", fontWeight: "bold" }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card
                size="small"
                style={{ textAlign: "center", backgroundColor: "#f6ffed" }}
              >
                <Statistic
                  title="Mango Unripe"
                  value={result.counts.mango_unripe || 0}
                  valueStyle={{ color: "#52c41a" }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card
                size="small"
                style={{ textAlign: "center", backgroundColor: "#fffbe6" }}
              >
                <Statistic
                  title="Mango Ripe"
                  value={result.counts.mango_ripe || 0}
                  valueStyle={{ color: "#faad14" }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card
                size="small"
                style={{ textAlign: "center", backgroundColor: "#fff0f6" }}
              >
                <Statistic
                  title="Dragon Fruit Ripe"
                  value={result.counts.dragonfruit_ripe || 0}
                  valueStyle={{ color: "#eb2f96" }}
                />
              </Card>
            </Col>
          </Row>

          {/* Image & Bounding Box Details Layout */}
          <Row gutter={24}>
            {/* Left Column: Annotated Image Output */}
            <Col span={14}>
              <Card title="YOLOv8 Detection Visual Output" size="small">
                <img
                  src={result.annotated_image_base64}
                  alt="YOLO Detection Output"
                  style={{
                    width: "100%",
                    borderRadius: 8,
                    objectFit: "contain",
                  }}
                />
              </Card>
            </Col>

            {/* Right Column: Object List & Bounding Box Coordinates */}
            <Col span={10}>
              <Card
                title={`Detected Fruit Bounding Boxes (${result.detections.length})`}
                size="small"
              >
                <div style={{ maxHeight: 420, overflowY: "auto" }}>
                  {result.detections.length === 0 ? (
                    <Paragraph style={{ color: "#888" }}>
                      No fruit bounding boxes detected with confidence &ge;
                      0.25.
                    </Paragraph>
                  ) : (
                    result.detections.map((det, index) => {
                      const cfg = CLASS_CONFIG[det.class_name] || {
                        label: det.class_name,
                        color: "blue",
                      };
                      return (
                        <Descriptions
                          key={index}
                          size="small"
                          column={1}
                          bordered
                          style={{ marginBottom: 12 }}
                          title={
                            <Space>
                              <Tag color={cfg.color}>{cfg.label}</Tag>
                              <Text type="secondary">
                                Conf: {(det.confidence * 100).toFixed(1)}%
                              </Text>
                            </Space>
                          }
                        >
                          <Descriptions.Item label="BBox [xmin, ymin, xmax, ymax]">
                            {det.bbox.join(", ")}
                          </Descriptions.Item>
                        </Descriptions>
                      );
                    })
                  )}
                </div>
              </Card>
            </Col>
          </Row>
        </div>
      )}
    </Card>
  );
};

export default FruitDetector;

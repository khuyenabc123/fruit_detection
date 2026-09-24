import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Row,
  Slider,
  Spin,
  Statistic,
  Tag,
  Typography,
  Upload,
} from "antd";
import {
  CheckCircleOutlined,
  CloudUploadOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import type { UploadProps } from "antd";

const { Dragger } = Upload;
const { Text, Title, Paragraph } = Typography;
const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const MAX_IMAGE_BYTES = 12 * 1024 * 1024;

interface DetectionItem {
  class_id: number;
  class_name: string;
  confidence: number;
  detection_confidence?: number;
  ripeness_confidence?: number;
  uncertain?: boolean;
  bbox: number[];
}

interface DetectionResponse {
  success: boolean;
  filename: string;
  total_count: number;
  counts: Record<string, number>;
  detections: DetectionItem[];
  annotated_image_base64: string;
}

interface HealthResponse {
  model_loaded: boolean;
  model_classes: string[];
  pipeline_mode?: "legacy" | "two-stage";
}

const CLASS_CONFIG: Record<string, { label: string; color: string }> = {
  mango_unripe: { label: "Xoài chưa chín", color: "green" },
  mango_premature: { label: "Xoài non", color: "green" },
  mango_early: { label: "Xoài chín sớm", color: "lime" },
  mango_mature: { label: "Xoài trưởng thành", color: "gold" },
  mango_ripe: { label: "Xoài chín", color: "orange" },
  dragonfruit_unripe: { label: "Thanh long chưa chín", color: "cyan" },
  dragonfruit_ripe: { label: "Thanh long chín", color: "magenta" },
  dragonfruit_rotten: { label: "Thanh long hỏng", color: "red" },
  mango_uncertain: { label: "Xoài chưa chắc độ chín", color: "default" },
  dragonfruit_uncertain: { label: "Thanh long chưa chắc độ chín", color: "default" },
};

function classConfig(name: string) {
  return CLASS_CONFIG[name] || { label: name.replaceAll("_", " "), color: "blue" };
}

export default function FruitDetector() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [threshold, setThreshold] = useState(0.25);
  const [ripenessThreshold, setRipenessThreshold] = useState(0.8);
  const [result, setResult] = useState<DetectionResponse | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_BASE}/health`, { signal: controller.signal })
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((data: HealthResponse) => setHealth(data))
      .catch(() => { if (!controller.signal.aborted) setHealth(null); });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    return () => { if (previewUrl) URL.revokeObjectURL(previewUrl); };
  }, [previewUrl]);

  const uploadProps: UploadProps = {
    accept: "image/jpeg,image/png,image/webp",
    multiple: false,
    showUploadList: false,
    beforeUpload: (selected) => {
      if (!selected.type.startsWith("image/")) {
        setError("Hãy chọn ảnh JPG, PNG hoặc WEBP.");
      } else if (selected.size > MAX_IMAGE_BYTES) {
        setError("Ảnh cần nhỏ hơn 12 MB.");
      } else {
        setFile(selected);
        setPreviewUrl(URL.createObjectURL(selected));
        setResult(null);
        setError(null);
      }
      return false;
    },
  };

  async function handleDetect() {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const response = await fetch(
        `${API_BASE}/detect?conf_threshold=${threshold.toFixed(2)}&ripeness_threshold=${ripenessThreshold.toFixed(2)}`,
        {
        method: "POST",
        body: formData,
        },
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `API trả về HTTP ${response.status}`);
      if (!data.success) throw new Error("API không trả về kết quả hợp lệ.");
      setResult(data as DetectionResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không thể kết nối API. Hãy thử lại.");
    } finally {
      setLoading(false);
    }
  }

  const foundClasses = Object.entries(result?.counts || {}).filter(([, count]) => count > 0);

  return (
    <div className="detector-page">
      <div className="page-heading">
        <div>
          <Text className="eyebrow">FRUIT DETECTION LAB</Text>
          <Title level={1}>Thử model nhận diện trái cây</Title>
          <Paragraph>Chọn ảnh mới, chỉnh ngưỡng tin cậy và xem box, nhãn cùng số lượng quả mà model dự đoán.</Paragraph>
        </div>
        <Tag color={health?.model_loaded ? "success" : "warning"} className="model-status">
          {health?.model_loaded
            ? `Model sẵn sàng · ${health.pipeline_mode === "two-stage" ? "pipeline 2 bước" : `${health.model_classes.length} lớp`}`
            : "Đang kiểm tra model"}
        </Tag>
      </div>

      <Row gutter={[24, 24]} align="stretch">
        <Col xs={24} lg={9}>
          <Card className="control-card" title="1. Chọn ảnh để thử">
            <Dragger {...uploadProps} className="upload-zone">
              <CloudUploadOutlined className="upload-icon" />
              <div className="upload-title">Kéo ảnh vào đây hoặc nhấp để chọn</div>
              <Text type="secondary">JPG, PNG, WEBP · tối đa 12 MB</Text>
            </Dragger>

            {file && <div className="selected-file"><CheckCircleOutlined /> {file.name}</div>}

            <div className="threshold-label">
              <Text strong>Ngưỡng phát hiện quả</Text>
              <Text>{Math.round(threshold * 100)}%</Text>
            </div>
            <Slider min={0.1} max={0.9} step={0.05} value={threshold} onChange={setThreshold} />
            <Text type="secondary" className="helper-text">Ngưỡng này ưu tiên không bỏ sót box; độ chín được lọc riêng bên dưới.</Text>

            <div className="threshold-label">
              <Text strong>Ngưỡng độ chín</Text>
              <Text>{Math.round(ripenessThreshold * 100)}%</Text>
            </div>
            <Slider min={0.5} max={0.95} step={0.05} value={ripenessThreshold} onChange={setRipenessThreshold} />
            <Text type="secondary" className="helper-text">Dưới ngưỡng này hệ thống trả về “chưa chắc” thay vì ép nhãn chín.</Text>

            <Button
              type="primary"
              size="large"
              block
              icon={<PlayCircleOutlined />}
              disabled={!file}
              loading={loading}
              onClick={handleDetect}
              className="run-button"
            >
              {loading ? "Đang phân tích..." : "Chạy nhận diện"}
            </Button>
            {file && <Button type="link" icon={<ReloadOutlined />} onClick={() => { setFile(null); setPreviewUrl(null); setResult(null); setError(null); }}>Chọn ảnh khác</Button>}
            {error && <Alert type="error" showIcon message="Không chạy được" description={error} className="error-alert" />}
          </Card>
        </Col>

        <Col xs={24} lg={15}>
          <Card className="preview-card" title="2. Kiểm tra kết quả">
            {loading ? (
              <div className="empty-preview"><Spin size="large" /><Text type="secondary">Model đang xử lý ảnh. Lần gọi đầu có thể chậm khi cloud khởi động.</Text></div>
            ) : result ? (
              <div className="preview-content">
                <div className="image-pair">
                  <div><Text strong>Ảnh gốc</Text><img src={previewUrl || ""} alt="Ảnh gốc" /></div>
                  <div><Text strong>Model dự đoán</Text><img src={result.annotated_image_base64} alt="Ảnh có box và nhãn dự đoán" /></div>
                </div>
                <div className="result-summary">
                  <Statistic title="Tổng số quả phát hiện" value={result.total_count} />
                  <div className="class-tags">
                    {foundClasses.length ? foundClasses.map(([name, count]) => {
                      const config = classConfig(name);
                      return <Tag key={name} color={config.color}>{config.label}: {count}</Tag>;
                    }) : <Text type="secondary">Không phát hiện quả ở ngưỡng này.</Text>}
                  </div>
                </div>
                {result.detections.length > 0 && (
                  <div className="detection-list">
                    <Text strong>Chi tiết từng box</Text>
                    {result.detections.map((item, index) => (
                      <Descriptions key={`${item.class_id}-${index}`} size="small" column={1} bordered>
                        <Descriptions.Item label={`#${index + 1} · ${classConfig(item.class_name).label}`}>
                          {item.ripeness_confidence !== undefined
                            ? `Độ chín ${(item.ripeness_confidence * 100).toFixed(1)}% · detector ${((item.detection_confidence || 0) * 100).toFixed(1)}%`
                            : `${(item.confidence * 100).toFixed(1)}%`} · [{item.bbox.join(", ")}]
                        </Descriptions.Item>
                      </Descriptions>
                    ))}
                  </div>
                )}
              </div>
            ) : previewUrl ? (
              <div className="selected-preview"><img src={previewUrl} alt="Ảnh đã chọn" /><Text type="secondary">Nhấn “Chạy nhận diện” để xem kết quả.</Text></div>
            ) : (
              <div className="empty-preview"><div className="empty-icon">🥭</div><Text type="secondary">Ảnh và kết quả dự đoán sẽ xuất hiện tại đây.</Text></div>
            )}
          </Card>
        </Col>
      </Row>
      <div className="page-footnote">Kết quả trên ảnh là dự đoán của model. Để đo độ chính xác, cần đánh giá trên tập test có nhãn.</div>
    </div>
  );
}

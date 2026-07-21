import { ArrowLeftOutlined, ToolOutlined } from "@ant-design/icons";
import { Button, Result } from "antd";
import { useNavigate } from "react-router-dom";

type PlaceholderPageProps = { title: string; description: string };

export function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  const navigate = useNavigate();
  return (
    <Result
      icon={<ToolOutlined />}
      title={title}
      subTitle={description}
      extra={<Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/")}>返回工作台</Button>}
    />
  );
}

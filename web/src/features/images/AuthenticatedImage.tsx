import { PictureOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";

import { imageApi } from "./imageApi";

type Props = {
  imageId: string;
  alt: string;
};

export function AuthenticatedImage({ imageId, alt }: Props) {
  const [source, setSource] = useState<string>();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    let objectUrl = "";
    setFailed(false);
    void imageApi.content(imageId)
      .then((blob) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setSource(objectUrl);
      })
      .catch(() => { if (active) setFailed(true); });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [imageId]);

  return source ? <img src={source} alt={alt} /> : <span className={`image-loading ${failed ? "failed" : ""}`}><PictureOutlined /></span>;
}

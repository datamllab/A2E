import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles/app.css";

const basename = (window.Config?.basename ?? "").replace(/\/+$/, "");
const faviconHref = `${basename}/a2e-favicon.png`;
const favicon =
  document.querySelector<HTMLLinkElement>('link[rel~="icon"]') ?? document.createElement("link");
favicon.rel = "icon";
favicon.type = "image/png";
favicon.href = faviconHref;
if (!favicon.isConnected) document.head.append(favicon);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

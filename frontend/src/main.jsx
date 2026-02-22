import { StrictMode } from "react";
import { createRoot }  from "react-dom/client";
import "./index.css";
import "./enhancements.css";  // E2/E4/E5/E6 styles
import App from "./App";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);

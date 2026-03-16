import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import QueryProvider from "@/components/query-provider";
import App from "@/App";
import "@/styles/globals.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <QueryProvider>
      <App />
    </QueryProvider>
  </BrowserRouter>,
);

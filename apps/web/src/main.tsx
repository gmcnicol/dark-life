import { ClerkProvider } from "@clerk/react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import QueryProvider from "@/components/query-provider";
import App from "@/App";
import { clerkEnabled, clerkPublishableKey } from "@/lib/auth-config";
import "@/styles/globals.css";

if (clerkEnabled && !clerkPublishableKey) {
  throw new Error("Add VITE_CLERK_PUBLISHABLE_KEY to the web environment.");
}

const app = (
  <BrowserRouter>
    <QueryProvider>
      <App />
    </QueryProvider>
  </BrowserRouter>
);

ReactDOM.createRoot(document.getElementById("root")!).render(
  clerkEnabled ? (
    <ClerkProvider publishableKey={clerkPublishableKey!} afterSignOutUrl="/sign-in">
      {app}
    </ClerkProvider>
  ) : (
    app
  ),
);

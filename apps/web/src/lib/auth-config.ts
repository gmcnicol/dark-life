export const clerkEnabled = (import.meta.env.VITE_CLERK_ENABLED ?? "false").toLowerCase() !== "false";

export const clerkPublishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string | undefined;

import { SignIn } from "@clerk/react";

export default function SignInRoute() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--app-bg)] px-4 py-10">
      <div className="w-full max-w-[1100px] rounded-[2rem] border border-white/10 bg-[linear-gradient(135deg,rgba(10,18,30,0.96),rgba(8,12,20,0.88))] p-6 shadow-[0_24px_90px_rgba(0,0,0,0.3)] backdrop-blur-xl lg:grid lg:grid-cols-[minmax(0,1fr)_26rem] lg:gap-8">
        <div className="space-y-5 pb-8 lg:pb-0">
          <p className="text-[0.72rem] font-semibold uppercase tracking-[0.34em] text-cyan-200/80">
            Dark Life Studio
          </p>
          <div className="space-y-3">
            <h1 className="font-display text-4xl tracking-[-0.04em] text-white md:text-5xl">
              Operator sign-in
            </h1>
            <p className="max-w-2xl text-sm leading-7 text-[var(--text-soft)] md:text-base">
              Authenticate before opening the story inbox, triggering ingestion, or using the privileged operator controls.
            </p>
          </div>
        </div>
        <div className="flex items-center justify-center rounded-[1.6rem] border border-white/10 bg-black/20 p-4">
          <SignIn fallbackRedirectUrl="/dashboard" />
        </div>
      </div>
    </div>
  );
}

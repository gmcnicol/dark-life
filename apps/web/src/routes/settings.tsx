import { PageHeader, Panel, SectionHeading, StatusBadge } from "@/components/ui-surfaces";

const SETTINGS_GROUPS = [
  {
    title: "Voice defaults",
    items: ["ElevenLabs voice selection", "Narration model profile", "Speaking speed and style"],
  },
  {
    title: "Subtitle defaults",
    items: ["Whisper model target", "Subtitle format", "Burn-in toggle"],
  },
  {
    title: "Render defaults",
    items: ["Music policy", "Queue cadence", "Output target preset"],
  },
];

export default function SettingsRoute() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Operating defaults"
        title="Studio settings"
        description="Keep render defaults, subtitle policy, and voice assumptions legible for operators. This surface is currently informational and should become editable only when those mutations are wired intentionally."
      />
      <div className="grid gap-4 xl:grid-cols-3">
        {SETTINGS_GROUPS.map((group) => (
          <Panel key={group.title} className="space-y-4">
            <SectionHeading
              eyebrow="Default group"
              title={group.title}
              description="Shown here so operators can verify the defaults influencing the pipeline."
            />
            <div className="space-y-3">
              {group.items.map((item) => (
                <div key={item} className="flex items-center justify-between gap-3 rounded-[1.2rem] border border-white/8 bg-white/[0.03] px-4 py-3">
                  <span className="text-sm text-white">{item}</span>
                  <StatusBadge tone="neutral">Planned</StatusBadge>
                </div>
              ))}
            </div>
          </Panel>
        ))}
      </div>
    </div>
  );
}

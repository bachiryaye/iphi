import { useT } from "@/shared/i18n/context";
/** Every observation shown comes from the simulator (P5). */
export function SimTag() {
  const t = useT();
  return (
    <span
      title={t("Source: IPHI simulator, synthetic telemetry")}
      className="inline-flex h-5 items-center rounded-[3px] border border-border-strong px-1.5 font-mono text-micro font-medium tracking-[.03em] text-text-muted"
    >
      SIM
    </span>
  );
}

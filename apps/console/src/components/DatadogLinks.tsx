// Deep links sang Datadog: monitor, logs, traces, notebook
const SITE = import.meta.env.VITE_DD_SITE ?? "datadoghq.com";

export function DatadogLinks({ service, incidentKey }: { service?: string; incidentKey?: string }) {
  const base = `https://app.${SITE}`;
  const q = encodeURIComponent([service && `service:${service}`, incidentKey && `@incident_id:${incidentKey}`].filter(Boolean).join(" "));
  const links = [
    ["Monitors", `${base}/monitors/manage`],
    ["Logs", `${base}/logs?query=${q}`],
    ["Traces", `${base}/apm/traces?query=${q}`],
  ];
  return (
    <div className="flex gap-3 text-xs">
      {links.map(([label, href]) => (
        <a key={label} href={href} target="_blank" rel="noreferrer" className="text-sky-400 hover:underline">
          Datadog: {label} ↗
        </a>
      ))}
    </div>
  );
}

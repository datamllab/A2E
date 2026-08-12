export function MetricTooltip({ text }: { text: string }) {
  const items = text
    .split("\n")
    .map((line) => line.replace(/^-\s*/, "").trim())
    .filter(Boolean);

  return (
    <div className="metric-tooltip" role="tooltip">
      <ul>
        {items.map((item, index) => (
          <li key={`${index}-${item}`}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

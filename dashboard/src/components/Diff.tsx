export function Diff({ text }: { text: string }) {
  const lines = text.replace(/\n$/, "").split("\n");
  return (
    <pre translate="no" className="overflow-x-auto rounded-lg border border-line bg-surface-2 py-2 font-mono text-[12px] leading-relaxed">
      {lines.map((line, i) => {
        const tone =
          line.startsWith("+++") || line.startsWith("---") ? "text-muted"
          : line.startsWith("+") ? "bg-add text-ink"
          : line.startsWith("-") ? "bg-del text-ink"
          : "text-muted";
        return (
          <code key={i} className={`block whitespace-pre px-3 ${tone}`}>
            {line || " "}
          </code>
        );
      })}
    </pre>
  );
}

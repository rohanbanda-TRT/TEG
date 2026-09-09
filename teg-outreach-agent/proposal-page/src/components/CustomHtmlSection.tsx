import { Section } from "./Section";

interface CustomHtmlSectionProps {
  title: string;
  htmlContent: string;
  confidence: string;
}

export function CustomHtmlSection({ title, htmlContent, confidence }: CustomHtmlSectionProps) {
  // Evidence confidence badge colors
  const confidenceColors: Record<string, string> = {
    verified: "bg-green-100 text-green-800",
    inferred: "bg-blue-100 text-blue-800",
    hypothesis: "bg-yellow-100 text-yellow-800",
    requires_confirmation: "bg-orange-100 text-orange-800",
  };

  const badgeColor = confidenceColors[confidence] || "bg-gray-100 text-gray-800";
  const confidenceLabel = confidence.replace(/_/g, " ").toUpperCase();

  return (
    <Section>
      <div className="mb-4 flex items-center gap-2">
        <h3 className="text-xl font-semibold text-gray-900">{title}</h3>
        <span className={`px-2 py-1 text-xs font-medium rounded ${badgeColor}`}>
          {confidenceLabel}
        </span>
      </div>
      <div
        className="prose prose-sm max-w-none"
        dangerouslySetInnerHTML={{ __html: htmlContent }}
      />
    </Section>
  );
}

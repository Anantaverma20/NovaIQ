/**
 * InsightCard component - displays individual insight
 */

interface InsightCardProps {
  insight: {
    id: number;
    title: string;
    summary: string;
    confidence: number;
    created_at: string;
  };
}

export default function InsightCard({ insight }: InsightCardProps) {
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-600 bg-green-50';
    if (confidence >= 0.5) return 'text-yellow-600 bg-yellow-50';
    return 'text-red-600 bg-red-50';
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow">
      <div className="flex justify-between items-start mb-3">
        <h3 className="text-lg font-semibold text-gray-900 flex-1">
          {insight.title}
        </h3>
        <span
          className={`px-2 py-1 rounded text-xs font-medium ${getConfidenceColor(
            insight.confidence
          )}`}
        >
          {(insight.confidence * 100).toFixed(0)}%
        </span>
      </div>

      <p className="text-gray-600 text-sm mb-4 line-clamp-3">
        {insight.summary}
      </p>

      <div className="flex justify-between items-center text-xs text-gray-400">
        <span>ID: {insight.id}</span>
        <span>{formatDate(insight.created_at)}</span>
      </div>
    </div>
  );
}


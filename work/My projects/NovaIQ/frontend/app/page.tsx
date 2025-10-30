'use client';

import { useEffect, useState } from 'react';
import { fetchInsights } from './api';
import InsightCard from '../components/InsightCard';

interface Insight {
  id: number;
  title: string;
  summary: string;
  confidence: number;
  created_at: string;
}

export default function Home() {
  const [insights, setInsights] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadInsights();
  }, []);

  const loadInsights = async () => {
    try {
      setLoading(true);
      const data = await fetchInsights();
      setInsights(data.insights || []);
      setError(null);
    } catch (err) {
      setError('Failed to load insights');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen p-8 bg-gray-50">
      <div className="max-w-6xl mx-auto">
        <header className="mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">NovaIQ</h1>
          <p className="text-gray-600">AI-powered insights and research tracking</p>
        </header>

        {loading && (
          <div className="text-center py-12">
            <p className="text-gray-500">Loading insights...</p>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        {!loading && !error && (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {insights.map((insight) => (
              <InsightCard key={insight.id} insight={insight} />
            ))}
          </div>
        )}

        {!loading && !error && insights.length === 0 && (
          <div className="text-center py-12 bg-white rounded-lg shadow">
            <p className="text-gray-500 mb-4">No insights yet</p>
            <p className="text-sm text-gray-400">
              Trigger ingestion to start collecting insights
            </p>
          </div>
        )}
      </div>
    </main>
  );
}


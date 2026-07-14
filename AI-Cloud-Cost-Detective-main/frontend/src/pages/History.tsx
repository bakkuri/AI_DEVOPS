import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { getAnalysisHistory, getAnalysisById } from '../api';
import { getToken } from '../auth';

interface HistoryItem {
  id: number;
  resource_group: string;
  resources_scanned: number;
  issues_found: number;
  estimated_savings: string | null;
  status: string;
  created_at: string;
}

export const History: React.FC = () => {
  const navigate = useNavigate();
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [loadingAnalysisId, setLoadingAnalysisId] = useState<number | null>(null);

  useEffect(() => {
    if (!getToken()) {
      navigate('/login');
      return;
    }

    const fetchHistory = async () => {
      try {
        const items = await getAnalysisHistory();
        setHistory(items);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch history');
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, [navigate]);

  const handleViewReport = async (analysisDbId: number) => {
    setLoadingAnalysisId(analysisDbId);
    try {
      const analysis = await getAnalysisById(analysisDbId);
      navigate(`/report/${analysis.analysis_id}`, { state: analysis });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analysis');
      setLoadingAnalysisId(null);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-900 text-green-200';
      case 'in_progress':
        return 'bg-blue-900 text-blue-200';
      case 'failed':
        return 'bg-red-900 text-red-200';
      default:
        return 'bg-gray-700 text-gray-200';
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900">
        <Navbar />
        <div className="max-w-6xl mx-auto px-4 py-8">
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 text-center">
            <p className="text-gray-400">Loading history...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900">
      <Navbar />

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
          <h1 className="text-3xl font-bold text-white mb-2">Analysis History</h1>
          <p className="text-gray-400 mb-6">View your past cost analyses</p>

          {error && (
            <div className="mb-4 p-3 bg-red-900 border border-red-700 rounded-lg text-red-200 text-sm">
              {error}
            </div>
          )}

          {history.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-400 mb-4">No analyses yet</p>
              <button
                onClick={() => navigate('/dashboard')}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition"
              >
                Run Your First Analysis
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead className="border-b border-gray-700">
                  <tr>
                    <th className="px-4 py-3 text-gray-300 font-semibold">Resource Group</th>
                    <th className="px-4 py-3 text-gray-300 font-semibold">Date</th>
                    <th className="px-4 py-3 text-gray-300 font-semibold">Resources</th>
                    <th className="px-4 py-3 text-gray-300 font-semibold">Issues Found</th>
                    <th className="px-4 py-3 text-gray-300 font-semibold">Est. Savings</th>
                    <th className="px-4 py-3 text-gray-300 font-semibold">Status</th>
                    <th className="px-4 py-3 text-gray-300 font-semibold">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {history.map((item) => (
                    <tr key={item.id} className="hover:bg-gray-700 transition">
                      <td className="px-4 py-3 text-gray-300">{item.resource_group}</td>
                      <td className="px-4 py-3 text-gray-400 text-sm">{formatDate(item.created_at)}</td>
                      <td className="px-4 py-3 text-gray-300">{item.resources_scanned}</td>
                      <td className="px-4 py-3 text-gray-300">{item.issues_found}</td>
                      <td className="px-4 py-3 text-green-400 font-medium">
                        {item.estimated_savings || '-'}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(item.status)}`}>
                          {item.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => handleViewReport(item.id)}
                          disabled={loadingAnalysisId === item.id}
                          className="text-blue-400 hover:text-blue-300 disabled:text-gray-500 text-sm font-medium transition"
                        >
                          {loadingAnalysisId === item.id ? 'Loading...' : 'View Report →'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <button
          onClick={() => navigate('/dashboard')}
          className="mt-6 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition font-medium"
        >
          ← Back to Dashboard
        </button>
      </div>
    </div>
  );
};

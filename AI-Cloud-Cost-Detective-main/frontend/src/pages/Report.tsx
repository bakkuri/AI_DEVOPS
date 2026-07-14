import React, { useState, useEffect } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { AnalysisResponse, CostIssue } from '../api';
import { getToken } from '../auth';

export const Report: React.FC = () => {
  const { analysisId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);

  useEffect(() => {
    if (!getToken()) {
      navigate('/login');
      return;
    }

    // Get analysis data from route state or parse URL
    if (location.state) {
      setAnalysis(location.state as AnalysisResponse);
    } else {
      // Could fetch from API if needed
      setAnalysis(null);
    }
  }, [location, navigate]);

  if (!analysis) {
    return (
      <div className="min-h-screen bg-gray-900">
        <Navbar />
        <div className="max-w-4xl mx-auto px-4 py-8">
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 text-center">
            <p className="text-gray-400">Loading analysis report...</p>
          </div>
        </div>
      </div>
    );
  }

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'high':
        return 'bg-red-900 text-red-200 border-red-700';
      case 'medium':
        return 'bg-yellow-900 text-yellow-200 border-yellow-700';
      case 'low':
        return 'bg-blue-900 text-blue-200 border-blue-700';
      default:
        return 'bg-gray-700 text-gray-200 border-gray-600';
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  return (
    <div className="min-h-screen bg-gray-900">
      <Navbar />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 mb-6">
          <h1 className="text-3xl font-bold text-white mb-2">Analysis Report</h1>
          <p className="text-gray-400">Resource Group: {analysis.resource_group}</p>
          <p className="text-sm text-gray-500 mt-2">ID: {analysis.analysis_id}</p>
        </div>

        {/* Summary */}
        {analysis.analysis && (
          <>
            <div className="bg-gradient-to-r from-green-900 to-green-800 border border-green-700 rounded-lg p-6 mb-6">
              <h2 className="text-2xl font-bold text-white mb-4">💰 Estimated Savings</h2>
              <p className="text-4xl font-bold text-green-200">
                {analysis.analysis.total_estimated_savings}
              </p>
              <p className="text-green-300 mt-2">
                Found {analysis.analysis.issues.length} cost optimization opportunities
              </p>
            </div>

            {/* Summary Section */}
            <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 mb-6">
              <h3 className="text-xl font-semibold text-white mb-3">Analysis Summary</h3>
              <p className="text-gray-300 leading-relaxed">{analysis.analysis.summary}</p>
            </div>

            {/* Issues */}
            {analysis.analysis.issues.length > 0 && (
              <div className="mb-6">
                <h3 className="text-xl font-semibold text-white mb-4">Issues Found</h3>
                <div className="space-y-4">
                  {analysis.analysis.issues.map((issue, idx) => (
                    <div key={idx} className={`border rounded-lg p-4 ${getSeverityColor(issue.severity)}`}>
                      <div className="flex items-start justify-between mb-2">
                        <div>
                          <h4 className="font-semibold">{issue.title}</h4>
                          <p className="text-sm opacity-90">
                            {issue.resource_name} ({issue.resource_type})
                          </p>
                        </div>
                        <span className="text-xs font-bold px-2 py-1 bg-black bg-opacity-25 rounded">
                          {issue.severity.toUpperCase()}
                        </span>
                      </div>

                      <p className="text-sm mb-3">{issue.description}</p>

                      <div className="flex items-center justify-between">
                        <span className="font-medium">Estimated Savings: {issue.estimated_savings}</span>
                      </div>

                      {issue.fix_command && (
                        <div className="mt-3 pt-3 border-t border-current border-opacity-25">
                          <p className="text-xs font-semibold mb-2 opacity-75">Fix Command:</p>
                          <div className="bg-black bg-opacity-25 rounded p-2 font-mono text-xs overflow-x-auto">
                            {issue.fix_command}
                          </div>
                          <button
                            onClick={() => copyToClipboard(issue.fix_command || '')}
                            className="mt-2 text-xs px-2 py-1 bg-black bg-opacity-25 hover:bg-opacity-40 rounded transition"
                          >
                            📋 Copy Command
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recommendations */}
            {analysis.analysis.recommendations.length > 0 && (
              <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 mb-6">
                <h3 className="text-xl font-semibold text-white mb-4">General Recommendations</h3>
                <ul className="space-y-2">
                  {analysis.analysis.recommendations.map((rec, idx) => (
                    <li key={idx} className="text-gray-300 flex items-start gap-2">
                      <span className="text-blue-400 mt-1">→</span>
                      <span>{rec}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}

        {/* Resources Section */}
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
          <h3 className="text-xl font-semibold text-white mb-4">
            Resources Scanned ({analysis.total_resources})
          </h3>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {analysis.resources.map((resource, idx) => (
              <div key={idx} className="text-sm text-gray-400 p-2 bg-gray-700 rounded">
                <span className="font-medium text-gray-300">{resource.name}</span>
                <span className="mx-2">•</span>
                <span>{resource.resource_type}</span>
                <span className="mx-2">•</span>
                <span>{resource.region}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="mt-6 flex gap-4">
          <button
            onClick={() => navigate('/dashboard')}
            className="flex-1 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition"
          >
            ← Back to Dashboard
          </button>
          <button
            onClick={() => navigate('/history')}
            className="flex-1 py-2 bg-gray-700 hover:bg-gray-600 text-white font-medium rounded-lg transition"
          >
            View History →
          </button>
        </div>
      </div>
    </div>
  );
};

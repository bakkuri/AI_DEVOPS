import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { ProgressTracker } from '../components/ProgressTracker';
import { getResourceGroups, analyzeResourceGroup, connectToProgress } from '../api';
import { getToken } from '../auth';

export const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const [resourceGroups, setResourceGroups] = useState<string[]>([]);
  const [selectedGroup, setSelectedGroup] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [progressMessages, setProgressMessages] = useState<{ message: string; type: string; timestamp: string }[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisId, setAnalysisId] = useState('');
  const [ws, setWs] = useState<WebSocket | null>(null);

  useEffect(() => {
    // Check authentication
    if (!getToken()) {
      navigate('/login');
      return;
    }

    // Fetch resource groups
    const fetchGroups = async () => {
      try {
        const groups = await getResourceGroups();
        setResourceGroups(groups);
        if (groups.length > 0) {
          setSelectedGroup(groups[0]);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch resource groups');
      }
    };

    fetchGroups();
  }, [navigate]);

  // Cleanup WebSocket on unmount
  useEffect(() => {
    return () => {
      if (ws) {
        try {
          ws.close();
        } catch (e) {
          // ignore
        }
      }
    };
  }, [ws]);

  const handleAnalyze = async () => {
    if (!selectedGroup) {
      setError('Please select a resource group');
      return;
    }

    setError('');
    setLoading(true);
    setIsAnalyzing(true);
    setProgressMessages([]);

    try {
      // Start analysis
      const response = await analyzeResourceGroup(selectedGroup);
      setAnalysisId(response.analysis_id);

      // If the backend returned analysis immediately (e.g. OpenAI fallback),
      // skip waiting for WebSocket progress and navigate to the report.
      if (response.analysis) {
        setIsAnalyzing(false);
        navigate(`/report/${response.analysis_id}`, { state: response });
        return;
      }

      // Connect to WebSocket for progress (only when analysis runs asynchronously)
      const newWs = connectToProgress(
        response.analysis_id,
        (msg) => {
          setProgressMessages((prev) => [...prev, msg]);
          if (msg.type === 'completed') {
            setIsAnalyzing(false);
            try {
              newWs.close();
            } catch (e) {
              // ignore
            }
            setTimeout(() => {
              navigate(`/report/${response.analysis_id}`, { state: response });
            }, 1000);
          }
          if (msg.type === 'error') {
            setIsAnalyzing(false);
            try {
              newWs.close();
            } catch (e) {
              // ignore
            }
          }
        },
        (err) => {
          console.error('WebSocket error:', err);
          setError('Connection error during analysis');
          setIsAnalyzing(false);
        },
        () => {
          // cleanup when the socket closes
          setIsAnalyzing(false);
        }
      );

      setWs(newWs);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
      setIsAnalyzing(false);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-900">
      <Navbar />

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
          <h2 className="text-2xl font-bold text-white mb-6">AWS Resource Analysis</h2>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Select AWS Resource Group
              </label>
              <select
                value={selectedGroup}
                onChange={(e) => setSelectedGroup(e.target.value)}
                disabled={isAnalyzing}
                className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
              >
                {resourceGroups.length === 0 ? (
                  <option>No resource groups available</option>
                ) : (
                  resourceGroups.map((group) => (
                    <option key={group} value={group}>
                      {group}
                    </option>
                  ))
                )}
              </select>
            </div>

            {error && (
              <div className="p-3 bg-red-900 border border-red-700 rounded-lg text-red-200 text-sm">
                {error}
              </div>
            )}

            <button
              onClick={handleAnalyze}
              disabled={loading || isAnalyzing || !selectedGroup}
              className="w-full py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white font-medium rounded-lg transition"
            >
              {loading ? 'Starting analysis...' : isAnalyzing ? 'Analyzing...' : 'Run Analysis'}
            </button>

            {isAnalyzing && (
              <ProgressTracker
                messages={progressMessages}
                isComplete={!isAnalyzing}
                error={error}
              />
            )}
          </div>
        </div>

        <div className="mt-8 bg-gray-800 border border-gray-700 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-white mb-4">How it works</h3>
          <ul className="space-y-2 text-gray-300 text-sm">
            <li>✓ Scans all resources in your AWS Resource Group</li>
            <li>✓ Analyzes resources for cost optimization opportunities</li>
            <li>✓ Identifies unused/over-provisioned resources</li>
            <li>✓ Provides AWS CLI commands to fix issues</li>
            <li>✓ Estimates potential savings</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

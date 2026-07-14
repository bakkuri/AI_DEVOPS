import React from 'react';
import { ReactNode } from 'react';

interface ProgressTrackerProps {
  messages: { message: string; type: string; timestamp: string }[];
  isComplete: boolean;
  error?: string;
}

export const ProgressTracker: React.FC<ProgressTrackerProps> = ({ messages, isComplete, error }) => {
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 mt-4">
      <h3 className="text-lg font-semibold text-white mb-3">Progress</h3>

      <div className="space-y-2 max-h-60 overflow-y-auto">
        {messages.length === 0 ? (
          <p className="text-gray-400 text-sm">Waiting to start analysis...</p>
        ) : (
          messages.map((msg, idx) => (
            <div key={idx} className="flex items-start gap-2">
              <div className="flex-shrink-0 mt-1">
                {msg.type === 'completed' ? (
                  <div className="w-4 h-4 bg-green-500 rounded-full"></div>
                ) : msg.type === 'error' ? (
                  <div className="w-4 h-4 bg-red-500 rounded-full"></div>
                ) : (
                  <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                )}
              </div>
              <div className="flex-1">
                <p className="text-sm text-gray-300">{msg.message}</p>
                <p className="text-xs text-gray-500">
                  {new Date(msg.timestamp).toLocaleTimeString()}
                </p>
              </div>
            </div>
          ))
        )}
      </div>

      {error && (
        <div className="mt-3 p-2 bg-red-900 border border-red-700 rounded text-red-200 text-sm">
          {error}
        </div>
      )}

      {isComplete && (
        <div className="mt-3 p-2 bg-green-900 border border-green-700 rounded text-green-200 text-sm">
          Analysis complete!
        </div>
      )}
    </div>
  );
};

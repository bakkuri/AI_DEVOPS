import React from 'react';
import { logout, isAuthenticated } from '../auth';

interface NavbarProps {
  userEmail?: string;
}

export const Navbar: React.FC<NavbarProps> = ({ userEmail }) => {
  const loggedIn = isAuthenticated();

  return (
    <nav className="bg-gray-800 border-b border-gray-700">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">💰</span>
          </div>
          <h1 className="text-xl font-bold text-white">AI Cloud Cost Detective</h1>
        </div>

        <div className="flex items-center gap-4">
          <a href="/dashboard" className="text-gray-300 hover:text-white transition">
            Dashboard
          </a>
          <a href="/history" className="text-gray-300 hover:text-white transition">
            History
          </a>
          {loggedIn && (
            <>
              {userEmail && <span className="text-gray-400 text-sm">{userEmail}</span>}
              <button
                onClick={logout}
                className="px-3 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition text-sm font-medium"
              >
                Logout
              </button>
            </>
          )}
        </div>
      </div>
    </nav>
  );
};

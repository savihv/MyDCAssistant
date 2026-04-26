import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/Button";
import { JuniorTechBotLogo } from "../components/JuniorTechBotLogo";
import { sessionManager, TroubleshootingSession } from "../utils/sessionManager";
import { Timestamp } from "firebase/firestore";
import { ProtectedRoute } from "../components/ProtectedRoute";
import { TechnicianEmptyState } from "../components/TechnicianEmptyState";
import { Link } from "react-router-dom";

export default function History() {
  const navigate = useNavigate();
  
  const [sessions, setSessions] = useState<TroubleshootingSession[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("all");
  const [organizationFilter, setOrganizationFilter] = useState<string>(""); // Added organization filter state
  
  // State for status update dropdown
  const [selectedSession, setSelectedSession] = useState<TroubleshootingSession | null>(null);
  const [updatingStatus, setUpdatingStatus] = useState(false);
  useEffect(() => {
    const fetchSessions = async () => {
      setIsLoading(true);
      setError(null);
      
      try {
        // Fetch sessions using the sessionManager, applying the organization filter
        const fetchedSessions = await sessionManager.listSessions(organizationFilter.trim());
        setSessions(fetchedSessions);
      } catch (err) {
        console.error("Error fetching sessions:", err);
        setError("Failed to load troubleshooting sessions. Please try again.");
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchSessions();
  }, [organizationFilter]); // Added organizationFilter to dependency array
  
  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'new':
        return 'bg-blue-900/50 text-blue-300 border-blue-700';
      case 'in-progress':
        return 'bg-yellow-900/50 text-yellow-300 border-yellow-700';
      case 'completed':
        return 'bg-green-900/50 text-green-300 border-green-700';
      case 'archived':
        return 'bg-gray-800 text-gray-400 border-gray-700';
      default:
        return 'bg-gray-800 text-gray-400 border-gray-700';
    }
  };
  
  const formatDate = (timestamp: Timestamp) => {
    const date = timestamp.toDate();
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };
  
  const handleSessionClick = (sessionId: string) => {
    navigate(`/Response?sessionId=${sessionId}`);
  };
  
  const handleContinueSession = async (sessionId: string) => {
    try {
      await sessionManager.reopenSessionIfNeeded(sessionId);
      navigate(`/SessionChatPage?sessionId=${sessionId}`);
    } catch (error) {
      console.error("Error reopening session:", error);
      setError("Failed to continue the session. Please try again.");
    }
  };

  const handleNewSession = () => {
    navigate('/SessionCreate');
  };
  
  const getFilteredSessions = () => {
    if (filter === "all") {
      return sessions;
    }
    return sessions.filter(session => session.status === filter);
  };
  
  // Handle status update
  const handleStatusUpdate = async (sessionId: string, newStatus: TroubleshootingSession['status']) => {
    setUpdatingStatus(true);
    
    try {
      await sessionManager.updateStatus(sessionId, newStatus);
      
      // Update the sessions list with the new status
      setSessions(prevSessions => 
        prevSessions.map(session => 
          session.id === sessionId ? { ...session, status: newStatus } : session
        )
      );
      
      // Clear the selected session
      setSelectedSession(null);
    } catch (error) {
      console.error("Error updating session status:", error);
      alert("Failed to update session status. Please try again.");
    } finally {
      setUpdatingStatus(false);
    }
  };
  return (
    <ProtectedRoute>
      <div className="flex flex-col min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="py-4 px-4 bg-gray-800 border-b border-gray-700">
        <div className="container mx-auto flex items-center justify-between">
          <div className="flex items-center">
            <JuniorTechBotLogo className="w-8 h-8 mr-2" />
            <h1 className="text-xl font-bold">
              <span className="text-white">Junior</span>
              <span className="text-blue-400">TechBot</span>
            </h1>
          </div>
          <nav>
            <ul className="flex space-x-4">
              <li>
                <button onClick={() => navigate("/")} className="text-gray-300 hover:text-white">
                  Home
                </button>
              </li>
              <li>
                <button onClick={() => navigate("/SessionCreate")} className="text-gray-300 hover:text-white">
                  New Session
                </button>
              </li>
              <li>
                <button onClick={() => navigate("/History")} className="text-blue-400">
                  History
                </button>
              </li>
              <li>
                <button onClick={() => navigate("/KnowledgeBaseSearch")} className="text-gray-300 hover:text-white">
                  Knowledge Base Search
                </button>
              </li>
              <li>
                <Link to="/ExpertSubmission" className="text-gray-300 hover:text-white">
                  Expert Submission
                </Link>
              </li>
            </ul>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 container mx-auto py-8 px-4">
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold">Troubleshooting History</h2>
            <div className="flex space-x-3">
              <Button 
                variant="outline" 
                onClick={() => window.location.reload()}
                className="flex items-center"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Refresh
              </Button>
              <Button 
                variant="default" 
                onClick={handleNewSession}
                className="flex items-center"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                New Session
              </Button>
            </div>
          </div>
          
          {/* Filter Controls */}
          <div className="mb-6 flex flex-wrap gap-2">
            <button 
              className={`px-4 py-2 rounded-md border ${filter === 'all' ? 'bg-gray-700 border-gray-500' : 'bg-gray-800 border-gray-700 text-gray-300 hover:bg-gray-700'}`}
              onClick={() => setFilter('all')}
            >
              All Sessions
            </button>
            <button 
              className={`px-4 py-2 rounded-md border ${filter === 'new' ? 'bg-gray-700 border-gray-500' : 'bg-gray-800 border-gray-700 text-gray-300 hover:bg-gray-700'}`}
              onClick={() => setFilter('new')}
            >
              New
            </button>
            <button 
              className={`px-4 py-2 rounded-md border ${filter === 'in-progress' ? 'bg-gray-700 border-gray-500' : 'bg-gray-800 border-gray-700 text-gray-300 hover:bg-gray-700'}`}
              onClick={() => setFilter('in-progress')}
            >
              In Progress
            </button>
            <button 
              className={`px-4 py-2 rounded-md border ${filter === 'completed' ? 'bg-gray-700 border-gray-500' : 'bg-gray-800 border-gray-700 text-gray-300 hover:bg-gray-700'}`}
              onClick={() => setFilter('completed')}
            >
              Completed
            </button>
            <button 
              className={`px-4 py-2 rounded-md border ${filter === 'archived' ? 'bg-gray-700 border-gray-500' : 'bg-gray-800 border-gray-700 text-gray-300 hover:bg-gray-700'}`}
              onClick={() => setFilter('archived')}
            >
              Archived
            </button>
          </div>
          
          {/* Organization Filter Input */}
          <div className="mb-4">
            <input
              type="text"
              placeholder="Filter by Organization (e.g., Maintenance)..."
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={organizationFilter}
              onChange={(e) => setOrganizationFilter(e.target.value)}
            />
          </div>
          
          {isLoading ? (
            <div className="bg-gray-800 rounded-lg p-8 border border-gray-700 flex items-center justify-center">
              <svg className="animate-spin h-8 w-8 text-blue-500 mr-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span>Loading troubleshooting sessions...</span>
            </div>
          ) : error ? (
            <div className="bg-red-900/30 border border-red-700 rounded-md p-4 text-white">
              <p>{error}</p>
              <Button 
                variant="outline" 
                className="mt-4"
                onClick={() => window.location.reload()}
              >
                Try Again
              </Button>
            </div>
          ) : sessions.length === 0 ? (
            <TechnicianEmptyState
              title="No troubleshooting sessions found"
              description="Start a new session to troubleshoot a device or issue."
              icon={
                <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 mx-auto text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                </svg>
              }
              actionLabel="Start New Session"
              onAction={handleNewSession}
            />
          ) : getFilteredSessions().length === 0 ? (
            <TechnicianEmptyState
              title={`No ${filter} sessions found`}
              description="Try selecting a different filter or create a new session."
              secondaryActionLabel="View All Sessions"
              onSecondaryAction={() => setFilter('all')}
              actionLabel="Start New Session"
              onAction={handleNewSession}
            />
          ) : (
            <>
              
            <div className="grid gap-4 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-2">
              {getFilteredSessions().map((session) => (
                <div 
                  key={session.id} 
                  className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden hover:bg-gray-750 transition-colors cursor-pointer group"
                >
                  <div className="p-5" onClick={() => handleSessionClick(session.id)}>
                    <div className="flex justify-between items-start mb-3">
                      <h3 className="text-lg font-semibold truncate group-hover:text-blue-400 transition-colors">
                        {session.assignmentName}
                      </h3>
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${getStatusBadgeClass(session.status)}`}>
                        {session.status === 'new' ? 'New' : 
                         session.status === 'in-progress' ? 'In Progress' : 
                         session.status === 'completed' ? 'Completed' : 
                         'Archived'}
                      </span>
                    </div>
                    
                    {session.organization && (
                      <p className="text-sm text-gray-400 mb-2">
                        <span className="inline-block mr-1">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                          </svg>
                        </span>
                        {session.organization}
                      </p>
                    )}
                    
                    {session.assignmentLocation && (
                      <p className="text-sm text-gray-400 mb-2">
                        <span className="inline-block mr-1">
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                          </svg>
                        </span>
                        {session.assignmentLocation}
                      </p>
                    )}
                    
                    <p className="text-sm text-gray-300 mb-4 line-clamp-2">
                      {session.assignmentDescription}
                    </p>
                    
                    <div className="flex justify-between items-center text-xs text-gray-400">
                      <span>
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 inline mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                        Created: {formatDate(session.timestamp)}
                      </span>
                      <span>
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 inline mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        Updated: {formatDate(session.lastUpdated)}
                      </span>
                    </div>
                  </div>
                  
                  <div className="px-5 py-3 bg-gray-750 border-t border-gray-700 flex justify-between items-center">
                    <span className="text-sm text-gray-400">
                      Session #{session.id.substring(0, 6)}
                    </span>
                    <div className="flex items-center gap-4">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedSession(session);
                        }}
                        className="text-blue-400 text-sm hover:text-blue-300 flex items-center gap-1"
                        title="Update Status"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                        Status
                      </button>
                      <Button
                        variant="default"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleContinueSession(session.id);
                        }}
                        className="group-hover:underline"
                      >
                        Continue Session
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 inline ml-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            </>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="py-4 bg-gray-800 mt-auto border-t border-gray-700">
        <div className="container mx-auto px-4 text-center text-gray-400">
          <p>&copy; 2025 TechTalk. All rights reserved.</p>
        </div>
      </footer>
      
      {/* Status Update Menu */}
      {selectedSession && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-10" onClick={() => setSelectedSession(null)}>
          <div className="bg-gray-800 rounded-lg shadow-lg p-4 w-64" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-medium mb-3">Update Status</h3>
            <div className="mb-2 p-2 border border-gray-700 rounded-md bg-gray-900">
              <p className="text-sm text-gray-300 mb-1">Current status:</p>
              <div className="flex justify-between items-center">
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${getStatusBadgeClass(selectedSession.status)}`}>
                  {selectedSession.status === 'new' ? 'New' : 
                   selectedSession.status === 'in-progress' ? 'In Progress' : 
                   selectedSession.status === 'completed' ? 'Completed' : 
                   'Archived'}
                </span>
              </div>
            </div>
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-gray-300">Change to:</h4>
              <div className="grid grid-cols-1 gap-2">
                {selectedSession.status !== 'new' && (
                  <button 
                    className={`py-2 px-3 rounded-md border border-blue-700 bg-blue-900/30 text-blue-300 hover:bg-blue-900/50`}
                    onClick={() => handleStatusUpdate(selectedSession.id, 'new')}
                    disabled={updatingStatus}
                  >
                    Set as New
                  </button>
                )}
                {selectedSession.status !== 'in-progress' && (
                  <button 
                    className={`py-2 px-3 rounded-md border border-yellow-700 bg-yellow-900/30 text-yellow-300 hover:bg-yellow-900/50`}
                    onClick={() => handleStatusUpdate(selectedSession.id, 'in-progress')}
                    disabled={updatingStatus}
                  >
                    Mark In Progress
                  </button>
                )}
                {selectedSession.status !== 'completed' && (
                  <button 
                    className={`py-2 px-3 rounded-md border border-green-700 bg-green-900/30 text-green-300 hover:bg-green-900/50`}
                    onClick={() => handleStatusUpdate(selectedSession.id, 'completed')}
                    disabled={updatingStatus}
                  >
                    Mark as Completed
                  </button>
                )}
                {selectedSession.status !== 'archived' && (
                  <button 
                    className={`py-2 px-3 rounded-md border border-gray-700 bg-gray-800 text-gray-300 hover:bg-gray-700`}
                    onClick={() => handleStatusUpdate(selectedSession.id, 'archived')}
                    disabled={updatingStatus}
                  >
                    Archive Session
                  </button>
                )}
              </div>
            </div>
            {updatingStatus && (
              <div className="mt-3 flex justify-center">
                <svg className="animate-spin h-5 w-5 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              </div>
            )}
            <div className="mt-4 flex justify-end">
              <Button 
                variant="outline" 
                size="sm"
                onClick={() => setSelectedSession(null)}
                className="text-xs"
                disabled={updatingStatus}
              >
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}
      </div>
    </ProtectedRoute>
  );
}

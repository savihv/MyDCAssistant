import React from "react";
import { CTAButton } from "../components/CTAButton";
import { FeatureCard } from "../components/FeatureCard";
import { JuniorTechBotLogo } from "../components/JuniorTechBotLogo";
import { useNavigate, Link } from "react-router-dom";
import { useCurrentUser, firebaseAuth } from "../app";
import { useState } from "react";
import { useUserRoles } from "../utils/useUserRoles";
import { Button } from "../components/Button";
import { Card, CardHeader, CardTitle, CardDescription } from "../extensions/shadcn/components/card.tsx";

// Force router rebuild
export default function App() {
  const { user, loading } = useCurrentUser();
  const navigate = useNavigate();
  const { role, isSystemAdmin, isCompanyAdmin, loading: rolesLoading, debug } = useUserRoles();
  const [showDebug, setShowDebug] = useState(false);

  const handleGetStarted = () => {
  // Don't navigate if roles are still loading
  if (loading || rolesLoading) {
    console.log('Auth or roles still loading, delaying navigation');
    return;
  }
  
  if (user) {
    console.log('Navigating with role:', role, 'isSystemAdmin:', isSystemAdmin, 'isCompanyAdmin:', isCompanyAdmin);
    // Route users based on their role
    if (role === 'system_admin') {
      navigate("admin-settings"); // System Admins land on Admin Settings
    } else if (role === 'company_admin') {
      navigate("company-admin-dashboard"); // Direct navigation to CompanyAdminDashboard
    } else {
      // Default for technicians
      navigate("SessionCreate");
    }
  } else {
    navigate("Login"); // Relative path without leading slash
  }
};
  
  const handleSignUp = () => {
    navigate("Login?register=true"); // Relative path without leading slash
  };

  const handleSignIn = () => {
    navigate("Login"); // Relative path without leading slash
  };

  const handleSignOut = async () => {
    try {
      await firebaseAuth.signOut();
      navigate(""); // Relative path without leading slash (home)
    } catch (error) {
      console.error("Sign out error:", error);
    }
  };
  
  // Show loading placeholder while determining auth state
  if (loading || rolesLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="animate-pulse">
          <JuniorTechBotLogo className="w-16 h-16" />
        </div>
      </div>
    );
  }
  
  return (
    <div className="flex flex-col min-h-screen bg-gray-900 text-white">
      {/* Hero Section */}
      <header className="py-20 px-4">
        <div className="container mx-auto max-w-6xl">
          <div className="flex items-center justify-between mb-8">
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
                  <Link to="" className="text-blue-400">
                    Home
                  </Link>
                </li>
                {user ? (
                  <>
                    {/* Conditional rendering for navigation links */}
                    {!isCompanyAdmin && (
                      <>
                      <li>
                        <Link to="SessionCreate" className="text-gray-300 hover:text-white">
                          New Session
                        </Link>
                      </li>
                      <li>
                        <Link to="History" className="text-gray-300 hover:text-white">
                          History
                        </Link>
                      </li>
                      <li>
                        <Link to="KnowledgeBaseSearch" className="text-gray-300 hover:text-white">
                          Knowledge Base Search
                        </Link>
                      </li>
                      <li>
                        <Link to="ExpertSubmission" className="text-gray-300 hover:text-white">
                          Expert Submission
                        </Link>
                      </li>
                      <li>
                        <Link
                          to="MyReports"
                          className="text-gray-300 hover:text-white"
                        >
                          My Reports
                        </Link>
                      </li>
                      </>
                    )}
                    <li>
                      <button onClick={handleSignOut} className="text-gray-300 hover:text-white">
                        Sign Out
                      </button>
                    </li>
                    <li>
                      <button 
                        onClick={() => setShowDebug(!showDebug)} 
                        className="text-yellow-400 hover:text-yellow-300 font-semibold bg-gray-800 px-2 py-1 rounded"
                      >
                        🔧 Debug
                      </button>
                    </li>
                  </>
                ) : (
                  <>
                    <li>
                      <Link to="Login" className="text-gray-300 hover:text-white">
                        Sign In
                      </Link>
                    </li>
                    <li>
                      <Link to="Login?register=true" className="text-gray-300 hover:text-white">
                        Register
                      </Link>
                    </li>
                  </>
                )}
              </ul>
            </nav>
          </div>
          <div className="flex flex-col lg:flex-row items-center justify-between gap-10">
            {showDebug && user && (
              <div className="w-full mb-6 border-2 border-yellow-500 rounded-md p-4 bg-gray-800 text-white">
                <h3 className="text-xl font-bold text-yellow-400 mb-3">🔧 Debug Information</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  <div><strong>User Email:</strong> {user?.email || 'Not logged in'}</div>
                  <div><strong>User ID:</strong> {user?.uid || 'N/A'}</div>
                  <div><strong>Role:</strong> <span className="text-yellow-400 font-mono">{role}</span></div>
                  <div><strong>System Admin:</strong> <span className={isSystemAdmin ? 'text-green-400' : 'text-red-400'}>{isSystemAdmin ? 'Yes ✓' : 'No ✗'}</span></div>
                  <div><strong>Company Admin:</strong> <span className={isCompanyAdmin ? 'text-green-400' : 'text-red-400'}>{isCompanyAdmin ? 'Yes ✓' : 'No ✗'}</span></div>
                  <div><strong>Loading:</strong> {loading || rolesLoading ? 'Yes' : 'No'}</div>
                </div>
                
                <div className="mt-4 mb-2 text-yellow-400">* If role is incorrect, try force refreshing token:</div>
                <div className="flex space-x-2">
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="text-yellow-400 border-yellow-400 hover:bg-yellow-900" 
                    onClick={async () => {
                      if (user) {
                        try {
                          // Force token refresh
                          await user.getIdToken(true);
                          window.location.reload();
                        } catch (err) {
                          console.error('Error refreshing token:', err);
                        }
                      }
                    }}
                  >
                    Force Refresh Token
                  </Button>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="text-yellow-400 border-yellow-400 hover:bg-yellow-900" 
                    onClick={() => setShowDebug(false)}
                  >
                    Hide Debug Panel
                  </Button>
                </div>
                
                {/* Additional raw debug info */}
                <div className="mt-4 pt-4 border-t border-gray-700">
                  <details>
                    <summary className="cursor-pointer text-sm text-gray-400 hover:text-white">Show Raw Debug Info</summary>
                    <pre className="mt-2 p-2 bg-gray-900 rounded text-xs overflow-auto max-h-40 text-gray-400">
                      {JSON.stringify(debug, null, 2)}
                    </pre>
                  </details>
                </div>
              </div>
            )}
            
            <div className="lg:w-1/2">
              <h1 className="text-4xl md:text-5xl font-bold mb-6 text-blue-400">
                <span className="text-white">Junior</span>TechBot
                <JuniorTechBotLogo className="inline-block w-12 h-12 ml-2 align-middle" />
              </h1>
              <h2 className="text-3xl md:text-4xl font-bold mb-6">
                Voice-Powered Troubleshooting Assistant for Field Technicians
              </h2>
              <p className="text-lg text-gray-300 mb-8">
                Capture images and videos, use voice commands to describe issues, and receive instant
                troubleshooting guidance in both text and audio formats. JuniorTechBot is your hands-free
                expert assistant in the field.
              </p>
              {user ? (
                <div>
                  <p className="text-green-400 mb-4">
                    Welcome back, {user.displayName || user.email}!
                  </p>
                  <CTAButton 
                    className="text-lg px-8 py-3" 
                    onClick={handleGetStarted}
                    disabled={rolesLoading}
                  >
                    {rolesLoading ? (
                      <>
                        <span className="mr-2 inline-block h-4 w-4 animate-spin rounded-full border-2 border-solid border-current border-r-transparent align-[-0.125em]"></span>
                        Loading...
                      </>
                    ) : (
                      "Continue to App"
                    )}
                  </CTAButton>
                </div>
              ) : (
                <CTAButton className="text-lg px-8 py-3" onClick={handleGetStarted}>
                  Get Started
                </CTAButton>
              )}
            </div>
            <div className="lg:w-1/2">
              <div className="bg-gray-800 rounded-lg p-4 shadow-xl border border-gray-700">
                <div className="relative w-full pt-[56.25%] bg-gray-700 rounded">
                  <div className="absolute inset-0 flex items-center justify-center text-gray-500">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-32 w-32" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Features Section */}
      <section className="py-16 bg-gray-800 px-4">
        <div className="container mx-auto max-w-6xl">
          <h2 className="text-3xl font-bold text-center mb-12">How JuniorTechBot Works</h2>
          
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            <FeatureCard
              icon={<svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>}
              title="Capture Media"
              description="Take photos or videos of the equipment you're troubleshooting directly from your device."
            />
            
            <FeatureCard
              icon={<svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>}
              title="Voice Commands"
              description="Describe the issue or ask questions using natural voice commands while keeping your hands free."
            />
            
            <FeatureCard
              icon={<svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>}
              title="Instant Solutions"
              description="Receive expert troubleshooting guidance in both text and audio formats for easy reference."
            />
          </div>
        </div>
      </section>
      
      {/* CTA Section */}
      <section className="py-20 px-4">
        <div className="container mx-auto max-w-4xl text-center">
          <h2 className="text-3xl font-bold mb-6">Ready to streamline your field work?</h2>
          <p className="text-xl text-gray-300 mb-10 max-w-2xl mx-auto">
            Join JuniorTechBot today and experience hands-free technical assistance that saves time and reduces errors.
          </p>
          {user ? (
            <CTAButton 
              className="text-lg px-8 py-3" 
              onClick={() => {
                if (!rolesLoading) navigate('SessionCreate'); // Relative path without leading slash
              }}
              disabled={rolesLoading}
            >
              {rolesLoading ? (
                <>
                  <span className="mr-2 inline-block h-4 w-4 animate-spin rounded-full border-2 border-solid border-current border-r-transparent align-[-0.125em]"></span>
                  Loading...
                </>
              ) : (
                "Create New Session"
              )}
            </CTAButton>
          ) : (
            <div className="flex flex-col md:flex-row justify-center gap-4">
              <CTAButton className="text-lg px-8 py-3" onClick={handleSignUp}>
                Sign Up Now
              </CTAButton>
              <CTAButton className="text-lg px-8 py-3 bg-gray-700 hover:bg-gray-600" onClick={handleSignIn}>
                Sign In
              </CTAButton>
            </div>
          )}
        </div>
      </section>
      
      {/* Footer */}
      <footer className="py-8 bg-gray-800 mt-auto">
        <div className="container mx-auto px-4 text-center text-gray-400">
          <p>© 2025 JuniorTechBot. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}

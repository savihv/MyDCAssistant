import React from "react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCurrentUser } from "../app";
import { useUserRoles } from "../utils/useUserRoles";
import { Button } from "../components/Button";
import { Spinner } from "../components/Spinner";
import { Tabs, TabsList, TabsTrigger } from "../extensions/shadcn/components/tabs";
import { HomeIcon, FileTextIcon, UserIcon, ShieldAlertIcon, SettingsIcon, CheckCircleIcon } from "lucide-react";

interface Props {
  children: React.ReactNode;
  activeTab: string;
}

/**
 * Layout component for admin pages
 * Provides consistent navigation and styling
 */
export function AdminLayoutFixed({ children, activeTab }: Props) {
  const { user, loading: userLoading } = useCurrentUser();
  const { role, isSystemAdmin, isCompanyAdmin, loading: rolesLoading, debug } = useUserRoles();
  const navigate = useNavigate();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [showDebug, setShowDebug] = useState(false);
  
  // Loading state combines user and roles loading
  const loading = userLoading || rolesLoading;

  // Debug output when component renders
  console.log('AdminLayout rendering with:', { 
    user: user?.email, 
    role, 
    isSystemAdmin, 
    isCompanyAdmin,
    debug
  });

  // Handle tab change - use relative paths for base path compatibility
  const handleTabChange = (value: string) => {
    switch (value) {
      case "documents":
        navigate("admin-documents");
        break;
      case "moderation":
        navigate("admin-moderation");
        break;
      case "users":
        navigate("admin-users");
        break;
      case "approval":
        navigate("admin-approval");
        break;
      case "settings":
        navigate(isSystemAdmin ? "admin-system" : "admin-settings");
        break;
      case "system":
        navigate("admin-system");
        break;
      case "dashboard":
      default:
        navigate("admin-dashboard");
        break;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Admin Header */}
      <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-14 max-w-screen-2xl items-center">
          <div className="mr-4 flex">
            <Button variant="ghost" className="mr-2" onClick={() => navigate("")}>  
              <span className="font-bold text-lg">TechTalk</span>
              <span className="ml-2 text-xs bg-primary text-primary-foreground px-1.5 py-0.5 rounded-md">
                Admin
              </span>
            </Button>
          </div>
          
          {/* Main Navigation */}
          <div className="flex flex-1 items-center justify-between space-x-2 md:justify-end">
            <div className="w-full flex-1 md:w-auto md:flex-none">
              <Tabs 
                defaultValue={activeTab} 
                value={activeTab}
                onValueChange={handleTabChange}
                className="w-full"
              >
                <TabsList className="grid w-full grid-cols-3 md:grid-cols-6 lg:w-auto">
                  <TabsTrigger value="dashboard">
                    <HomeIcon className="h-4 w-4 mr-2" />
                    Dashboard
                  </TabsTrigger>
                  <TabsTrigger value="documents">
                    <FileTextIcon className="h-4 w-4 mr-2" />
                    Documents
                  </TabsTrigger>
                  {isSystemAdmin && (
                    <TabsTrigger value="users">
                      <UserIcon className="h-4 w-4 mr-2" />
                      Users
                    </TabsTrigger>
                  )}
                  {(isSystemAdmin || isCompanyAdmin) && (
                    <TabsTrigger value="approval">
                      <CheckCircleIcon className="h-4 w-4 mr-2" />
                      Approvals
                    </TabsTrigger>
                  )}
                  <TabsTrigger value="moderation">
                    <ShieldAlertIcon className="h-4 w-4 mr-2" />
                    Moderation
                  </TabsTrigger>
                  <TabsTrigger value="settings">
                    <SettingsIcon className="h-4 w-4 mr-2" />
                    Settings
                  </TabsTrigger>
                  {isSystemAdmin && (
                    <TabsTrigger value="system">
                      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4 mr-2">
                        <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>
                        <path d="M13.8 13.8A6 6 0 0 0 18 7.2"/>
                      </svg>
                      System
                    </TabsTrigger>
                  )}
                </TabsList>
              </Tabs>
            </div>

            <div className="flex items-center">
              {user && (
                <div className="flex items-center gap-4">
                  <span className="text-sm hidden md:inline-block">
                    {user.email}
                  </span>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    onClick={() => navigate("")}
                  >
                    Exit Admin
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container max-w-screen-2xl py-6">
        {/* Debug Panel */}
        <div className="mb-4 border-2 border-amber-500 rounded-md p-2">
          <Button 
            variant="outline" 
            size="sm" 
            className="text-sm text-amber-500 hover:text-amber-400 font-bold" 
            onClick={() => setShowDebug(!showDebug)}
          >
            {showDebug ? "Hide Debug Info" : "📊 SHOW DEBUG INFO"}
          </Button>
          
          {showDebug && (
            <div className="mt-2 rounded-md bg-muted p-3 text-xs text-muted-foreground">
              <div><strong>User:</strong> {user?.email || 'Not logged in'}</div>
              <div><strong>Role:</strong> {role}</div>
              <div><strong>System Admin:</strong> {isSystemAdmin ? 'Yes' : 'No'}</div>
              <div><strong>Company Admin:</strong> {isCompanyAdmin ? 'Yes' : 'No'}</div>
              <div><strong>Loading:</strong> {loading ? 'Yes' : 'No'}</div>
              <div className="mt-2 text-amber-400">* If role is incorrect, try force refreshing token:</div>
              <Button 
                variant="outline" 
                size="sm" 
                className="mt-1 h-6 text-xs text-amber-400" 
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
            </div>
          )}
        </div>
        
        {children}
      </main>
    </div>
  );
}
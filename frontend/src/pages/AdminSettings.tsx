import React from "react";
import { useState, useEffect } from "react";
import { firebaseApp } from "../app";
import { useUserRoles } from "../utils/useUserRoles";
import { getFirestore, doc, getDoc, updateDoc, setDoc } from "firebase/firestore";
import { AdminGuard } from "../components/AdminGuard";
import { AdminLayout } from "../components/AdminLayout";
import { Button } from "../components/Button";
import { Label } from "../extensions/shadcn/components/label";
import { Input } from "../extensions/shadcn/components/input";
import { Switch } from "../extensions/shadcn/components/switch";
import { Textarea } from "../extensions/shadcn/components/textarea";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "../extensions/shadcn/components/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../extensions/shadcn/components/select";
import { Spinner } from "../components/Spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../extensions/shadcn/components/tabs";
import { toast } from "sonner";

interface SystemSettings {
  webSearch: {
    enabled: boolean;
    includeSources: boolean;
    maxResults: number;
    preferredSources: string[];
    blockedSources: string[];
  };
  
  contentModeration: {
    enabled: boolean;
    autoApprove: boolean;
    thresholds: {
      adult: number;
      violence: number;
      medical: number;
      racy: number;
      spoofed: number;
    };
  };
  vectorDatabase: {
    provider: string;
    apiKey?: string;
    indexName: string;
    dimensions: number;
  };
  ragSettings: {
    enabled: boolean;
    maxResults: number;
    scoreThreshold: number;
    includeSources: boolean;
  };
  namespaceConfiguration?: {
    enabled: boolean;
    intents?: Array<{
      id: string;
      displayName: string;
      description?: string;
      keywords?: string[];
    }>;
    namespaces: Array<{
      id: string;
      displayName: string;
      isDefault: boolean;
      intents: string[];
    }>;
  };
}

export default function AdminSettings() {
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [pageLoading, setPageLoading] = useState(true); // Renamed to avoid conflict
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<string>("general");
  
  const { 
    role,
    isSystemAdmin,
    company,
    loading: userRolesLoading 
  } = useUserRoles();
  const db = getFirestore(firebaseApp);

  // Fetch settings on load
  useEffect(() => {
    if (userRolesLoading || !role) {
      setPageLoading(userRolesLoading); // Keep page loading if roles are loading
      return;
    }
    
    const fetchSettings = async () => {
      setPageLoading(true);
      let settingsPath: string | null = null;

      if (isSystemAdmin) {
        settingsPath = 'settings/system_defaults';
      } else if (role === 'company_admin') {
        if (company) {
          settingsPath = `settings/${company}`; // Corrected path for fetching
        } else {
          console.error("Error: Company ID is missing for company admin.");
          toast.error("Failed to load settings: Company information missing for your account.");
          setPageLoading(false);
          return;
        }
      } else {
        console.error(`Error: User with role '${role}' is not authorized to view settings.`);
        toast.error("Unauthorized to view settings.");
        setPageLoading(false);
        return;
      }
        
      // This check is now more specific. If settingsPath is null here, it's an unhandled role or state.
      if (!settingsPath) {
          console.error("Error: Could not determine settings path due to unexpected role or state.");
          toast.error("Failed to load settings: Configuration error.");
          setPageLoading(false);
          return;
      }
        
      try {
        const settingsDoc = await getDoc(doc(db, settingsPath));
        
        if (settingsDoc.exists()) {
          setSettings(settingsDoc.data() as SystemSettings);
        } else {
          // Initialize with defaults if not found
          const defaultSettings: SystemSettings = {
            contentModeration: {
              enabled: true,
              autoApprove: false,
              thresholds: {
                adult: 0.7,
                violence: 0.7,
                medical: 0.8,
                racy: 0.7,
                spoofed: 0.8,
              },
            },
            vectorDatabase: {
              provider: 'pinecone',
              indexName: 'techtalk-documents',
              dimensions: 1536, // OpenAI embedding dimensions
            },
            ragSettings: {
              enabled: true,
              maxResults: 3,
              scoreThreshold: 0.7,
              includeSources: true,
            },
            webSearch: {
              enabled: true,
              includeSources: true,
              maxResults: 3,
              preferredSources: [],
              blockedSources: [],
            },
          };
          
          setSettings(defaultSettings);
          
          // Save defaults to database
          // Ensure company is not literally 'null' string if that's a possibility from claims
          if (settingsPath && (isSystemAdmin || (role === 'company_admin' && company && company !== "null"))) { 
            await setDoc(doc(db, settingsPath), defaultSettings);
          }
        }
      } catch (error) {
        console.error("Error fetching settings:", error);
        toast.error(`Failed to load settings from ${settingsPath}`);
      } finally {
        setPageLoading(false);
      }
    };
    
    fetchSettings();
  }, [db, role, company, isSystemAdmin, userRolesLoading]);

  // Update a setting value
  const updateSetting = (path: string, value: any) => {
    if (!settings) return;
    
    // Create a copy of the settings object
    const newSettings = { ...settings };
    
    // Split path into parts and update the nested property
    const pathParts = path.split('.');
    let current: any = newSettings;
    
    for (let i = 0; i < pathParts.length - 1; i++) {
      current = current[pathParts[i]];
    }
    
    current[pathParts[pathParts.length - 1]] = value;
    
    // Update state
    setSettings(newSettings);
  };

  // Save settings to Firestore
  const saveSettings = async () => {
    if (!settings || userRolesLoading || !role) {
      toast.error("Cannot save settings: User information not fully loaded.");
      return;
    }
    
    setSaving(true);
    let settingsPath: string | null = null;

    if (isSystemAdmin) {
      settingsPath = 'settings/system_defaults';
    } else if (role === 'company_admin') {
      if (company) {
        settingsPath = `settings/${company}`; // Corrected path
      } else {
        console.error("Error saving settings: Company ID is missing for company admin.");
        toast.error("Failed to save settings: Company information missing for your account.");
        setSaving(false);
        return;
      }
    } else {
      console.error(`Error saving settings: User with role '${role}' is not authorized.`);
      toast.error("Unauthorized to save settings.");
      setSaving(false);
      return;
    }

    if (!settingsPath) {
      console.error("Error saving settings: Could not determine settings path.");
      toast.error("Failed to save settings: Configuration error.");
      setSaving(false);
      return;
    }
      
    try {
      await updateDoc(doc(db, settingsPath), settings as any); // Cast to any to satisfy updateDoc, data structure is validated by SystemSettings interface
      
      toast.success("Settings saved successfully");
    } catch (error) {
      console.error("Error saving settings:", error);
      toast.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  // Display loading spinner if user roles are loading or page is still processing settings
  if (userRolesLoading || pageLoading) {
    return (
      <AdminGuard>
        <AdminLayout activeTab="settings">
          <div className="flex justify-center items-center h-64">
            <Spinner size="lg" />
          </div>
        </AdminLayout>
      </AdminGuard>
    );
  }

  // If settings are null after loading (e.g. due to an error handled in fetchSettings like missing companyId)
  if (!settings) {
    return (
      <AdminGuard>
        <AdminLayout activeTab="settings">
          <div className="p-4 text-center">
            <p className="text-red-500">Could not load settings. Please check console for errors or contact support.</p>
            {/* Optionally, provide a retry button or more specific guidance based on error state if available */}
          </div>
        </AdminLayout>
      </AdminGuard>
    );
  }

  return (
    <AdminGuard>
      <AdminLayout activeTab="settings">
        <div className="flex flex-col gap-6">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
            <p className="text-muted-foreground">
              {isSystemAdmin 
                ? 'Configure system-wide settings'
                : 'Configure company-specific settings'}
            </p>
          </div>
          
          <Tabs
            defaultValue="general"
            value={activeTab}
            onValueChange={setActiveTab}
            className="space-y-4"
          >
            <TabsList>
              <TabsTrigger value="general">General</TabsTrigger>
              <TabsTrigger value="content-moderation">Content Moderation</TabsTrigger>
              {isSystemAdmin && (
                <TabsTrigger value="vector-db">Vector Database</TabsTrigger>
              )}
              <TabsTrigger value="rag">RAG Settings</TabsTrigger>
              <TabsTrigger value="web-search">Web Search</TabsTrigger>
              <TabsTrigger value="namespaces">Namespaces</TabsTrigger>
            </TabsList>
            
            {/* General Settings */}
            <TabsContent value="general" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>General Settings</CardTitle>
                  <CardDescription>
                    Basic configuration for your knowledge base
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label>Enable RAG System</Label>
                      <p className="text-sm text-muted-foreground">
                        Toggle the retrieval augmented generation system
                      </p>
                    </div>
                    <Switch
                      checked={settings.ragSettings.enabled}
                      onCheckedChange={(checked) => updateSetting('ragSettings.enabled', checked)}
                    />
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label>Enable Web Search</Label>
                      <p className="text-sm text-muted-foreground">
                        Allow searching external websites for troubleshooting information
                      </p>
                    </div>
                    <Switch
                      checked={settings.webSearch.enabled}
                      onCheckedChange={(checked) => updateSetting('webSearch.enabled', checked)}
                    />
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label>Content Moderation</Label>
                      <p className="text-sm text-muted-foreground">
                        Enable content screening for all uploads
                      </p>
                    </div>
                    <Switch
                      checked={settings.contentModeration.enabled}
                      onCheckedChange={(checked) => updateSetting('contentModeration.enabled', checked)}
                    />
                  </div>
                </CardContent>
                <CardFooter>
                  <Button onClick={saveSettings} disabled={saving}>
                    {saving ? <><Spinner className="mr-2" size="sm" /> Saving...</> : 'Save Changes'}
                  </Button>
                </CardFooter>
              </Card>
            </TabsContent>
            
            {/* Content Moderation Settings */}
            <TabsContent value="content-moderation" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Content Moderation Settings</CardTitle>
                  <CardDescription>
                    Configure how uploads are screened and moderated
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label>Auto-approve Safe Content</Label>
                      <p className="text-sm text-muted-foreground">
                        Automatically approve content that passes moderation thresholds
                      </p>
                    </div>
                    <Switch
                      checked={settings.contentModeration.autoApprove}
                      onCheckedChange={(checked) => updateSetting('contentModeration.autoApprove', checked)}
                    />
                  </div>
                  
                  <div className="space-y-3 border-t pt-3">
                    <h3 className="text-sm font-medium">Moderation Thresholds</h3>
                    <p className="text-sm text-muted-foreground">Content exceeding these values will be flagged</p>
                    
                    <div className="grid gap-4">
                      <div className="grid gap-2">
                        <div className="flex items-center justify-between">
                          <Label htmlFor="adult-threshold">Adult Content</Label>
                          <span className="text-sm">{settings.contentModeration.thresholds.adult * 100}%</span>
                        </div>
                        <Input
                          id="adult-threshold"
                          type="range"
                          min="0"
                          max="1"
                          step="0.05"
                          value={settings.contentModeration.thresholds.adult}
                          onChange={(e) => updateSetting('contentModeration.thresholds.adult', parseFloat(e.target.value))}
                        />
                      </div>
                      
                      <div className="grid gap-2">
                        <div className="flex items-center justify-between">
                          <Label htmlFor="violence-threshold">Violence</Label>
                          <span className="text-sm">{settings.contentModeration.thresholds.violence * 100}%</span>
                        </div>
                        <Input
                          id="violence-threshold"
                          type="range"
                          min="0"
                          max="1"
                          step="0.05"
                          value={settings.contentModeration.thresholds.violence}
                          onChange={(e) => updateSetting('contentModeration.thresholds.violence', parseFloat(e.target.value))}
                        />
                      </div>
                      
                      <div className="grid gap-2">
                        <div className="flex items-center justify-between">
                          <Label htmlFor="medical-threshold">Medical Content</Label>
                          <span className="text-sm">{settings.contentModeration.thresholds.medical * 100}%</span>
                        </div>
                        <Input
                          id="medical-threshold"
                          type="range"
                          min="0"
                          max="1"
                          step="0.05"
                          value={settings.contentModeration.thresholds.medical}
                          onChange={(e) => updateSetting('contentModeration.thresholds.medical', parseFloat(e.target.value))}
                        />
                      </div>
                      
                      <div className="grid gap-2">
                        <div className="flex items-center justify-between">
                          <Label htmlFor="racy-threshold">Racy Content</Label>
                          <span className="text-sm">{settings.contentModeration.thresholds.racy * 100}%</span>
                        </div>
                        <Input
                          id="racy-threshold"
                          type="range"
                          min="0"
                          max="1"
                          step="0.05"
                          value={settings.contentModeration.thresholds.racy}
                          onChange={(e) => updateSetting('contentModeration.thresholds.racy', parseFloat(e.target.value))}
                        />
                      </div>
                      
                      <div className="grid gap-2">
                        <div className="flex items-center justify-between">
                          <Label htmlFor="spoofed-threshold">Spoofed/Fake Content</Label>
                          <span className="text-sm">{settings.contentModeration.thresholds.spoofed * 100}%</span>
                        </div>
                        <Input
                          id="spoofed-threshold"
                          type="range"
                          min="0"
                          max="1"
                          step="0.05"
                          value={settings.contentModeration.thresholds.spoofed}
                          onChange={(e) => updateSetting('contentModeration.thresholds.spoofed', parseFloat(e.target.value))}
                        />
                      </div>
                    </div>
                  </div>
                </CardContent>
                <CardFooter>
                  <Button onClick={saveSettings} disabled={saving}>
                    {saving ? <><Spinner className="mr-2" size="sm" /> Saving...</> : 'Save Changes'}
                  </Button>
                </CardFooter>
              </Card>
            </TabsContent>
            
            {/* Vector Database Settings (System Admin Only) */}
            {isSystemAdmin && (
              <TabsContent value="vector-db" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Vector Database Configuration</CardTitle>
                    <CardDescription>
                      Configure vector database settings for document embeddings
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid gap-2">
                      <Label htmlFor="vector-provider">Vector Database Provider</Label>
                      <Select
                        value={settings.vectorDatabase.provider}
                        onValueChange={(value) => updateSetting('vectorDatabase.provider', value)}
                      >
                        <SelectTrigger id="vector-provider">
                          <SelectValue placeholder="Select provider" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="pinecone">Pinecone</SelectItem>
                          <SelectItem value="weaviate">Weaviate</SelectItem>
                          <SelectItem value="qdrant">Qdrant</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    
                    <div className="grid gap-2">
                      <Label htmlFor="index-name">Index Name</Label>
                      <Input
                        id="index-name"
                        value={settings.vectorDatabase.indexName}
                        onChange={(e) => updateSetting('vectorDatabase.indexName', e.target.value)}
                      />
                    </div>
                    
                    <div className="grid gap-2">
                      <Label htmlFor="dimensions">Vector Dimensions</Label>
                      <Input
                        id="dimensions"
                        type="number"
                        value={settings.vectorDatabase.dimensions}
                        onChange={(e) => updateSetting('vectorDatabase.dimensions', parseInt(e.target.value))}
                      />
                      <p className="text-xs text-muted-foreground">
                        OpenAI embeddings use 1536 dimensions, Gemini uses 768
                      </p>
                    </div>
                  </CardContent>
                  <CardFooter>
                    <Button onClick={saveSettings} disabled={saving}>
                      {saving ? <><Spinner className="mr-2" size="sm" /> Saving...</> : 'Save Changes'}
                    </Button>
                  </CardFooter>
                </Card>
              </TabsContent>
            )}
            
            {/* RAG Settings */}
            <TabsContent value="rag" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>RAG System Settings</CardTitle>
                  <CardDescription>
                    Configure retrieval augmented generation behavior
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-2">
                    <Label htmlFor="max-results">Maximum Results</Label>
                    <Input
                      id="max-results"
                      type="number"
                      value={settings.ragSettings.maxResults}
                      onChange={(e) => updateSetting('ragSettings.maxResults', parseInt(e.target.value))}
                    />
                    <p className="text-xs text-muted-foreground">
                      Maximum number of document chunks to retrieve per query
                    </p>
                  </div>
                  
                  <div className="grid gap-2">
                    <Label htmlFor="score-threshold">Similarity Threshold</Label>
                    <div className="flex items-center gap-2">
                      <Input
                        id="score-threshold"
                        type="range"
                        min="0"
                        max="1"
                        step="0.05"
                        value={settings.ragSettings.scoreThreshold}
                        onChange={(e) => updateSetting('ragSettings.scoreThreshold', parseFloat(e.target.value))}
                      />
                      <span className="text-sm w-12">{settings.ragSettings.scoreThreshold * 100}%</span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Minimum similarity score for retrieved documents
                    </p>
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label>Include Source Attribution</Label>
                      <p className="text-sm text-muted-foreground">
                        Include document sources in AI responses
                      </p>
                    </div>
                    <Switch
                      checked={settings.ragSettings.includeSources}
                      onCheckedChange={(checked) => updateSetting('ragSettings.includeSources', checked)}
                    />
                  </div>
                </CardContent>
                <CardFooter>
                  <Button onClick={saveSettings} disabled={saving}>
                    {saving ? <><Spinner className="mr-2" size="sm" /> Saving...</> : 'Save Changes'}
                  </Button>
                </CardFooter>
              </Card>
            </TabsContent>
            
            {/* Web Search Settings */}
            <TabsContent value="web-search" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Web Search Settings</CardTitle>
                  <CardDescription>
                    Configure how the system searches for community knowledge
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label>Enable Web Search</Label>
                      <p className="text-sm text-muted-foreground">
                        Allow searching web forums and technical communities for answers
                      </p>
                    </div>
                    <Switch
                      checked={settings.webSearch.enabled}
                      onCheckedChange={(checked) => updateSetting('webSearch.enabled', checked)}
                    />
                  </div>
                  
                  <div className="grid gap-2">
                    <Label htmlFor="web-max-results">Maximum Results</Label>
                    <Input
                      id="web-max-results"
                      type="number"
                      value={settings.webSearch.maxResults}
                      onChange={(e) => updateSetting('webSearch.maxResults', parseInt(e.target.value))}
                    />
                    <p className="text-xs text-muted-foreground">
                      Maximum number of web results to include per query
                    </p>
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                      <Label>Include Source Attribution</Label>
                      <p className="text-sm text-muted-foreground">
                        Include web sources in AI responses
                      </p>
                    </div>
                    <Switch
                      checked={settings.webSearch.includeSources}
                      onCheckedChange={(checked) => updateSetting('webSearch.includeSources', checked)}
                    />
                  </div>
                  
                  <div className="grid gap-2">
                    <Label htmlFor="preferred-sources">Preferred Sources</Label>
                    <Textarea
                      id="preferred-sources"
                      placeholder="stackoverflow.com\nreddit.com/r/techsupport\ndocs.example.com"
                      value={settings.webSearch.preferredSources.join('\n')}
                      onChange={(e) => updateSetting('webSearch.preferredSources', e.target.value.split('\n').filter(Boolean))}
                      className="min-h-[100px]"
                    />
                    <p className="text-xs text-muted-foreground">
                      Enter one domain per line. These sources will be prioritized in search results.
                    </p>
                  </div>
                  
                  <div className="grid gap-2">
                    <Label htmlFor="blocked-sources">Blocked Sources</Label>
                    <Textarea
                      id="blocked-sources"
                      placeholder="example-spam.com\nbadinfo.net"
                      value={settings.webSearch.blockedSources.join('\n')}
                      onChange={(e) => updateSetting('webSearch.blockedSources', e.target.value.split('\n').filter(Boolean))}
                      className="min-h-[100px]"
                    />
                    <p className="text-xs text-muted-foreground">
                      Enter one domain per line. These sources will be excluded from search results.
                    </p>
                  </div>
                </CardContent>
                <CardFooter>
                  <Button onClick={saveSettings} disabled={saving}>
                    {saving ? <><Spinner className="mr-2" size="sm" /> Saving...</> : 'Save Changes'}
                  </Button>
                </CardFooter>
              </Card>
            </TabsContent>
            
            {/* Namespace Configuration */}
            <TabsContent value="namespaces" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Namespace Configuration</CardTitle>
                  <CardDescription>
                    Configure custom namespaces and their intent mappings for knowledge base organization
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="flex items-center justify-between pb-4 border-b">
                    <div className="space-y-0.5">
                      <Label>Enable Custom Namespaces</Label>
                      <p className="text-sm text-muted-foreground">
                        Use custom namespace configuration instead of defaults
                      </p>
                    </div>
                    <Switch
                      checked={settings.namespaceConfiguration?.enabled || false}
                      onCheckedChange={(checked) => {
                        const defaultIntents = [
                          { id: 'general', displayName: 'General', description: 'General knowledge and documentation', keywords: [] },
                          { id: 'baseline_comparison', displayName: 'Baseline Comparison', description: 'Standard guidelines and procedures', keywords: ['compare', 'baseline', 'standard', 'correct', 'normal', 'should be', 'supposed to'] },
                          { id: 'historic', displayName: 'Historic', description: 'Historical records and cases', keywords: ['last time', 'previous', 'history', 'before', 'past', 'how did we fix'] },
                          { id: 'expert', displayName: 'Expert', description: 'Expert tips and insights', keywords: ['expert', 'tip', 'best practice', 'recommendation', 'field'] },
                        ];
                        const defaultNamespaces = [
                          { id: 'general', displayName: 'General Knowledge', isDefault: true, intents: ['general'] },
                          { id: 'baseline', displayName: 'Standard Guidelines', isDefault: false, intents: ['baseline_comparison'] },
                          { id: 'expert', displayName: 'Expert Knowledge', isDefault: false, intents: ['expert'] },
                          { id: 'historic', displayName: 'Historic Records', isDefault: false, intents: ['historic'] },
                        ];
                        updateSetting('namespaceConfiguration', {
                          enabled: checked,
                          intents: settings.namespaceConfiguration?.intents || defaultIntents,
                          namespaces: settings.namespaceConfiguration?.namespaces || defaultNamespaces
                        });
                      }}
                    />
                  </div>

                  {settings.namespaceConfiguration?.enabled && (
                    <div className="space-y-4">
                      {/* Intent Management Section */}
                      <div className="space-y-4 pb-6 border-b">
                        <div className="flex items-center justify-between">
                          <div>
                            <h3 className="text-sm font-medium">Custom Intents</h3>
                            <p className="text-xs text-muted-foreground mt-1">
                              Define the intents that will be used to route queries to namespaces
                            </p>
                          </div>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              const newIntent = {
                                id: `intent_${Date.now()}`,
                                displayName: 'New Intent',
                                description: ''
                              };
                              const updatedIntents = [
                                ...(settings.namespaceConfiguration?.intents || []),
                                newIntent
                              ];
                              updateSetting('namespaceConfiguration.intents', updatedIntents);
                            }}
                          >
                            Add Intent
                          </Button>
                        </div>

                        <div className="space-y-2">
                          {(settings.namespaceConfiguration.intents || []).map((intent, index) => (
                            <Card key={intent.id} className="p-3">
                              <div className="flex items-start gap-3">
                                <div className="flex-1 grid gap-2">
                                  <div className="grid grid-cols-2 gap-3">
                                    <div className="grid gap-1.5">
                                      <Label htmlFor={`intent-id-${index}`} className="text-xs">Intent ID</Label>
                                      <Input
                                        id={`intent-id-${index}`}
                                        value={intent.id}
                                        onChange={(e) => {
                                          const updated = [...settings.namespaceConfiguration!.intents!];
                                          updated[index] = { ...intent, id: e.target.value };
                                          updateSetting('namespaceConfiguration.intents', updated);
                                        }}
                                        placeholder="e.g., taxonomy, market_data"
                                        className="h-8"
                                      />
                                    </div>
                                    <div className="grid gap-1.5">
                                      <Label htmlFor={`intent-name-${index}`} className="text-xs">Display Name</Label>
                                      <Input
                                        id={`intent-name-${index}`}
                                        value={intent.displayName}
                                        onChange={(e) => {
                                          const updated = [...settings.namespaceConfiguration!.intents!];
                                          updated[index] = { ...intent, displayName: e.target.value };
                                          updateSetting('namespaceConfiguration.intents', updated);
                                        }}
                                        placeholder="e.g., Taxonomy"
                                        className="h-8"
                                      />
                                    </div>
                                  </div>
                                  <div className="grid gap-1.5">
                                    <Label htmlFor={`intent-desc-${index}`} className="text-xs">Description</Label>
                                    <Input
                                      id={`intent-desc-${index}`}
                                      value={intent.description || ''}
                                      onChange={(e) => {
                                        const updated = [...settings.namespaceConfiguration!.intents!];
                                        updated[index] = { ...intent, description: e.target.value };
                                        updateSetting('namespaceConfiguration.intents', updated);
                                      }}
                                      placeholder="e.g., Master ontology for domain classification"
                                      className="h-8"
                                    />
                                  </div>
                                  <div className="grid gap-1.5">
                                    <Label htmlFor={`intent-keywords-${index}`} className="text-xs">Keywords (comma-separated)</Label>
                                    <Input
                                      id={`intent-keywords-${index}`}
                                      value={(intent.keywords || []).join(', ')}
                                      onChange={(e) => {
                                        const updated = [...settings.namespaceConfiguration!.intents!];
                                        const keywords = e.target.value.split(',').map(k => k.trim()).filter(k => k.length > 0);
                                        updated[index] = { ...intent, keywords };
                                        updateSetting('namespaceConfiguration.intents', updated);
                                      }}
                                      placeholder="e.g., taxonomy, classify, category, type"
                                      className="h-8"
                                    />
                                    <p className="text-xs text-muted-foreground">Optional: Fast keyword matching for this intent</p>
                                  </div>
                                </div>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => {
                                    const updated = settings.namespaceConfiguration!.intents!.filter((_, i) => i !== index);
                                    updateSetting('namespaceConfiguration.intents', updated);
                                  }}
                                  className="h-8"
                                >
                                  Delete
                                </Button>
                              </div>
                            </Card>
                          ))}
                          {(!settings.namespaceConfiguration.intents || settings.namespaceConfiguration.intents.length === 0) && (
                            <div className="text-center py-6 text-muted-foreground">
                              No custom intents defined. Add an intent to get started.
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Namespace Management Section */}
                      <div className="flex items-center justify-between">
                        <h3 className="text-sm font-medium">Configured Namespaces</h3>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            const existingNamespaces = settings.namespaceConfiguration?.namespaces || [];
                            const newNamespace = {
                              id: `custom_${Date.now()}`,
                              displayName: 'New Namespace',
                              isDefault: existingNamespaces.length === 0, // First namespace is default
                              intents: []
                            };
                            const updatedNamespaces = [
                              ...existingNamespaces,
                              newNamespace
                            ];
                            updateSetting('namespaceConfiguration.namespaces', updatedNamespaces);
                          }}
                        >
                          Add Namespace
                        </Button>
                      </div>

                      <div className="space-y-3">
                        {settings.namespaceConfiguration.namespaces.map((namespace, index) => {
                          const setDefaultNamespace = (namespaceId: string) => {
                            const updatedNamespaces = (settings.namespaceConfiguration?.namespaces || []).map(ns => ({
                              ...ns,
                              isDefault: ns.id === namespaceId
                            }));
                            updateSetting('namespaceConfiguration.namespaces', updatedNamespaces);
                          };

                          return (
                            <Card key={namespace.id} className="p-4">
                              <div className="space-y-3">
                                <div className="flex items-start justify-between gap-4">
                                  <div className="flex-1 grid gap-3">
                                    <div className="grid gap-2">
                                      <Label htmlFor={`ns-id-${index}`}>Namespace ID</Label>
                                      <Input
                                        id={`ns-id-${index}`}
                                        value={namespace.id}
                                        onChange={(e) => {
                                          const updated = [...settings.namespaceConfiguration!.namespaces];
                                          updated[index] = { ...namespace, id: e.target.value };
                                          updateSetting('namespaceConfiguration.namespaces', updated);
                                        }}
                                        placeholder="e.g., general, baseline, expert"
                                      />
                                    </div>
                                    <div className="grid gap-2">
                                      <Label htmlFor={`ns-name-${index}`}>Display Name</Label>
                                      <Input
                                        id={`ns-name-${index}`}
                                        value={namespace.displayName}
                                        onChange={(e) => {
                                          const updated = [...settings.namespaceConfiguration!.namespaces];
                                          updated[index] = { ...namespace, displayName: e.target.value };
                                          updateSetting('namespaceConfiguration.namespaces', updated);
                                        }}
                                        placeholder="e.g., General Knowledge"
                                      />
                                    </div>
                                    <div className="flex items-center gap-2">
                                      <input
                                        type="radio"
                                        id={`ns-default-${index}`}
                                        name="defaultNamespace"
                                        checked={namespace.isDefault || false}
                                        onChange={() => setDefaultNamespace(namespace.id)}
                                        className="h-4 w-4"
                                      />
                                      <Label htmlFor={`ns-default-${index}`} className="text-sm cursor-pointer">
                                        Set as Default
                                      </Label>
                                    </div>
                                  </div>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => {
                                      const updated = settings.namespaceConfiguration!.namespaces.filter((_, i) => i !== index);
                                      updateSetting('namespaceConfiguration.namespaces', updated);
                                    }}
                                    disabled={settings.namespaceConfiguration!.namespaces.length === 1}
                                  >
                                    Delete
                                  </Button>
                                </div>

                                <div className="space-y-2">
                                  <Label>Intent Mappings</Label>
                                  <p className="text-xs text-muted-foreground">
                                    Select which intents will search this namespace
                                  </p>
                                  <div className="grid grid-cols-2 gap-2 mt-2">
                                    {(settings.namespaceConfiguration?.intents || []).map((intent) => (
                                      <div key={intent.id} className="flex items-center space-x-2">
                                        <input
                                          type="checkbox"
                                          id={`ns-${index}-intent-${intent.id}`}
                                          checked={namespace.intents.includes(intent.id)}
                                          onChange={(e) => {
                                            const updated = [...settings.namespaceConfiguration!.namespaces];
                                            const intents = e.target.checked
                                              ? [...namespace.intents, intent.id]
                                              : namespace.intents.filter(i => i !== intent.id);
                                            updated[index] = { ...namespace, intents };
                                            updateSetting('namespaceConfiguration.namespaces', updated);
                                          }}
                                          className="rounded border-gray-300"
                                        />
                                        <Label
                                          htmlFor={`ns-${index}-intent-${intent.id}`}
                                          className="text-sm font-normal cursor-pointer"
                                          title={intent.description}
                                        >
                                          {intent.displayName}
                                        </Label>
                                      </div>
                                    ))}
                                  </div>
                                  {(!settings.namespaceConfiguration?.intents || settings.namespaceConfiguration.intents.length === 0) && (
                                    <p className="text-xs text-amber-600 mt-2">
                                      ⚠️ No intents defined. Please add intents above first.
                                    </p>
                                  )}
                                </div>
                              </div>
                            </Card>
                          );
                        })}
                      </div>

                      <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                        <h4 className="text-sm font-medium text-blue-900 dark:text-blue-100 mb-2">Intent Coverage</h4>
                        <div className="text-xs text-blue-800 dark:text-blue-200 space-y-1">
                          {(settings.namespaceConfiguration?.intents || []).map((intent) => {
                            const namespaces = settings.namespaceConfiguration!.namespaces.filter(ns => 
                              ns.intents.includes(intent.id)
                            );
                            return (
                              <div key={intent.id} className="flex justify-between">
                                <span className="font-medium">{intent.displayName}:</span>
                                <span>
                                  {namespaces.length > 0 
                                    ? namespaces.map(ns => ns.displayName).join(', ')
                                    : '⚠️ Not mapped'
                                  }
                                </span>
                              </div>
                            );
                          })}
                          {(!settings.namespaceConfiguration?.intents || settings.namespaceConfiguration.intents.length === 0) && (
                            <p className="text-center text-muted-foreground">No intents defined yet</p>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

                  {!settings.namespaceConfiguration?.enabled && (
                    <div className="text-center py-8 text-muted-foreground">
                      <p>Enable custom namespaces to configure intent mappings</p>
                      <p className="text-sm mt-2">Currently using default namespace configuration</p>
                    </div>
                  )}
                </CardContent>
                <CardFooter>
                  <Button onClick={saveSettings} disabled={saving}>
                    {saving ? <><Spinner className="mr-2" size="sm" /> Saving...</> : 'Save Changes'}
                  </Button>
                </CardFooter>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </AdminLayout>
    </AdminGuard>
  );
}

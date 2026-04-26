import React, { useState, useEffect, useRef } from "react";
import useWebSocket, { ReadyState } from 'react-use-websocket';
import { Button } from "../components/Button";
import { Input } from "../extensions/shadcn/components/input";
import { ToggleGroup, ToggleGroupItem } from "../extensions/shadcn/components/toggle-group";
import { auth, WS_API_URL, API_URL } from "../app";
import { apiClient } from "../app";
type NamespaceInfo = any;

// --- WORKAROUND: Moved helper function directly into the component ---
const getAuthenticatedWebSocket = async (path: string): Promise<{ url: string; protocols: string[] }> => {
  const token = await auth.getAuthToken();
  return {
    url: `${WS_API_URL}${path}`,
    protocols: ["databutton.app", `Authorization.Bearer.${token}`],
  };
};

// A simple spinner component for loading states
const Spinner = ({ className }: { className?: string }) => (
  <svg
    className={`animate-spin -ml-1 mr-3 h-5 w-5 text-white ${className}`}
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    viewBox="0 0 24 24"
  >
    <circle
      className="opacity-25"
      cx="12"
      cy="12"
      r="10"
      stroke="currentColor"
      strokeWidth="4"
    ></circle>
    <path
      className="opacity-75"
      fill="currentColor"
      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
    ></path>
  </svg>
);

export const KnowledgeSearch = () => {
  const [socketConfig, setSocketConfig] = useState<{ url: string; protocols: string[] } | null>(null);
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState<any[]>([]);
  const [summary, setSummary] = useState<string | null>(null);
  const [sources, setSources] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [activeFilter, setActiveFilter] = useState("all");
  const [playingSourceId, setPlayingSourceId] = useState<string | null>(null);
  const [openingDocId, setOpeningDocId] = useState<string | null>(null);
  const [namespaces, setNamespaces] = useState<NamespaceInfo[]>([]);
  const [namespacesLoading, setNamespacesLoading] = useState(true);
  const audioPlayerRef = useRef<HTMLAudioElement>(null);

  // Helper to safely extract the title from various possible keys
  const getSourceTitle = (source: any) => {
    if (source.file_name) return source.file_name;
    if (source.fileName) return source.fileName;
    if (source.title) return source.title;
    if (source.name) return source.name;
    if (source.original_session_id) return "Expert Session";
    if (source.ticket_id) return `Historic Ticket #${source.ticket_id}`;
    return source.document_id || "Unknown Source";
  };

  // Helper to safely extract the text content from various possible keys
  const getSourceText = (source: any) => {
    return source.original_text || source.text || source.page_content || source.content || source.image_description || "";
  };

  // 1. Get the authenticated WebSocket URL when the component mounts
  useEffect(() => {
    const fetchSocketUrl = async () => {
      // Use the local helper function
      const config = await getAuthenticatedWebSocket('/ws/retrieve-knowledge');
      setSocketConfig(config);
    };
    fetchSocketUrl();
  }, []);

  // Fetch company namespaces on mount
  useEffect(() => {
    const fetchNamespaces = async () => {
      try {
        const response = await apiClient.get_company_namespaces_endpoint();
        const data = await response.json();
        setNamespaces(data.namespaces || []);
        console.log('[NAMESPACE_DEBUG] Fetched namespaces:', data.namespaces);
      } catch (error) {
        console.error('[NAMESPACE_DEBUG] Error fetching namespaces:', error);
        // Fallback to empty array - "All" will still work
        setNamespaces([]);
      } finally {
        setNamespacesLoading(false);
      }
    };
    fetchNamespaces();
  }, []);

  // 2. Initialize the WebSocket connection
  const { sendMessage, lastMessage, readyState } = useWebSocket(
    socketConfig?.url || null, 
    {
      protocols: socketConfig?.protocols,
      shouldReconnect: (closeEvent) => true,
    }
  );

  // 3. Handle incoming messages from the server
  useEffect(() => {
    if (lastMessage !== null) {
      const message = JSON.parse(lastMessage.data);
      if (message.status !== 'complete') {
        setMessages((prev) => [...prev, message]);
      }
      
      if (message.status === 'processing') {
        setIsSearching(true);
      }
      if (message.status === 'complete') {
        console.log('[FRONTEND_DEBUG] Received complete message:', message);
        console.log('[FRONTEND_DEBUG] Sources data:', message.data.sources);
        
        // Debug each source structure
        if (message.data.sources) {
          message.data.sources.forEach((source, idx) => {
            console.log(`[FRONTEND_DEBUG] Source ${idx + 1}:`, {
              hasMetadata: !!(source.file_name && source.document_id && source.page_number),
              fileName: source.file_name,
              pageNumber: source.page_number,
              documentId: source.document_id,
              fullSource: source
            });
          });
        }
        
        setSummary(message.data.summary);
        setSources(message.data.sources || []);
        setIsSearching(false);
      }
      if (message.status === 'error') {
        setIsSearching(false);
        // Here you would show an error toast or message
        console.error("WebSocket Error:", message.message);
      }
    }
  }, [lastMessage]);

  const handleOpenDocument = async (documentId: string) => {
    if (!documentId) return;
    setOpeningDocId(documentId);
    try {
      // WORKAROUND: Bypass the brain client and call the endpoint directly
      // as there appears to be a parameter name mismatch in the generated client.
      const token = await auth.getAuthToken();
      const response = await fetch(`${API_URL}/get-secure-document-url/${documentId}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        window.open(data.signed_url, "_blank", "noopener,noreferrer");
      } else {
        const errorData = await response.json();
        console.error(
          "Failed to get secure URL:",
          errorData.detail || "Unknown error",
        );
        // In a real app, you'd show a toast notification here.
      }
    } catch (error) {
      console.error("Error fetching secure document URL:", error);
    } finally {
      setOpeningDocId(null);
    }
  };

  const playAudioForSource = async (source: any) => {
    // If we click the same source that is playing, stop it.
    if (playingSourceId === source.chunk_id) {
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
        audioPlayerRef.current.currentTime = 0;
      }
      setPlayingSourceId(null);
      return;
    }

    const textToPlay = getSourceText(source);

    if (!textToPlay) {
      console.warn("No text content found for audio playback", source);
      return;
    }

    setPlayingSourceId(source.chunk_id);

    try {
      const token = await auth.getAuthToken();
      
      // Call synthesize to get the audio URL (cached or newly generated)
      const response = await fetch(`${API_URL}/synthesize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ text: textToPlay }),
      });

      if (!response.ok) {
        throw new Error(`API returned an error: ${response.statusText}`);
      }

      // Get the audio URL from the response
      const data = await response.json();
      const audioUrl = data.audio_url;
      
      // Fetch the pre-generated audio file (instant playback)
      const audioResponse = await fetch(audioUrl, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      
      if (!audioResponse.ok) {
        throw new Error(`Failed to fetch audio file: ${audioResponse.statusText}`);
      }
      
      const blob = await audioResponse.blob();
      const objectUrl = URL.createObjectURL(blob);

      if (audioPlayerRef.current) {
        audioPlayerRef.current.src = objectUrl;
        audioPlayerRef.current.play();

        audioPlayerRef.current.onended = () => {
          setPlayingSourceId(null);
          URL.revokeObjectURL(objectUrl);
        };
      }
    } catch (error) {
      console.error("Failed to play audio:", error);
      setPlayingSourceId(null);
    }
  };

  const handleSearch = () => {
    if (query && readyState === ReadyState.OPEN) {
      setMessages([]); // Clear old messages
      setSummary(null);
      setSources([]);
      
      // Map filter selection to namespace values
      let namespaces: string[];
      if (activeFilter === "all") {
        // All sources - backend will expand to all namespaces
        namespaces = ["all"];
      } else {
        // Single selection - use the namespace ID directly
        namespaces = [activeFilter];
      }
      
      console.log(`[SEARCH] Sending query '${query}' with filter: ${activeFilter}, namespaces:`, namespaces);
      sendMessage(JSON.stringify({ query, namespaces }));
    }
  };

  const connectionStatus = {
    [ReadyState.CONNECTING]: "Connecting",
    [ReadyState.OPEN]: "Connected",
    [ReadyState.CLOSING]: "Closing",
    [ReadyState.CLOSED]: "Closed",
    [ReadyState.UNINSTANTIATED]: "Uninstantiated",
  };

  const handleToggleChange = (value: string) => {
    if (value) setActiveFilter(value);
  };

  return (
    <div className="flex flex-col h-full bg-gray-900 text-white font-sans">
      <audio ref={audioPlayerRef} style={{ display: "none" }} />
      <div className="flex-1 overflow-y-auto p-6">
        <h1 className="text-3xl font-extrabold text-center mb-6 text-indigo-400">Knowledge Search</h1>
        <div className="max-w-4xl mx-auto">
          {/* Input and Search Button */}
          <div className="flex w-full items-center space-x-3 mb-4">
            <Input 
              type="text" 
              placeholder="Enter your query..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={isSearching || readyState !== ReadyState.OPEN}
            />
            <Button onClick={handleSearch} disabled={isSearching || readyState !== ReadyState.OPEN || !query}>
              {isSearching ? <Spinner className="h-4 w-4 mr-2" /> : 'Search'}
            </Button>
          </div>
          
          {/* Filter Group */}
          <div className="flex items-center space-x-4 mb-4">
            <span className="text-sm font-medium text-gray-400">Filter by Source:</span>
            <ToggleGroup
              type="single"
              defaultValue="all"
              onValueChange={handleToggleChange}
            >
              <ToggleGroupItem value="all">
                All
              </ToggleGroupItem>
              {namespacesLoading ? (
                <ToggleGroupItem value="loading" disabled>
                  Loading...
                </ToggleGroupItem>
              ) : (
                namespaces.map((ns) => (
                  <ToggleGroupItem key={ns.id} value={ns.id}>
                    {ns.displayName}
                  </ToggleGroupItem>
                ))
              )}
            </ToggleGroup>
          </div>

          <p className="text-sm text-gray-500 mt-2">WebSocket Status: <span className={`font-semibold ${readyState === ReadyState.OPEN ? 'text-green-400' : 'text-yellow-500'}`}>{connectionStatus[readyState]}</span></p>

          {/* Display messages and results */}
          <div className="mt-6 space-y-2">
            {messages.map((msg, idx) => (
              <div key={idx} className="text-sm p-3 bg-gray-800 rounded-md shadow-inner">
                <span className="font-bold capitalize text-indigo-300">{msg.status}:</span> {msg.message}
              </div>
            ))}
          </div>

          {summary && (
            <div className="mt-8 p-6 border border-gray-700 rounded-xl bg-gray-800 shadow-xl">
              <h3 className="font-bold text-xl mb-3 text-indigo-400">Summary</h3>
              <p className="text-gray-200 whitespace-pre-wrap leading-relaxed">{summary}</p>
              
              {sources.length > 0 && (
                <div className="mt-6">
                  <h4 className="font-bold text-lg mb-3 text-gray-300 border-b border-gray-700 pb-1">Sources ({sources.length}):</h4>
                  <div className="space-y-3">
                    {sources.map((source, idx) => (
                      <details key={idx} className="bg-gray-700/50 p-4 rounded-lg text-sm shadow-md">
                        <summary className="cursor-pointer font-semibold text-blue-300 hover:text-blue-200 flex items-center justify-between transition-colors">
                          <span className="truncate max-w-[300px]" title={getSourceTitle(source)}>
                            {getSourceTitle(source)}
                          </span>
                          {source.document_id && source.file_name && (
                            <Button
                              size="sm"
                              variant="outline"
                              className="ml-2 text-xs bg-gray-600 hover:bg-gray-500 border-gray-500 text-gray-200"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleOpenDocument(source.document_id);
                              }}
                              disabled={openingDocId === source.document_id}
                            >
                              {openingDocId === source.document_id ? <Spinner className="h-4 w-4 mr-1 text-indigo-400" /> : null}
                              {openingDocId === source.document_id ? "Opening..." : "Open Document"}
                            </Button>
                          )}
                        </summary>
                        <div className="mt-3 space-y-2">
                          {/* Metadata */}
                          <div className="text-xs text-gray-400 border-b border-gray-600 pb-2 flex flex-wrap gap-4">
                            {source.file_name && <span><span className="font-semibold">File:</span> {source.file_name}</span>}
                            {source.page_number && <span><span className="font-semibold">Page:</span> {source.page_number}</span>}
                            {source.original_session_id && <span><span className="font-semibold">Session ID:</span> {source.original_session_id.slice(0, 8)}...</span>}
                            {source.ticket_id && <span><span className="font-semibold">Ticket:</span> {source.ticket_id}</span>}
                            {source.source && <span><span className="font-semibold">Type:</span> {source.source.replace('_', ' ')}</span>}
                          </div>
                          <div className="flex items-start gap-3 pt-2">
                            {/* Snippet */}
                            <pre className="flex-grow text-gray-300 overflow-x-auto whitespace-pre-wrap font-mono text-xs bg-gray-800 p-3 rounded-lg border border-gray-700">
                              {getSourceText(source)}
                            </pre>
                            {/* Playback Button */}
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => playAudioForSource(source)}
                              className="mt-1 flex-shrink-0 bg-gray-600 hover:bg-gray-500"
                            >
                              {playingSourceId === source.chunk_id ? (
                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-stop-fill text-red-400" viewBox="0 0 16 16">
                                  <path d="M5 3.5h6A1.5 1.5 0 0 1 12.5 5v6a1.5 1.5 0 0 1-1.5 1.5H5A1.5 1.5 0 0 1 3.5 11V5A1.5 1.5 0 0 1 5 3.5z"/>
                                </svg>
                              ) : (
                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-play-fill text-green-400" viewBox="0 0 16 16">
                                  <path d="m11.596 8.697-6.363 3.692c-.54.313-1.233-.066-1.233-.697V4.308c0-.63.692-1.01 1.233-.696l6.363 3.692a.802.802 0 0 1 0 1.393z"/>
                                </svg>
                              )}
                            </Button>
                          </div>
                        </div>
                      </details>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

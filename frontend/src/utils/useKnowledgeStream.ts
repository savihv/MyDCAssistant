import { useEffect, useRef, useCallback } from "react";
import { auth, WS_API_URL } from "app";
import { useKnowledgeStreamStore, WebSocketMessage } from "./useKnowledgeStreamStore";
import { create } from "zustand";
import { apiClient } from "app";
// import removed

const WEBSOCKET_PATH = "/knowledge_retrieval/ws/stream-knowledge";

/**
 * Custom hook to manage a streaming WebSocket connection for knowledge retrieval.
 * It handles connection setup, authentication, message passing, and cleanup.
 *
 * @returns {object} An object containing the `sendQuery` function.
 */
export const useKnowledgeStream = () => {
  const ws = useRef<WebSocket | null>(null);
  const { setStatus, addChunk, setError, setLastMessage, reset } = useKnowledgeStreamStore((state) => state.actions);

  const connect = useCallback(async () => {
    // Prevent multiple connections
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      return;
    }

    setStatus("connecting");

    try {
      // 1. Get authentication token
      const token = await auth.getAuthToken();
      if (!token) {
        throw new Error("Authentication token not found.");
      }

      // 2. Construct WebSocket URL with required protocols
      const url = `${WS_API_URL}${WEBSOCKET_PATH}`;
      const protocols = ["databutton.app", `Authorization.Bearer.${token}`];

      // 3. Initialize WebSocket connection
      ws.current = new WebSocket(url, protocols);

      // 4. Define event listeners
      ws.current.onopen = () => {
        setStatus("connected");
      };

      ws.current.onmessage = (event) => {
        const message: WebSocketMessage = JSON.parse(event.data);
        setLastMessage(message);

        switch (message.status) {
          case "chunk":
            if (message.data) {
              addChunk(message.data);
            }
            break;
          case "error":
            setError(message.message || "An unknown error occurred.");
            break;
          case "complete":
            // The stream is finished, but we can keep the connection open for more queries.
            break;
          default:
            break;
        }
      };

      ws.current.onerror = (event) => {
        console.error("WebSocket Error:", event);
        setError("WebSocket connection error.");
        setStatus("error");
      };

      ws.current.onclose = (event) => {
        if (event.wasClean) {
          setStatus("disconnected");
        } else {
          // e.g., server process killed or network down
          setError("Connection died unexpectedly.");
          setStatus("error");
        }
      };
    } catch (error) {
      console.error("Failed to connect to WebSocket:", error);
      setError(error instanceof Error ? error.message : "An unknown connection error occurred.");
      setStatus("error");
    }
  }, [setStatus, addChunk, setError, setLastMessage]);

  const disconnect = useCallback(() => {
    if (ws.current) {
      ws.current.close();
      ws.current = null;
      reset();
    }
  }, [reset]);

  // Effect to connect on mount and disconnect on unmount
  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  /**
   * Sends a query to the WebSocket server.
   *
   * @param {string} query The search query string.
   * @param {string[]} [media_urls] Optional array of media URLs.
   */
  const sendQuery = useCallback((query: string, media_urls?: string[]) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      // Reset previous results before sending a new query
      reset();
      setStatus("connected"); // Ensure status is ready for new stream
      
      const payload = {
        query,
        media_urls: media_urls || [],
      };
      ws.current.send(JSON.stringify(payload));
    } else {
      console.error("Cannot send query: WebSocket is not connected.");
      setError("Cannot send query: WebSocket is not connected.");
      setStatus("error");
    }
  }, [reset, setStatus, setError]);

  return { sendQuery, connect, disconnect };
};

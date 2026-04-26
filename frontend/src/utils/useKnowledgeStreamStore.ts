import { create } from "zustand";
import { devtools } from "zustand/middleware";

// Defines the structure of a single knowledge chunk received from the stream
export interface KnowledgeChunk {
  page_content: string;
  metadata: {
    source: string;
    [key: string]: any;
  };
  score: number;
}

// Defines the shape of the WebSocket message object
export interface WebSocketMessage {
  status: "info" | "error" | "processing" | "chunk" | "complete";
  message?: string;
  data?: KnowledgeChunk;
}

// Defines the possible states of the WebSocket connection
export type WebSocketStatus = "idle" | "connecting" | "connected" | "disconnected" | "error";

// Defines the structure of the store's state
interface KnowledgeStreamState {
  status: WebSocketStatus;
  chunks: KnowledgeChunk[];
  error: string | null;
  lastMessage: WebSocketMessage | null;
  actions: {
    setStatus: (status: WebSocketStatus) => void;
    addChunk: (chunk: KnowledgeChunk) => void;
    setError: (error: string | null) => void;
    setLastMessage: (message: WebSocketMessage) => void;
    reset: () => void;
  };
}

// Create the Zustand store for managing the knowledge stream
export const useKnowledgeStreamStore = create<KnowledgeStreamState>()(
  devtools(
    (set) => ({
      status: "idle",
      chunks: [],
      error: null,
      lastMessage: null,
      actions: {
        setStatus: (status) => set({ status, error: null }),
        addChunk: (chunk) => set((state) => ({ chunks: [...state.chunks, chunk] })),
        setError: (error) => set({ status: "error", error }),
        setLastMessage: (message) => set({ lastMessage: message }),
        reset: () => set({ status: "idle", chunks: [], error: null, lastMessage: null }),
      },
    }),
    { name: "KnowledgeStreamStore" }
  )
);

// Export actions for easy access in components and hooks
export const useKnowledgeStreamActions = () => useKnowledgeStreamStore((state) => state.actions);

// Export state selectors for easy access in components
export const useKnowledgeStreamStatus = () => useKnowledgeStreamStore((state) => state.status);
export const useKnowledgeStreamChunks = () => useKnowledgeStreamStore((state) => state.chunks);
export const useKnowledgeStreamError = () => useKnowledgeStreamStore((state) => state.error);
export const useKnowledgeStreamLastMessage = () => useKnowledgeStreamStore((state) => state.lastMessage);

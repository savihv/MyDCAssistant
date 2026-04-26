import React, { useState, useEffect } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../extensions/shadcn/components/select";
import { Label } from "../extensions/shadcn/components/label";
import { Skeleton } from "../extensions/shadcn/components/skeleton";
import { doc, getDoc } from "firebase/firestore";
import { firestore } from "../app";
import { useUserRoles } from "../utils/useUserRoles";
import { apiClient } from "../app";
import { NamespaceInfo } from "../apiclient/data-contracts";

// Default knowledge bases for fallback
const DEFAULT_KNOWLEDGE_BASES = [
  { value: "general", label: "General Knowledge", isDefault: true },
  { value: "baseline", label: "Baseline (Golden Standard)", isDefault: false },
  { value: "historic", label: "Historic Records", isDefault: false },
  { value: "expert", label: "Expert Knowledge", isDefault: false },
];

interface Props {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  onDefaultNamespaceLoad?: (defaultNamespace: string) => void; // NEW PROP
}

interface Namespace {
  value: string;
  label: string;
  isDefault?: boolean;
}

export const KnowledgeBaseSelector: React.FC<Props> = ({
  value,
  onChange,
  disabled,
  onDefaultNamespaceLoad, // NEW PROP
}) => {
  const { company } = useUserRoles();
  const [namespaces, setNamespaces] = useState<Namespace[]>(DEFAULT_KNOWLEDGE_BASES);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchNamespaces = async () => {
      try {
        console.log("[KnowledgeBaseSelector] Fetching namespaces from API");
        const response = await apiClient.get_company_namespaces_endpoint();
        const data: { namespaces: NamespaceInfo[] } = await response.json();
        
        console.log("[KnowledgeBaseSelector] Received namespaces:", data.namespaces);
        
        // Transform backend format to component format
        const transformed = data.namespaces.map(ns => ({
          value: ns.id,
          label: ns.displayName,
          isDefault: ns.isDefault || false,
        }));
        
        setNamespaces(transformed);
        
        // Notify parent of default namespace
        if (onDefaultNamespaceLoad) {
          const defaultNs = transformed.find(ns => ns.isDefault);
          onDefaultNamespaceLoad(defaultNs?.value || transformed[0]?.value || 'general');
        }
        setLoading(false);
      } catch (error) {
        console.error("[KnowledgeBaseSelector] Error fetching namespaces:", error);
        // Fallback to defaults
        console.log("[KnowledgeBaseSelector] Using default namespaces");
        setNamespaces(DEFAULT_KNOWLEDGE_BASES);
        if (onDefaultNamespaceLoad) {
          const defaultNs = DEFAULT_KNOWLEDGE_BASES.find(ns => ns.isDefault);
          onDefaultNamespaceLoad(defaultNs?.value || 'general');
        }
        setLoading(false);
      }
    };

    fetchNamespaces();
  }, [onDefaultNamespaceLoad]);

  // Show skeleton while loading
  if (loading) {
    return (
      <div className="space-y-2">
        <Label>Knowledge Base</Label>
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <Label>Knowledge Base</Label>
      <Select value={value} onValueChange={onChange} disabled={disabled}>
        <SelectTrigger id="knowledge-base-select">
          <SelectValue placeholder={loading ? "Loading..." : "Select a knowledge base..."} />
        </SelectTrigger>
        <SelectContent>
          {namespaces.map((kb) => (
            <SelectItem key={kb.value} value={kb.value}>
              {kb.label}
              {kb.isDefault && <span className="ml-2 text-xs text-muted-foreground">(Default)</span>}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
};

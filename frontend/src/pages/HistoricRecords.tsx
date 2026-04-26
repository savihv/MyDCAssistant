import React, { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { apiClient } from "../app";
import { Trash2, Loader2, ArrowLeft, RefreshCw } from "lucide-react";
import { Button } from "../extensions/shadcn/components/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../extensions/shadcn/components/card";
import { Checkbox } from "../extensions/shadcn/components/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../extensions/shadcn/components/table";
import { Badge } from "../extensions/shadcn/components/badge";
import { useNavigate } from "react-router-dom";
import { KnowledgeBaseSelector } from "../components/KnowledgeBaseSelector";

interface HistoricRecord {
  id: string;
  record_id: string;
  issue_description: string;
  resolution: string;
  service_date?: string;
  technician_name?: string;
  equipment_model?: string;
  equipment_manufacturer?: string;
  customer_name?: string;
  customer_location?: string;
  technician_notes?: string;
  imported_at?: any;
}

export default function HistoricRecordsPage() {
  const navigate = useNavigate();
  const [records, setRecords] = useState<HistoricRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedRecordIds, setSelectedRecordIds] = useState<Set<string>>(new Set());
  const [isDeleting, setIsDeleting] = useState(false);
  const [targetIndex, setTargetIndex] = useState<string>('general');
  const [selectorKey, setSelectorKey] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const LIMIT = 50;

  // Fetch records
  const fetchRecords = useCallback(async (resetOffset: boolean = false) => {
    setLoading(true);
    try {
      const currentOffset = resetOffset ? 0 : offset;
      const response = await apiClient.list_historic_records({
        target_index: targetIndex,
        limit: LIMIT,
        offset: currentOffset
      });
      
      if (!response.ok) {
        throw new Error('Failed to fetch records');
      }
      
      const data = await response.json();
      setRecords(data.records || []);
      setHasMore(data.has_more || false);
      
      if (resetOffset) {
        setOffset(0);
      }
    } catch (error) {
      console.error('Error fetching records:', error);
      toast.error('Failed to fetch records');
    } finally {
      setLoading(false);
    }
  }, [targetIndex, offset]);

  // Effect: Refresh KnowledgeBaseSelector when window regains focus
  useEffect(() => {
    const handleFocus = () => {
      console.log('[HistoricRecords] Window focused, refreshing namespace selector');
      setSelectorKey(prev => prev + 1);
    };
    
    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, []);

  useEffect(() => {
    fetchRecords(true);
  }, [targetIndex]);

  // Toggle selection
  const toggleRecordSelection = (recordId: string) => {
    setSelectedRecordIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(recordId)) {
        newSet.delete(recordId);
      } else {
        newSet.add(recordId);
      }
      return newSet;
    });
  };

  // Toggle all
  const toggleAll = () => {
    if (selectedRecordIds.size === records.length) {
      setSelectedRecordIds(new Set());
    } else {
      setSelectedRecordIds(new Set(records.map(r => r.id)));
    }
  };

  // Delete single record
  const handleDeleteRecord = async (recordId: string) => {
    if (!confirm("Are you sure you want to delete this record? This action cannot be undone.")) {
      return;
    }
    
    try {
      const response = await apiClient.delete_historic_record({
        recordId,
        target_index: targetIndex
      });
      
      if (!response.ok) {
        throw new Error('Delete failed');
      }
      
      setRecords(prev => prev.filter(r => r.id !== recordId));
      toast.success("Record deleted successfully");
    } catch (error) {
      console.error("Error deleting record:", error);
      toast.error("Failed to delete record");
    }
  };

  // Bulk delete
  const handleBulkDelete = async () => {
    if (selectedRecordIds.size === 0) {
      toast.error("No records selected");
      return;
    }

    if (!confirm(`Are you sure you want to delete ${selectedRecordIds.size} record(s)? This action cannot be undone.`)) {
      return;
    }

    setIsDeleting(true);
    
    try {
      const response = await apiClient.bulk_delete_historic_records({
        record_ids: Array.from(selectedRecordIds),
        target_index: targetIndex
      });
      
      if (!response.ok) {
        throw new Error('Bulk delete failed');
      }
      
      const result = await response.json();
      
      // Remove deleted records from state
      setRecords(prev => prev.filter(r => !selectedRecordIds.has(r.id)));
      setSelectedRecordIds(new Set());
      
      toast.success(result.message || `Deleted ${result.deleted_count} record(s)`);
      
      if (result.failed_count > 0) {
        toast.warning(`${result.failed_count} record(s) failed to delete`);
      }
    } catch (error) {
      console.error("Error during bulk delete:", error);
      toast.error("Failed to delete records");
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="container mx-auto py-8 px-4">
      <Card className="bg-gray-800 border-gray-700 text-white">
        <CardHeader>
          <div className="flex justify-between items-start">
            <div>
              <CardTitle className="text-2xl">Historic Records Management</CardTitle>
              <CardDescription className="text-gray-400">
                View and manage CSV imported historic records
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={() => fetchRecords(true)}
                disabled={loading}
              >
                <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
              <Button
                variant="outline"
                onClick={() => navigate("/bulk-import")}
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Import
              </Button>
            </div>
          </div>
        </CardHeader>
        
        <CardContent className="space-y-4">
          {/* Knowledge base selector */}
          <div className="max-w-xs">
            <KnowledgeBaseSelector
              key={selectorKey}
              value={targetIndex}
              onChange={setTargetIndex}
              disabled={loading || isDeleting}
            />
          </div>

          {/* Bulk actions */}
          {selectedRecordIds.size > 0 && (
            <div className="flex items-center justify-between p-4 bg-gray-700/50 rounded-lg">
              <span className="text-sm">
                {selectedRecordIds.size} record(s) selected
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={handleBulkDelete}
                disabled={isDeleting}
              >
                {isDeleting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Deleting...
                  </>
                ) : (
                  <>
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete Selected
                  </>
                )}
              </Button>
            </div>
          )}

          {/* Records table */}
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
            </div>
          ) : records.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              <p>No records found for this knowledge base.</p>
            </div>
          ) : (
            <div className="border border-gray-700 rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="bg-gray-900/50 border-gray-700 hover:bg-gray-900/50">
                    <TableHead className="w-12">
                      <Checkbox
                        checked={selectedRecordIds.size === records.length && records.length > 0}
                        onCheckedChange={toggleAll}
                      />
                    </TableHead>
                    <TableHead>Record ID</TableHead>
                    <TableHead>Issue</TableHead>
                    <TableHead>Resolution</TableHead>
                    <TableHead>Service Date</TableHead>
                    <TableHead>Technician</TableHead>
                    <TableHead>Equipment</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {records.map((record) => (
                    <TableRow 
                      key={record.id}
                      className="border-gray-700 hover:bg-gray-700/30"
                    >
                      <TableCell>
                        <Checkbox
                          checked={selectedRecordIds.has(record.id)}
                          onCheckedChange={() => toggleRecordSelection(record.id)}
                        />
                      </TableCell>
                      <TableCell className="font-mono text-sm">
                        {record.record_id}
                      </TableCell>
                      <TableCell className="max-w-xs truncate">
                        {record.issue_description}
                      </TableCell>
                      <TableCell className="max-w-xs truncate">
                        {record.resolution}
                      </TableCell>
                      <TableCell>
                        {record.service_date ? (
                          <Badge variant="outline">{record.service_date}</Badge>
                        ) : (
                          <span className="text-gray-500">N/A</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {record.technician_name || <span className="text-gray-500">N/A</span>}
                      </TableCell>
                      <TableCell>
                        {record.equipment_model ? (
                          <div className="text-sm">
                            <div>{record.equipment_model}</div>
                            {record.equipment_manufacturer && (
                              <div className="text-gray-500 text-xs">
                                {record.equipment_manufacturer}
                              </div>
                            )}
                          </div>
                        ) : (
                          <span className="text-gray-500">N/A</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteRecord(record.id)}
                        >
                          <Trash2 className="h-4 w-4 text-red-400" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          {/* Pagination */}
          {(hasMore || offset > 0) && (
            <div className="flex justify-between items-center">
              <Button
                variant="outline"
                onClick={() => {
                  setOffset(Math.max(0, offset - LIMIT));
                  fetchRecords();
                }}
                disabled={offset === 0 || loading}
              >
                Previous
              </Button>
              <span className="text-sm text-gray-400">
                Showing {offset + 1} - {Math.min(offset + LIMIT, offset + records.length)}
              </span>
              <Button
                variant="outline"
                onClick={() => {
                  setOffset(offset + LIMIT);
                  fetchRecords();
                }}
                disabled={!hasMore || loading}
              >
                Next
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

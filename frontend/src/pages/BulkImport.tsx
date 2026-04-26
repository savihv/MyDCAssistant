import React, { useState, useCallback, useEffect } from "react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import { apiClient } from "../app";
import { UploadCloud, File as FileIcon, Loader2, AlertCircle, ArrowLeft, Info } from "lucide-react";
import { Button } from "../extensions/shadcn/components/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../extensions/shadcn/components/card";
import { Alert, AlertDescription } from "../extensions/shadcn/components/alert";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../extensions/shadcn/components/select";
import { Label } from "../extensions/shadcn/components/label";
import type { CSVUploadResponse, CSVHeadersResponse } from "../apiclient/data-contracts";
import { useNavigate } from "react-router-dom";
import { KnowledgeBaseSelector } from "../components/KnowledgeBaseSelector";

// Define the fields the system expects
const SYSTEM_FIELDS = {
  required: ['record_id', 'issue_description', 'resolution'],
  optional: [
    'service_date', 
    'technician_name', 
    'equipment_model', 
    'equipment_manufacturer',
    'customer_name', 
    'customer_location', 
    'technician_notes'
  ],
};
const ALL_SYSTEM_FIELDS = [...SYSTEM_FIELDS.required, ...SYSTEM_FIELDS.optional];

type ColumnMapping = Record<string, string>;

// Helper function to check if a column name suggests it might contain dates
function isLikelyDateColumn(columnName: string): boolean {
  const lowerName = columnName.toLowerCase().replace(/[_\s-]/g, '');
  const dateKeywords = ['date', 'time', 'created', 'updated', 'modified', 'timestamp', 'day', 'month', 'year'];
  return dateKeywords.some(keyword => lowerName.includes(keyword));
}

export default function BulkImportPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [targetIndex, setTargetIndex] = useState<string>('general');
  const [selectorKey, setSelectorKey] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadErrors, setUploadErrors] = useState<string[]>([]);
  const [csvHeaders, setCsvHeaders] = useState<string[]>([]);
  const [isFetchingHeaders, setIsFetchingHeaders] = useState(false);
  const [columnMapping, setColumnMapping] = useState<ColumnMapping>({});
  const [dateWarning, setDateWarning] = useState<string | null>(null);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      const selectedFile = acceptedFiles[0];
      if (selectedFile.type !== "text/csv") {
        toast.error("Invalid file type. Please upload a CSV file.");
        return;
      }
      setFile(selectedFile);
      setUploadErrors([]);
      setCsvHeaders([]);
      setColumnMapping({});
      setIsFetchingHeaders(true);

      try {
        const response = await apiClient.get_csv_headers({ file: selectedFile });
        const result = await response.json() as CSVHeadersResponse;
        
        if (response.ok && result.headers) {
          setCsvHeaders(result.headers);
          // Auto-map initial values
          const initialMapping: ColumnMapping = {};
          ALL_SYSTEM_FIELDS.forEach(field => {
            const similarHeader = result.headers.find(h => h.replace(/[\s_]/g, '').toLowerCase() === field.replace(/_/g, ''));
            if (similarHeader) {
              initialMapping[field] = similarHeader;
            }
          });
          setColumnMapping(initialMapping);
        } else {
          toast.error("Could not read headers from the CSV file.");
        }
      } catch (error) {
        toast.error("Failed to fetch CSV headers.");
      } finally {
        setIsFetchingHeaders(false);
      }
    }
  }, []);

  const handleMappingChange = (systemField: string, csvHeader: string) => {
    // Clear any previous date warning
    if (systemField === 'service_date') {
      setDateWarning(null);
    }
    
    // If user selects the "skip" option, store it as an empty string.
    const newValue = csvHeader === '--none--' ? '' : csvHeader;
    
    // Validate if service_date is being mapped to a non-date column
    if (systemField === 'service_date' && newValue && !isLikelyDateColumn(newValue)) {
      setDateWarning(
        `Warning: "${newValue}" doesn't appear to be a date column. The system expects dates in formats like YYYY-MM-DD, MM/DD/YYYY, or similar. ` +
        `If this column doesn't contain dates, consider leaving Service Date unmapped (it's optional).`
      );
    }
    
    setColumnMapping(prev => ({ ...prev, [systemField]: newValue }));
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
    },
    multiple: false,
  });

  // Effect: Refresh KnowledgeBaseSelector when window regains focus
  useEffect(() => {
    const handleFocus = () => {
      console.log('[BulkImport] Window focused, refreshing namespace selector');
      setSelectorKey(prev => prev + 1);
    };
    
    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, []);

  const handleUpload = async () => {
    if (!file) {
      toast.warning("Please select a file to upload.");
      return;
    }
    // Validate that all required fields are mapped
    const missingMappings = SYSTEM_FIELDS.required.filter(field => !columnMapping[field]);
    if (missingMappings.length > 0) {
      toast.error(`Please map all required fields: ${missingMappings.join(', ')}`);
      return;
    }
    
    // Warn if date field has suspicious mapping but allow upload
    if (dateWarning) {
      const proceed = confirm(
        "You've mapped a non-date column to Service Date. This may cause parsing warnings. Do you want to continue?"
      );
      if (!proceed) {
        return;
      }
    }

    setIsUploading(true);
    setUploadErrors([]); // Clear errors on new upload
    const toastId = toast.loading("Uploading and processing CSV file...");

    try {
      // Revert to using the brain client for a more reliable upload.
      // The backend will be updated to accept this structure.
      const response = await apiClient.upload_historic_records_csv({
        file: file,
        mapping: JSON.stringify(columnMapping),
        target_index: targetIndex  // ✅ Add target_index here
      });
      const result = await response.json();

      if (response.ok) {
        const uploadResult = result as CSVUploadResponse;
        toast.success(uploadResult.message || "File processed successfully!", { id: toastId });
        if (uploadResult.errors && uploadResult.errors.length > 0) {
          setUploadErrors(uploadResult.errors);
          toast.warning("Some rows had issues and were not imported. See details below.");
        }
        setFile(null);
        setCsvHeaders([]);
        setColumnMapping({});
        setDateWarning(null);
        setTargetIndex('historic');
      } else {
        throw new Error((result as any).detail || "An unknown error occurred.");
      }
    } catch (error: any) {
      toast.error(error.message || "Upload failed. Please try again.", { id: toastId });
    } finally {
      setIsUploading(false);
    }
  };
  return (
    <div className="container mx-auto py-8">
      <Card className="max-w-3xl mx-auto bg-gray-800 border-gray-700 text-white">
        <CardHeader className="flex flex-row justify-between items-start">
          <div>
            <CardTitle>Bulk Import Historic Data</CardTitle>
            <CardDescription>
              Upload your historical service records as a CSV file to enrich the knowledge base.
            </CardDescription>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => navigate("/historic-records")}
            >
              Manage Records
            </Button>
            <Button
              variant="outline"
              onClick={() => navigate("/admin-documents")}
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Go back to Documents
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          <div
            {...getRootProps()}
            className={`flex flex-col items-center justify-center p-12 border-2 border-dashed rounded-lg cursor-pointer transition-colors ${
              isDragActive ? "border-blue-400 bg-gray-700" : "border-gray-600 hover:border-gray-500"
            }`}
          >
            <input {...getInputProps()} />
            <UploadCloud className="w-12 h-12 text-gray-500 mb-4" />
            {isDragActive ? (
              <p>Drop the CSV file here ...</p>
            ) : (
              <p>Drag & drop a CSV file here, or click to select a file</p>
            )}
          </div>

          <Card className="bg-gray-900/60 border-gray-700">
            <CardContent className="pt-6 space-y-4">
              <Label htmlFor="knowledge-base-type" className="text-base font-semibold">Knowledge Base Type</Label>
          
              <KnowledgeBaseSelector
                key={selectorKey}
                value={targetIndex}
                onChange={setTargetIndex}
                disabled={isUploading}
              />
            </CardContent>
          </Card>
          
          {uploadErrors.length > 0 && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                <h5 className="font-bold mb-2">Import Errors:</h5>
                <ul className="list-disc pl-5 space-y-1">
                  {uploadErrors.map((error, index) => (
                    <li key={index} className="text-sm">{error}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          )}

          {file && (
            <div className="p-4 bg-gray-700/50 rounded-lg">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <FileIcon className="w-6 h-6 text-gray-400" />
                  <span className="font-medium">{file.name}</span>
                </div>
                <Button variant="ghost" size="sm" onClick={() => {
                  setFile(null);
                  setCsvHeaders([]);
                  setColumnMapping({});
                  setDateWarning(null);
                }}>Remove</Button>
              </div>

              {isFetchingHeaders && (
                <div className="flex items-center justify-center p-4">
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  <span>Reading columns...</span>
                </div>
              )}

              {csvHeaders.length > 0 && !isFetchingHeaders && (
                <>
                  {dateWarning && (
                    <Alert className="bg-yellow-900/20 border-yellow-600 text-yellow-200">
                      <Info className="h-4 w-4" />
                      <AlertDescription className="text-sm">
                        {dateWarning}
                      </AlertDescription>
                    </Alert>
                  )}
                  
                  <Card className="mt-4 bg-gray-900/60 border-gray-700">
                    <CardHeader>
                      <CardTitle className="text-lg">Map Columns</CardTitle>
                      <CardDescription>
                        Match your CSV columns to the system's fields. Required fields are marked with an asterisk (*).
                        <br />
                        <span className="text-yellow-300 text-xs">Note: Service Date expects date values (YYYY-MM-DD, MM/DD/YYYY, etc.). It's optional and can be left unmapped.</span>
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4">
                      {ALL_SYSTEM_FIELDS.map(field => (
                        <div key={field} className="grid grid-cols-2 items-center gap-4">
                          <Label htmlFor={field}>
                            {field.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                            {SYSTEM_FIELDS.required.includes(field) && <span className="text-red-500 ml-1">*</span>}
                          </Label>
                          <Select
                            value={columnMapping[field] || "--none--"}
                            onValueChange={(value) => handleMappingChange(field, value)}
                          >
                            <SelectTrigger id={field} className="bg-gray-800 border-gray-600">
                              <SelectValue placeholder="Select a column..." />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="--none--">
                                <em className="text-gray-400">Skip this field</em>
                              </SelectItem>
                              {csvHeaders
                                .filter(header => header && header.trim() !== '')
                                .map(header => (
                                <SelectItem key={header} value={header}>{header}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                </>
              )}
            </div>
          )}

          <div className="flex justify-end">
            <Button onClick={handleUpload} disabled={!file || isUploading || isFetchingHeaders} className="bg-blue-600 hover:bg-blue-700">
              {isUploading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Processing...
                </>
              ) : "Upload and Process File"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

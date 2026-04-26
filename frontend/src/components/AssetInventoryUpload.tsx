import React from "react";
import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Card } from "../extensions/shadcn/components/card";
import { Button } from "../components/Button";
import { Badge } from "../extensions/shadcn/components/badge";
import { Alert, AlertDescription } from "../extensions/shadcn/components/alert";
import { Upload, FileText, CheckCircle2, AlertCircle, Download, XCircle } from 'lucide-react';
import { apiClient } from "../app";
import { toast } from 'sonner';

export interface Props {
  projectId: string;
  onComplete: () => void;
  onSkip: () => void;
}

interface UploadResult {
  success: boolean;
  matchedCount: number;
  unmatchedSchematicDevices: string[];
  unmatchedInventoryDevices: Array<{
    rack: string;
    uPosition: string;
    serialNumber: string;
    manufacturer: string;
  }>;
  validationReport: string;
}

export function AssetInventoryUpload({ projectId, onComplete, onSkip }: Props) {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;

    const file = acceptedFiles[0];
    setSelectedFile(file);
    setIsUploading(true);
    setUploadResult(null);

    try {
      // Upload asset inventory CSV
      const formData = new FormData();
      formData.append('file', file);

      const response = await apiClient.upload_asset_inventory(
        { projectId: projectId },
        formData as any
      );

      const result: UploadResult = (await response.json()) as any;
      setUploadResult(result);

      if (result.matchedCount > 0) {
        toast.success(`✅ Matched ${result.matchedCount} devices with asset inventory`);
      } else {
        toast.warning('No devices matched - check location data');
      }
    } catch (error) {
      toast.error('Failed to upload asset inventory');
      console.error('Upload error:', error);
    } finally {
      setIsUploading(false);
    }
  }, [projectId]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
    },
    maxFiles: 1,
    disabled: isUploading,
  });

  const handleDownloadTemplate = async () => {
    try {
      const response = await apiClient.download_asset_template();
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'asset_inventory_template.csv';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success('Template downloaded');
    } catch (error) {
      toast.error('Failed to download template');
      console.error('Download error:', error);
    }
  };

  return (
    <div className="space-y-6">
      {/* Instructions */}
      <Alert>
        <AlertDescription>
          Upload your asset inventory CSV to merge hardware details (serial numbers, asset tags,
          manufacturer, model) with the schematic extraction. This step is optional but recommended
          for production deployments.
        </AlertDescription>
      </Alert>

      {/* Download Template Button */}
      <div className="flex justify-end">
        <Button variant="outline" size="sm" onClick={handleDownloadTemplate}>
          <Download className="w-4 h-4 mr-2" />
          Download CSV Template
        </Button>
      </div>

      {/* Upload Zone */}
      <Card
        {...getRootProps()}
        className={`p-12 border-2 border-dashed transition-all cursor-pointer ${
          isDragActive
            ? 'border-primary bg-primary/5'
            : 'border-border hover:border-primary/50 hover:bg-accent/50'
        } ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center justify-center text-center space-y-4">
          {isUploading ? (
            <>
              <Upload className="w-12 h-12 text-primary animate-pulse" />
              <p className="text-lg font-medium">Uploading and matching...</p>
            </>
          ) : selectedFile ? (
            <>
              <FileText className="w-12 h-12 text-primary" />
              <p className="text-lg font-medium">{selectedFile.name}</p>
              <p className="text-sm text-muted-foreground">Drop a new file to replace</p>
            </>
          ) : (
            <>
              <Upload className="w-12 h-12 text-muted-foreground" />
              <div>
                <p className="text-lg font-medium mb-1">
                  Drag & drop your asset inventory CSV here
                </p>
                <p className="text-sm text-muted-foreground">or click to browse</p>
              </div>
              <p className="text-xs text-muted-foreground">
                CSV with columns: Site, Room, Row, Rack, U-Position, Serial Number, Asset Tag,
                Manufacturer, Model
              </p>
            </>
          )}
        </div>
      </Card>

      {/* Validation Results */}
      {uploadResult && (
        <div className="space-y-4">
          {/* Summary Cards */}
          <div className="grid grid-cols-3 gap-4">
            <Card className="p-6 border-l-4 border-l-green-500">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Matched</p>
                  <p className="text-3xl font-bold text-green-600">
                    {uploadResult.matchedCount}
                  </p>
                </div>
                <CheckCircle2 className="w-8 h-8 text-green-500" />
              </div>
            </Card>

            <Card className="p-6 border-l-4 border-l-orange-500">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Unmatched Schematic</p>
                  <p className="text-3xl font-bold text-orange-600">
                    {uploadResult.unmatchedSchematicDevices.length}
                  </p>
                </div>
                <AlertCircle className="w-8 h-8 text-orange-500" />
              </div>
            </Card>

            <Card className="p-6 border-l-4 border-l-red-500">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Unmatched Inventory</p>
                  <p className="text-3xl font-bold text-red-600">
                    {uploadResult.unmatchedInventoryDevices.length}
                  </p>
                </div>
                <XCircle className="w-8 h-8 text-red-500" />
              </div>
            </Card>
          </div>

          {/* Unmatched Devices */}
          {uploadResult.unmatchedSchematicDevices.length > 0 && (
            <Card className="p-6">
              <h3 className="font-semibold mb-3 flex items-center">
                <AlertCircle className="w-5 h-5 text-orange-500 mr-2" />
                Schematic Devices Without Hardware Data ({uploadResult.unmatchedSchematicDevices.length})
              </h3>
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {uploadResult.unmatchedSchematicDevices.map((device, idx) => (
                  <div key={idx} className="text-sm text-muted-foreground">
                    • {device}
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Unmatched Inventory */}
          {uploadResult.unmatchedInventoryDevices.length > 0 && (
            <Card className="p-6">
              <h3 className="font-semibold mb-3 flex items-center">
                <XCircle className="w-5 h-5 text-red-500 mr-2" />
                Inventory Items Not Found in Schematic ({uploadResult.unmatchedInventoryDevices.length})
              </h3>
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {uploadResult.unmatchedInventoryDevices.map((item, idx) => (
                  <div key={idx} className="text-sm text-muted-foreground">
                    • {item.rack}/{item.uPosition}: {item.serialNumber} ({item.manufacturer})
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex justify-between pt-6">
        <Button variant="outline" onClick={onSkip}>
          Skip (Process Without Asset Data)
        </Button>
        <Button
          onClick={onComplete}
          disabled={!uploadResult && !selectedFile}
        >
          Continue to Processing
        </Button>
      </div>
    </div>
  );
}

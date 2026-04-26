import React, { useState } from "react";
import { Button } from "../components/Button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "../extensions/shadcn/components/card";
import { Badge } from "../extensions/shadcn/components/badge";
import { Upload, FileText, Loader2, CheckCircle, AlertTriangle, XCircle, DollarSign, Calculator } from "lucide-react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import { Navigate, useNavigate } from "react-router-dom";

interface CostEstimate {
  tier: string;
  monthly_cost: number;
  gpus_included: number;
}

interface ValidationResponse {
  valid: boolean;
  gpu_count: number;
  switch_count: number;
  warnings: string[];
  errors: string[];
  cost_estimation: CostEstimate;
  compatibility_score: number;
}

export default function DesignCalculator() {
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<ValidationResponse | null>(null);
  const navigate = useNavigate();

  const onDrop = async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;

    const file = acceptedFiles[0];
    setIsUploading(true);
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      // Direct fetch to backend since API client might not be regenerated yet
      const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
      const response = await fetch(`${API_URL}/preflight/validate-design`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Validation failed");
      }

      const data: ValidationResponse = await response.json();
      setResult(data);
      toast.success("BOM Validated successfully");

    } catch (error) {
      console.error("Error validating design:", error);
      toast.error("Failed to validate design. Ensure backend is running.");
    } finally {
      setIsUploading(false);
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "text/csv": [".csv"],
      "application/vnd.ms-excel": [".xls", ".xlsx"]
    },
    maxSize: 10 * 1024 * 1024, // 10MB
    multiple: false,
    disabled: isUploading,
  });

  return (
    <div className="min-h-screen bg-black text-gray-100 flex flex-col pt-12">
      <div className="max-w-4xl mx-auto w-full px-6">
        
        <div className="text-center mb-10">
          <Badge variant="outline" className="mb-4 text-cyan-400 border-cyan-800">PRE-FLIGHT DESIGNER</Badge>
          <h1 className="text-4xl font-bold font-mono tracking-tight mb-4 text-white flex items-center justify-center gap-3">
            <Calculator className="w-8 h-8 text-cyan-500" />
            AI Factory Build Calculator
          </h1>
          <p className="text-gray-400 text-lg">
            Upload your BOM (Bill of Materials) CSV to validate topology compatibility and estimate your SaaS tier pricing.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          
          <Card className="border-gray-800 bg-gray-900 shadow-xl">
            <CardHeader>
              <CardTitle className="text-white">Upload Design Specifications</CardTitle>
              <CardDescription>We accept generic CSV BOM exports.</CardDescription>
            </CardHeader>
            <CardContent>
              <div
                {...getRootProps()}
                className={`border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-all ${
                  isDragActive
                    ? 'border-cyan-500 bg-cyan-950/20'
                    : 'border-gray-700 hover:border-cyan-500/50 hover:bg-gray-800'
                } ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <input {...getInputProps()} />
                {isUploading ? (
                  <div className="flex flex-col items-center">
                    <Loader2 className="w-10 h-10 text-cyan-500 animate-spin mb-4" />
                    <p className="text-md font-medium text-white">Analyzing Topology...</p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center">
                    <Upload className="w-10 h-10 text-gray-400 mb-4" />
                    {isDragActive ? (
                      <p className="text-md font-medium text-white">Drop the CSV here...</p>
                    ) : (
                      <div>
                        <p className="text-md font-medium mb-1 text-white">Drag & drop your BOM file</p>
                        <p className="text-xs text-gray-500">
                          CSV format • Max 10MB
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          <Card className={`border-gray-800 shadow-xl transition-all duration-500 ${result ? 'bg-gray-900 border-cyan-900' : 'bg-gray-900/50'}`}>
            <CardHeader>
              <CardTitle className="text-white flex items-center justify-between">
                <span>Validation Results</span>
                {result && (
                  <Badge variant={result.valid ? 'default' : 'destructive'} className={result.valid ? 'bg-emerald-600' : ''}>
                    {result.valid ? 'PASSED' : 'FAILED'}
                  </Badge>
                )}
              </CardTitle>
              <CardDescription>Compatibility Score & Cost Estimates</CardDescription>
            </CardHeader>
            <CardContent>
              {!result ? (
                <div className="flex flex-col items-center justify-center h-48 text-gray-500 border border-dashed border-gray-800 rounded-lg">
                  <FileText className="w-8 h-8 mb-2 opacity-50" />
                  <p className="text-sm">Upload a design to view analysis.</p>
                </div>
              ) : (
                <div className="space-y-6">
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-black border border-gray-800 rounded-lg p-4 flex flex-col items-center justify-center">
                      <span className="text-xs text-gray-500 font-mono mb-1">COMPATIBILITY SCORE</span>
                      <span className={`text-3xl font-bold font-mono ${result.compatibility_score > 80 ? 'text-emerald-400' : result.compatibility_score > 40 ? 'text-amber-400' : 'text-red-400'}`}>
                        {result.compatibility_score}/100
                      </span>
                    </div>
                    <div className="bg-black border border-gray-800 rounded-lg p-4 flex flex-col items-center justify-center">
                      <span className="text-xs text-gray-500 font-mono mb-1">TOTAL HARDWARE</span>
                      <span className="text-2xl font-bold font-mono text-white">
                        {result.gpu_count} <span className="text-sm text-gray-500 font-sans">GPUs</span>
                      </span>
                      <span className="text-md font-bold font-mono text-white">
                        {result.switch_count} <span className="text-xs text-gray-500 font-sans">Switches</span>
                      </span>
                    </div>
                  </div>

                  <div className="bg-black border border-cyan-900/50 rounded-lg p-5">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-gray-400">Recommended SaaS Tier:</span>
                      <Badge variant="outline" className="text-cyan-400 border-cyan-800">
                        {result.cost_estimation.tier}
                      </Badge>
                    </div>
                    <div className="flex items-end gap-2">
                      <DollarSign className="w-6 h-6 text-emerald-500 mb-1" />
                      <span className="text-4xl font-bold text-white tracking-tight">
                        {result.cost_estimation.monthly_cost.toLocaleString()}
                      </span>
                      <span className="text-gray-500 mb-1">/ mo</span>
                    </div>
                    <p className="text-xs text-gray-500 mt-3 pt-3 border-t border-gray-800">
                      Covers full automated orchestration for up to {result.cost_estimation.gpus_included} GPUs.
                    </p>
                  </div>

                  {result.errors.length > 0 && (
                    <div className="bg-red-950/30 border border-red-900/50 rounded-lg p-4">
                      <div className="flex items-center gap-2 text-red-400 font-medium mb-2">
                        <XCircle className="w-4 h-4" /> Errors
                      </div>
                      <ul className="text-sm text-red-200/80 space-y-1 ml-6 list-disc">
                        {result.errors.map((e, idx) => <li key={idx}>{e}</li>)}
                      </ul>
                    </div>
                  )}

                  {result.warnings.length > 0 && (
                    <div className="bg-amber-950/30 border border-amber-900/50 rounded-lg p-4">
                      <div className="flex items-center gap-2 text-amber-500 font-medium mb-2">
                        <AlertTriangle className="w-4 h-4" /> Warnings
                      </div>
                      <ul className="text-sm text-amber-200/80 space-y-1 ml-6 list-disc">
                        {result.warnings.map((w, idx) => <li key={idx}>{w}</li>)}
                      </ul>
                    </div>
                  )}

                </div>
              )}
            </CardContent>
            {result && result.valid && (
              <CardFooter className="bg-gray-900/50 border-t border-gray-800 rounded-b-lg">
                 <Button 
                    className="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-medium"
                    onClick={() => navigate("/register")}
                 >
                   Proceed to SaaS Checkout
                 </Button>
              </CardFooter>
            )}
          </Card>

        </div>
      </div>
    </div>
  );
}

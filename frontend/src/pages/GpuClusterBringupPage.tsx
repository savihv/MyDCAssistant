import React from "react";
import { useState, useEffect } from 'react';
import { UploadZone } from "../components/UploadZone";
import { LegendConfiguration } from "../components/LegendConfiguration";
import { AssetInventoryUpload } from "../components/AssetInventoryUpload";
import { ResultsView } from "../components/ResultsView";
import { ProvisioningAlertsDashboard } from "../components/ProvisioningAlertsDashboard";
import { Card } from "../extensions/shadcn/components/card";
import { Badge } from "../extensions/shadcn/components/badge";
import { Button } from "../components/Button";
import { CheckCircle2, Circle, Loader2, XCircle, Shield } from 'lucide-react';
import { apiClient } from "../app";
import { ProcessingStatusResponse } from "../apiclient/data-contracts";

type Step = 'upload' | 'configure' | 'asset-upload' | 'processing' | 'results' | 'provisioning';

interface StepIndicatorProps {
  currentStep: Step;
}

function StepIndicator({ currentStep }: StepIndicatorProps) {
  const steps = [
    { id: 'upload', label: 'Upload Schematic' },
    { id: 'configure', label: 'Configure Legend' },
    { id: 'asset-upload', label: 'Asset Inventory' },
    { id: 'processing', label: 'Processing' },
    { id: 'results', label: 'View Results' },
    { id: 'provisioning', label: 'Day 1 Provisioning' },
  ];

  const stepIndex = steps.findIndex((s) => s.id === currentStep);

  return (
    <div className="mb-8">
      <div className="flex items-center justify-between max-w-4xl mx-auto">
        {steps.map((step, index) => (
          <div key={step.id} className="flex items-center flex-1">
            <div className="flex flex-col items-center flex-1">
              <div
                className={`w-10 h-10 rounded-full flex items-center justify-center border-2 ${
                  index < stepIndex
                    ? 'bg-primary border-primary text-primary-foreground'
                    : index === stepIndex
                    ? 'border-primary text-primary'
                    : 'border-border text-muted-foreground'
                }`}
              >
                {index < stepIndex ? (
                  <CheckCircle2 className="w-5 h-5" />
                ) : index === stepIndex ? (
                  <Circle className="w-5 h-5 fill-current" />
                ) : (
                  <Circle className="w-5 h-5" />
                )}
              </div>
              <span
                className={`mt-2 text-sm font-medium ${
                  index <= stepIndex ? 'text-foreground' : 'text-muted-foreground'
                }`}
              >
                {step.label}
              </span>
            </div>
            {index < steps.length - 1 && (
              <div
                className={`h-0.5 flex-1 mx-4 ${
                  index < stepIndex ? 'bg-primary' : 'bg-border'
                }`}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function GpuClusterBringupPage() {
  const [currentStep, setCurrentStep] = useState<Step>('upload');
  const [projectId, setProjectId] = useState<string | null>(null);
  const [schematicUrl, setSchematicUrl] = useState<string | null>(null);

  const handleUpload = (uploadedProjectId: string, uploadedSchematicUrl: string) => {
    setProjectId(uploadedProjectId);
    setSchematicUrl(uploadedSchematicUrl);
    setCurrentStep('configure');
  };

  const handleConfigurationComplete = () => {
    setCurrentStep('asset-upload');
  };

  const handleAssetUploadComplete = () => {
    setCurrentStep('processing');
  };

  const handleProcessingComplete = () => {
    setCurrentStep('results');
  };

  const handleViewProvisioning = () => {
    setCurrentStep('provisioning');
  };

  const handleBackToResults = () => {
    setCurrentStep('results');
  };

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-foreground mb-2">
                GPU Cluster Bringup
              </h1>
              <p className="text-muted-foreground">
                Transform your data center schematic into a deployment-ready cabling matrix
              </p>
            </div>
            {projectId && (
              <Badge variant="outline">
                Project: {projectId}
              </Badge>
            )}
          </div>
        </div>

        {/* Step Indicator */}
        <StepIndicator currentStep={currentStep} />

        {/* Step Content */}
        <div className="max-w-5xl mx-auto">
          {currentStep === 'upload' && (
            <Card className="p-8">
              <div className="mb-6">
                <h2 className="text-2xl font-semibold mb-2">Upload Your Schematic</h2>
                <p className="text-muted-foreground">
                  Upload a data center layout diagram showing compute nodes, storage arrays, and
                  network connections. We support PDF, PNG, JPG, and SVG formats.
                </p>
              </div>
              <UploadZone onUpload={handleUpload} />
            </Card>
          )}

          {currentStep === 'configure' && projectId && (
            <Card className="p-8">
              <div className="mb-6">
                <h2 className="text-2xl font-semibold mb-2">Configure Processing</h2>
                <p className="text-muted-foreground">
                  Define the color legend and device naming conventions used in your schematic.
                  This helps our AI accurately extract the topology.
                </p>
              </div>
              <LegendConfiguration
                projectId={projectId}
                onComplete={handleConfigurationComplete}
              />
            </Card>
          )}

          {currentStep === 'asset-upload' && projectId && (
            <Card className="p-8">
              <div className="mb-6">
                <h2 className="text-2xl font-semibold mb-2">Upload Asset Inventory</h2>
                <p className="text-muted-foreground">
                  Upload a CSV file containing your data center's asset inventory.
                  This helps our AI match devices in the schematic to real-world assets.
                </p>
              </div>
              <AssetInventoryUpload
                projectId={projectId}
                onComplete={handleAssetUploadComplete}
                onSkip={handleAssetUploadComplete}
              />
            </Card>
          )}

          {currentStep === 'processing' && projectId && (
            <ProcessingScreen projectId={projectId} onComplete={handleProcessingComplete} />
          )}

          {currentStep === 'results' && projectId && (
            <Card className="p-8">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-semibold">Extraction Results</h2>
                <Button onClick={handleViewProvisioning} className="flex items-center gap-2">
                  <Shield className="w-4 h-4" />
                  Day 1 Provisioning
                </Button>
              </div>
              <ResultsView projectId={projectId} />
            </Card>
          )}

          {currentStep === 'provisioning' && projectId && (
            <Card className="p-8">
              <div className="mb-6">
                <Button onClick={handleBackToResults} variant="outline" size="sm">
                  ← Back to Results
                </Button>
              </div>
              <ProvisioningAlertsDashboard projectId={projectId} />
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

// Processing screen with real-time polling
function ProcessingScreen({ projectId, onComplete }: { projectId: string; onComplete: () => void }) {
  const [status, setStatus] = useState<ProcessingStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let pollInterval: any;

    const pollStatus = async () => {
      try {
        const response = await apiClient.get_processing_status({ projectId: projectId });
        const resAny = response as any;
        const data: ProcessingStatusResponse = resAny.data ? resAny.data : (resAny.json ? await resAny.json() : resAny);
        setStatus(data);

        if (data.status === 'completed') {
          clearInterval(pollInterval);
          setTimeout(() => {
            onComplete();
          }, 1000);
        } else if (data.status === 'failed') {
          clearInterval(pollInterval);
          setError(data.error_message || 'Processing failed');
        }
      } catch (err) {
        console.error('Polling error:', err);
      }
    };

    // Poll every 2 seconds
    pollStatus();
    pollInterval = setInterval(pollStatus, 2000);

    return () => {
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [projectId, onComplete]);

  const currentStage = status?.current_stage || 'Initializing';
  const progress = status?.progress_percentage || 0;

  const stages = [
    { name: 'Loading schematic', threshold: 10 },
    { name: 'Extracting devices', threshold: 50 },
    { name: 'Extracting connections', threshold: 80 },
    { name: 'Validating topology', threshold: 100 },
  ];

  if (error) {
    return (
      <Card className="p-12">
        <div className="text-center">
          <XCircle className="w-16 h-16 mx-auto mb-6 text-red-500" />
          <h2 className="text-2xl font-semibold mb-2 text-red-500">Processing Failed</h2>
          <p className="text-muted-foreground mb-6">{error}</p>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-12">
      <div className="text-center">
        <Loader2 className="w-16 h-16 mx-auto mb-6 text-primary animate-spin" />
        <h2 className="text-2xl font-semibold mb-2">Processing Your Schematic</h2>
        <p className="text-muted-foreground mb-6">
          Our AI is analyzing your diagram to extract devices and connections.
          This may take a few minutes...
        </p>
        <div className="max-w-md mx-auto mb-6">
          <div className="space-y-3 text-left text-sm text-muted-foreground">
            {stages.map((stage) => {
              const isComplete = progress >= stage.threshold;
              const isActive = progress < stage.threshold && progress >= (stages[stages.indexOf(stage) - 1]?.threshold || 0);

              return (
                <div key={stage.name} className="flex items-center gap-2">
                  {isComplete ? (
                    <CheckCircle2 className="w-4 h-4 text-green-500" />
                  ) : isActive ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Circle className="w-4 h-4" />
                  )}
                  <span>{stage.name}</span>
                </div>
              );
            })}
          </div>
        </div>
        <div className="max-w-md mx-auto">
          <div className="w-full bg-accent rounded-full h-2">
            <div
              className="bg-primary h-2 rounded-full transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="text-sm text-muted-foreground mt-2">{progress}% complete</p>
        </div>
      </div>
    </Card>
  );
}

import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { apiClient } from 'app';
import { toast } from 'sonner';
import { Upload, FileText, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

export interface Props {
  onUpload: (projectId: string, schematicUrl: string) => void;
}

export function UploadZone({ onUpload }: Props) {
  const [isUploading, setIsUploading] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) return;

      const file = acceptedFiles[0];
      setIsUploading(true);

      // Create preview for images
      if (file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = (e) => {
          setPreview(e.target?.result as string);
        };
        reader.readAsDataURL(file);
      }

      try {
        const response = await apiClient.upload_schematic_file({ schematic_file: file as any } as any);
        
        // Safely extract from either native Fetch Response or Apiclient wrapper
        const resAny = response as any;
        const data = resAny.data ? resAny.data : (resAny.json ? await resAny.json() : resAny);

        toast.success('Schematic uploaded successfully');
        onUpload(data.project_id || data.projectId, data.schematic_url);
      } catch (error) {
        toast.error('Upload failed. Please try again.');
        console.error('Upload error:', error);
        setPreview(null);
      } finally {
        setIsUploading(false);
      }
    },
    [onUpload]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/png': ['.png'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/svg+xml': ['.svg'],
    },
    maxSize: 50 * 1024 * 1024, // 50MB
    multiple: false,
    disabled: isUploading,
  });

  if (preview) {
    return (
      <div className="space-y-4">
        <div className="border border-border rounded-lg p-4 bg-card">
          <div className="flex items-start gap-4">
            <FileText className="w-8 h-8 text-primary flex-shrink-0" />
            <div className="flex-1">
              <p className="font-medium mb-1">Schematic Preview</p>
              <p className="text-sm text-muted-foreground">File uploaded successfully</p>
            </div>
          </div>
          {preview.startsWith('data:image') && (
            <img
              src={preview}
              alt="Schematic preview"
              className="mt-4 max-h-64 rounded border border-border"
            />
          )}
        </div>
        <Button
          variant="outline"
          onClick={() => {
            setPreview(null);
          }}
          className="w-full"
        >
          Upload Different File
        </Button>
      </div>
    );
  }

  return (
    <div
      {...getRootProps()}
      className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-all ${
        isDragActive
          ? 'border-primary bg-primary/5'
          : 'border-border hover:border-primary/50 hover:bg-accent/50'
      } ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      <input {...getInputProps()} />
      {isUploading ? (
        <div className="flex flex-col items-center">
          <Loader2 className="w-12 h-12 text-primary animate-spin mb-4" />
          <p className="text-lg font-medium">Uploading schematic...</p>
          <p className="text-sm text-muted-foreground mt-2">Please wait</p>
        </div>
      ) : (
        <div className="flex flex-col items-center">
          <Upload className="w-12 h-12 text-muted-foreground mb-4" />
          {isDragActive ? (
            <p className="text-lg font-medium">Drop the schematic here...</p>
          ) : (
            <div>
              <p className="text-lg font-medium mb-2">Drag & drop your data center schematic</p>
              <p className="text-sm text-muted-foreground mb-4">
                or click to browse your files
              </p>
              <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
                <span className="px-2 py-1 bg-accent rounded">PDF</span>
                <span className="px-2 py-1 bg-accent rounded">PNG</span>
                <span className="px-2 py-1 bg-accent rounded">JPG</span>
                <span className="px-2 py-1 bg-accent rounded">SVG</span>
                <span className="text-muted-foreground">• Max 50MB</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

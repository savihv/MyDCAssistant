import React, { useState, useRef } from "react";
import { Button } from "./Button";

interface Props {
  onFilesChanged?: (files: FileWithPreview[]) => void;
  acceptedFileTypes: string;
  maxFiles: number;
  maxFileSize: number; // in MB
  isMultiple: boolean;
  fileType: 'image' | 'video';
}

interface FileWithPreview extends File {
  preview?: string;
  id: string;
}

export function FileUploader({
  acceptedFileTypes,
  maxFiles,
  maxFileSize,
  isMultiple,
  fileType,
  onFilesChanged
}: Props) {
  const [files, setFiles] = useState<FileWithPreview[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    processFiles(selectedFiles);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);

    const droppedFiles = Array.from(e.dataTransfer.files);
    processFiles(droppedFiles);
  };

  const processFiles = (selectedFiles: File[]) => {
    setError(null);

    // Filter files by type
    const validTypeFiles = selectedFiles.filter(file => {
      const isValidType = file.type.startsWith(fileType === 'image' ? 'image/' : 'video/');
      if (!isValidType) setError(`Only ${fileType} files are allowed`);
      return isValidType;
    });

    // Check file size
    const validSizeFiles = validTypeFiles.filter(file => {
      const isValidSize = file.size <= maxFileSize * 1024 * 1024;
      if (!isValidSize) setError(`File size must be less than ${maxFileSize}MB`);
      return isValidSize;
    });

    // Check max files
    if (files.length + validSizeFiles.length > maxFiles) {
      setError(`You can only upload up to ${maxFiles} ${fileType}${maxFiles > 1 ? 's' : ''}`);
      return;
    }

    // Add previews to files
    const filesWithPreviews = validSizeFiles.map(file => {
      const preview = URL.createObjectURL(file);
      return Object.assign(file, {
        preview,
        id: Math.random().toString(36).substring(2, 9)
      });
    });

    let updatedFiles: FileWithPreview[];
    if (isMultiple) {
      updatedFiles = [...files, ...filesWithPreviews];
      setFiles(updatedFiles);
    } else {
      updatedFiles = filesWithPreviews;
      setFiles(updatedFiles);
    }

    // Call the callback if provided
    if (onFilesChanged) {
      onFilesChanged(updatedFiles);
    }
  };

  const removeFile = (id: string) => {
    setFiles(prevFiles => {
      const updatedFiles = prevFiles.filter(file => file.id !== id);
      return updatedFiles;
    });
  };

  const triggerFileInput = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="mb-6">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-lg p-4 transition-colors ${isDragging ? 'border-blue-500 bg-gray-700/30' : 'border-gray-600'}`}
      >
        <div className="text-center p-6">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="mx-auto h-12 w-12 text-gray-400 mb-3"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            {fileType === 'image' ? (
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            ) : (
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
              />
            )}
          </svg>
          <p className="mb-2 text-sm text-gray-300">
            <span className="font-semibold">Click to upload</span> or drag and drop
          </p>
          <p className="text-xs text-gray-400">
            {fileType === 'image' ? 'PNG, JPG or GIF' : 'MP4, MOV or AVI'} up to {maxFileSize}MB
          </p>
          <Button
            onClick={triggerFileInput}
            variant="outline"
            className="mt-4"
          >
            Select {fileType}
          </Button>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept={acceptedFileTypes}
          onChange={handleFileChange}
          multiple={isMultiple}
          className="hidden"
        />
      </div>

      {error && (
        <div className="mt-2 text-red-500 text-sm">{error}</div>
      )}

      {files.length > 0 && (
        <div className="mt-4">
          <h4 className="text-sm font-medium mb-2 text-gray-300">
            Uploaded {fileType}s ({files.length}/{maxFiles})
          </h4>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {files.map((file) => (
              <div key={file.id} className="relative rounded-md overflow-hidden group">
                {fileType === 'image' ? (
                  <img
                    src={file.preview}
                    alt={file.name}
                    className="h-24 w-full object-cover"
                  />
                ) : (
                  <div className="h-24 w-full bg-gray-700 flex items-center justify-center">
                    <video
                      src={file.preview}
                      className="h-full w-full object-cover"
                      controls
                    />
                  </div>
                )}
                <button
                  onClick={() => removeFile(file.id)}
                  className="absolute top-1 right-1 bg-red-500 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className="h-4 w-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
                <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-60 px-2 py-1 text-xs truncate">
                  {file.name}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

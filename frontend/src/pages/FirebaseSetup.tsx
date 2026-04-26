import React from 'react';
import { Card } from "../extensions/shadcn/components/card";
import { firestoreRules, storageRules, setupInstructions } from "../utils/firebaseSecurityRules";

interface CodeBlockProps {
  title: string;
  code: string;
  language?: string;
}

const CodeBlock: React.FC<CodeBlockProps> = ({ title, code, language = 'text' }) => {
  return (
    <div className="mb-6">
      <h3 className="text-xl font-semibold mb-2">{title}</h3>
      <div className="bg-gray-800 p-4 rounded-md overflow-auto">
        <pre className="text-gray-200 text-sm">
          <code>{code}</code>
        </pre>
      </div>
    </div>
  );
};

export default function FirebaseSetupPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6">Firebase Setup Guide</h1>
      
      <Card className="mb-8 p-6">
        <h2 className="text-2xl font-semibold mb-4">Security Rules Configuration</h2>
        <p className="mb-4">
          To secure your Firebase project, copy and paste these rules into the Firebase Console.
          These rules ensure that users can only access their own data and prevent unauthorized access.
        </p>
        
        <CodeBlock title="Firestore Rules" code={firestoreRules} />
        
        <CodeBlock title="Storage Rules" code={storageRules} />
      </Card>
      
      <Card className="p-6">
        <h2 className="text-2xl font-semibold mb-4">Setup Instructions</h2>
        <div className="whitespace-pre-line">
          {setupInstructions}
        </div>
      </Card>
    </div>
  );
}

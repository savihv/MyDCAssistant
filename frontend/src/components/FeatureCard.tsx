import React from "react";

interface Props {
  icon: React.ReactNode;
  title: string;
  description: string;
}

export function FeatureCard({ icon, title, description }: Props) {
  return (
    <div className="flex flex-col items-center p-6 bg-gray-800 rounded-lg shadow-md">
      <div className="text-blue-500 text-3xl mb-4">{icon}</div>
      <h3 className="text-xl font-bold text-white mb-2">{title}</h3>
      <p className="text-gray-300 text-center">{description}</p>
    </div>
  );
}

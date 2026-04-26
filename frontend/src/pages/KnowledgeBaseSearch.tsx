import React from "react";
import { useNavigate } from "react-router-dom";
import { KnowledgeSearch } from "../components/KnowledgeSearch";
import { Button } from "../components/Button";
import { JuniorTechBotLogo } from "../components/JuniorTechBotLogo";

export default function KnowledgeBaseSearch() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gray-900 text-white flex flex-col">
      {/* Header */}
      <header className="bg-gray-800 shadow-md p-4">
        <div className="flex justify-between items-center">
          <div className="flex items-center">
            <JuniorTechBotLogo className="w-8 h-8 mr-2" />
            <h1 className="text-xl font-bold">
              <span className="text-white">Junior</span>
              <span className="text-blue-400">TechBot</span>
            </h1>
          </div>
          <nav>
            <ul className="flex items-center space-x-4">
              <li>
                <button onClick={() => navigate("/")} className="text-gray-300 hover:text-white">
                  Home
                </button>
              </li>
              <li>
                <button onClick={() => navigate("/SessionCreate")} className="text-gray-300 hover:text-white">
                  New Session
                </button>
              </li>
              <li>
                <button onClick={() => navigate("/History")} className="text-gray-300 hover:text-white">
                  History
                </button>
              </li>
              <li>
                {/* This is the current page, so it's highlighted */}
                <button onClick={() => navigate("/KnowledgeBaseSearch")} className="text-blue-400">
                  Knowledge Base Search
                </button>
              </li>
              <li>
                <button onClick={() => navigate("/ExpertSubmission")} className="text-gray-300 hover:text-white">
                  Expert Submission
                </button>
              </li>
            </ul>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-grow p-6">
        <div className="max-w-4xl mx-auto">
            <KnowledgeSearch />
        </div>
      </main>
    </div>
  );
}

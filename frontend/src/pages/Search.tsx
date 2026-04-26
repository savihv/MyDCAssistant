import React from "react";
import { useUserGuardContext } from "../app";
import { KnowledgeSearch } from "../components/KnowledgeSearch";

const SearchPage = () => {
  const { user } = useUserGuardContext();

  return (
    <div className="container mx-auto p-4">
      <header className="mb-8">
        <h1 className="text-4xl font-bold">Knowledge Base Search</h1>
        <p className="text-lg text-muted-foreground">
          Welcome, {user.email}. Use the tool below to search the knowledge base.
        </p>
      </header>

      <main>
        <KnowledgeSearch />
      </main>

      <footer className="mt-8 text-center text-sm text-muted-foreground">
        <p>TechTalk Assistant</p>
      </footer>
    </div>
  );
};

export default SearchPage;

// frontend/src/app/projects/[projectId]/agent1/page.tsx
// NO 'use client' for this test if possible

interface Agent1PageProps {
  params: {
    projectId: string; // This should match the folder name [projectId]
  };
  searchParams?: { [key: string]: string | string[] | undefined }; // Optional, good practice to include
}

export default function Agent1Page({ params, searchParams }: Agent1PageProps) {
  return (
    <div>
      <h1>Test Agent 1 Page</h1>
      <p>Project ID from props: {params.projectId}</p>
      {searchParams && Object.keys(searchParams).length > 0 && (
        <div>
          <h2>Search Params:</h2>
          <pre>{JSON.stringify(searchParams, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

// If it MUST be a client component:
// frontend/src/app/projects/[projectId]/agent1/page.tsx
'use client';

import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react'; // Example imports

export default function Agent1Page() { // NO params in props
  const params = useParams();
  const [projectId, setProjectId] = useState<string | null>(null);

  useEffect(() => {
    if (params.projectId) {
      const id = Array.isArray(params.projectId) ? params.projectId[0] : params.projectId;
      setProjectId(id);
    }
  }, [params.projectId]);

  if (!projectId) {
    return <div>Loading project ID...</div>;
  }

  return (
    <div>
      <h1>Test Agent 1 Page (Client Component)</h1>
      <p>Project ID from useParams hook: {projectId}</p>
    </div>
  );
}

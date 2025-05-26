// frontend/src/app/projects/[projectId]/agent1/page.tsx
'use client';

import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react'; // React itself is usually implicitly available or imported once.

export default function Agent1Page() {
  console.log('--- Agent1Page START OF RENDER ---'); // For browser console

  // Get params using the hook.
  // The key 'projectId' in params object comes from your folder name [projectId].
  const paramsFromHook = useParams<{ projectId: string }>(); // Explicitly type what you expect
  
  console.log('--- Agent1Page paramsFromHook:', paramsFromHook); // For browser console

  const [displayProjectId, setDisplayProjectId] = useState<string | null>(null);

  useEffect(() => {
    // paramsFromHook.projectId will be a string or string[] or undefined
    // depending on the route structure and if it's a catch-all. For [projectId], it's string.
    if (paramsFromHook && paramsFromHook.projectId) {
      // No need to check Array.isArray for a simple [projectId] segment,
      // it should directly be a string.
      setDisplayProjectId(paramsFromHook.projectId);
      console.log('--- Agent1Page useEffect, projectId set to:', paramsFromHook.projectId); // For browser console
    } else {
      console.log('--- Agent1Page useEffect, paramsHook.projectId is not available yet or is missing.');
    }
  }, [paramsFromHook]); // Depend on the whole params object or the specific key

  if (!displayProjectId) {
    console.log('--- Agent1Page rendering: Loading project ID... ---');
    return <div>Loading project ID (Client)...</div>;
  }

  console.log('--- Agent1Page rendering: Displaying page with projectId:', displayProjectId, '---');
  return (
    <div>
      <h1>Test Agent 1 Page (Client Component)</h1>
      <p>Project ID from useParams hook: {displayProjectId}</p>
    </div>
  );
}

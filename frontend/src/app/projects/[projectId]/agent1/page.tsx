// frontend/src/app/projects/[projectId]/agent1/page.tsx
'use client'; // Keep if you use client hooks, remove if not needed for this simple test

// import { useParams } from 'next/navigation'; // Keep if using params

export default function Agent1Page({ params }: { params: { projectId: string } }) {
  // const paramsFromHook = useParams(); // Alternative way to get params
  // const projectId = Array.isArray(paramsFromHook.projectId) ? paramsFromHook.projectId[0] : paramsFromHook.projectId;

  return (
    <div>
      <h1>Test Agent 1 Page</h1>
      <p>Project ID from props: {params.projectId}</p>
      {/* <p>Project ID from hook: {projectId}</p> */}
    </div>
  );
}

// frontend/src/app/projects/[projectId]/layout.tsx:
'use client'

import Link from 'next/link'
import { useParams, usePathname } from 'next/navigation'
import { useProjects } from '@/context/ProjectsContext'
import { Button } from '@/components/ui/button'
import { ArrowLeft, Bot, Combine, FileText, ChevronRight } from 'lucide-react';
import { cn } from "@/lib/utils";

export default function ProjectLayout({
  children,
}: {
  children: React.ReactNode
}) {
  console.log('--- ProjectLayout START OF RENDER ---');

  const paramsFromHook = useParams(); // Use a different name to avoid confusion with props if this were a server component
  const pathname = usePathname();
  const { getProject, projects: contextProjects, isLoading: contextIsLoading } = useProjects(); // Get projects array too

  console.log('--- ProjectLayout paramsFromHook:', paramsFromHook);
  console.log('--- ProjectLayout pathname:', pathname);
  console.log('--- ProjectLayout contextProjects (length):', contextProjects.length, 'isLoading:', contextIsLoading);


  const rawProjectId = paramsFromHook.projectId;
  const projectId = typeof rawProjectId === 'string' ? rawProjectId : (Array.isArray(rawProjectId) ? rawProjectId[0] : '');
  
  console.log('--- ProjectLayout determined projectId:', projectId);

  const project = projectId ? getProject(projectId) : null;

  console.log('--- ProjectLayout project from getProject:', project);

  // Define navigation items for better structure and easier rendering
  const navItems = projectId ? [ // Only define if projectId is available
    { href: `/projects/${projectId}/agent1`, label: 'Harvest', icon: Combine },
    { href: `/projects/${projectId}/agent2`, label: 'Extract', icon: Bot },
    { href: `/projects/${projectId}/agent3`, label: 'Report', icon: FileText },
  ] : [];

  if (!projectId && !contextIsLoading) {
     // This case might happen if useParams hasn't resolved yet, or if the route is invalid.
     // Or if context is still loading projects that might contain this one.
     console.log('--- ProjectLayout: projectId not yet available, or invalid route. Context isLoading:', contextIsLoading);
     // Potentially return a loading state or null if it's too early to render meaningfully
     // return <div>Loading project context...</div>; // Be careful with returning null from layout
  }
  
  // You could add a loading state here if `project` is null and `contextIsLoading` is true
  // or if `projectId` is available but `project` is still null (meaning getProject didn't find it yet).
  // For now, let the existing logic proceed.

  console.log('--- ProjectLayout RENDERING UI ---');
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 p-4 sm:p-6 lg:p-8">
      {/* ... rest of your layout JSX ... */}
      {/* Ensure all uses of `project?.name` are safe if project can be null */}
      <header className="bg-white dark:bg-gray-900 shadow-sm rounded-xl p-4 sm:p-6 border border-gray-100 dark:border-gray-800">
       <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
         <div className="flex items-center space-x-4">
           <Link href="/projects">
             <Button variant="outline" size="icon" aria-label="Back to projects list" className="flex-shrink-0 border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-800">
               <ArrowLeft className="h-4 w-4" />
             </Button>
           </Link>
           <div className="min-w-0">
             <div className="flex items-center text-sm text-gray-500 dark:text-gray-400 mb-1">
               <Link href="/projects" className="hover:underline">Projects</Link>
               <ChevronRight className="h-4 w-4 mx-1 text-gray-400" />
               <span className="font-medium text-gray-700 dark:text-gray-300 truncate" title={project?.name || projectId || ''}>
                 {project ? project.name : (projectId ? `Project (${projectId.substring(0,6)})...` : 'Loading project name...')}
               </span>
             </div>
             <h1 className="text-2xl font-bold text-gray-900 dark:text-white truncate">
               Project Dashboard
             </h1>
           </div>
         </div>
         {projectId && (
           <nav className="w-full sm:w-auto bg-gray-100 dark:bg-gray-800 p-1 rounded-lg flex items-center space-x-1 shadow-inner">
             {navItems.map((item) => {
               const isActive = pathname === item.href;
               return (
                 <Link key={item.href} href={item.href} className="flex-1 sm:flex-none">
                   <Button 
                     variant="ghost" 
                     size="sm" 
                     className={cn(
                       "w-full justify-center sm:justify-start text-sm font-medium transition-all duration-200 ease-in-out flex items-center px-4 py-2",
                       isActive 
                         ? "bg-white dark:bg-gray-900 text-blue-600 dark:text-blue-400 shadow-sm rounded-md"
                         : "text-gray-600 dark:text-gray-300 hover:bg-white/60 dark:hover:bg-gray-700/60 hover:text-gray-900 dark:hover:text-white"
                     )}
                   >
                     <item.icon className={cn("h-4 w-4 mr-2", isActive ? "text-blue-600 dark:text-blue-400" : "text-gray-400 dark:text-gray-500")} />
                     {item.label}
                   </Button>
                 </Link>
               );
             })}
           </nav>
         )}
       </div>
     </header>
      <main className="bg-white dark:bg-gray-900 shadow-sm rounded-xl p-6 sm:p-8 lg:p-10 border border-gray-100 dark:border-gray-800">
        {children} {/* This is where Agent1Page.tsx (minimal version) will render */}
      </main>
    </div>
  </div>
)
}

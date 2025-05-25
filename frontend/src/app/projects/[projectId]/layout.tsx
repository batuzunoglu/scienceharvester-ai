'use client'

import Link from 'next/link'
import { useParams, usePathname } from 'next/navigation'
import { useProjects } from '@/context/ProjectsContext'
import { Button } from '@/components/ui/button'
import { ArrowLeft, Bot, Combine, FileText, ChevronRight } from 'lucide-react';
import { cn } from "@/lib/utils"; // Make sure you have this utility or implement it

export default function ProjectLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const { projectId: rawProjectId } = useParams();
  const pathname = usePathname(); // Hook to get the current URL path
  const { getProject } = useProjects();

  const projectId = typeof rawProjectId === 'string' ? rawProjectId : (Array.isArray(rawProjectId) ? rawProjectId[0] : '');
  
  const project = projectId ? getProject(projectId) : null;

  // Define navigation items for better structure and easier rendering
  const navItems = [
    { href: `/projects/${projectId}/agent1`, label: 'Harvest', icon: Combine },
    { href: `/projects/${projectId}/agent2`, label: 'Extract', icon: Bot },
    { href: `/projects/${projectId}/agent3`, label: 'Report', icon: FileText },
  ];

  return (
    // Main container with a subtle background and padding
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 p-4 sm:p-6 lg:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        
        {/* Header Card */}
        <header className="bg-white dark:bg-gray-900 shadow-sm rounded-xl p-4 sm:p-6 border border-gray-100 dark:border-gray-800">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            
            {/* Left Section: Back Button & Breadcrumb/Title */}
            <div className="flex items-center space-x-4">
              <Link href="/projects">
                <Button 
                  variant="outline" 
                  size="icon" 
                  aria-label="Back to projects list" 
                  className="flex-shrink-0 border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-800"
                >
                  <ArrowLeft className="h-4 w-4" />
                </Button>
              </Link>
              <div className="min-w-0">
                {/* Breadcrumb for context */}
                <div className="flex items-center text-sm text-gray-500 dark:text-gray-400 mb-1">
                  <Link href="/projects" className="hover:underline">Projects</Link>
                  <ChevronRight className="h-4 w-4 mx-1 text-gray-400" />
                  <span className="font-medium text-gray-700 dark:text-gray-300 truncate" title={project?.name}>
                    {project ? project.name : (projectId ? `Project...` : 'Loading...')}
                  </span>
                </div>
                {/* Main Title (Could be dynamic based on active tab later if needed) */}
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white truncate">
                  Project Dashboard
                </h1>
              </div>
            </div>

            {/* Right Section: Tab-like Navigation */}
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
                          "w-full justify-center sm:justify-start text-sm font-medium transition-all duration-200 ease-in-out flex items-center px-4 py-2", // Added padding
                          isActive 
                            ? "bg-white dark:bg-gray-900 text-blue-600 dark:text-blue-400 shadow-sm rounded-md" // Active state with shadow
                            : "text-gray-600 dark:text-gray-300 hover:bg-white/60 dark:hover:bg-gray-700/60 hover:text-gray-900 dark:hover:text-white" // Inactive state
                        )}
                      >
                        <item.icon className={cn(
                            "h-4 w-4 mr-2", // Icon size and margin
                            isActive ? "text-blue-600 dark:text-blue-400" : "text-gray-400 dark:text-gray-500 group-hover:text-gray-600 dark:group-hover:text-gray-300" // Icon color
                        )} />
                        {item.label}
                      </Button>
                    </Link>
                  );
                })}
              </nav>
            )}
          </div>
        </header>

        {/* Main Content Card */}
        <main className="bg-white dark:bg-gray-900 shadow-sm rounded-xl p-6 sm:p-8 lg:p-10 border border-gray-100 dark:border-gray-800">
          {children}
        </main>
        
      </div>
    </div>
  )
}
// src/app/providers.tsx
'use client'

import { ReactNode } from 'react'
import { ProjectsProvider } from '@/context/ProjectsContext'

export function Providers({ children }: { children: ReactNode }) {
  return <ProjectsProvider>{children}</ProjectsProvider>
}
/**
 * React Query hooks for ScopePilot API.
 *
 * Each domain gets typed useQuery/useMutation hooks wrapping the API functions.
 * Pages import these instead of calling api functions directly in useEffect.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import * as auth from './auth'
import * as projects from './projects'
import * as sprints from './sprints'
import * as codebase from './codebase'
import * as apiTests from './api-tests'
import * as figma from './figma'
import * as team from './team'

// ── Keys ─────────────────────────────────────────────────────────────────
export const queryKeys = {
  me: ['me'] as const,
  projects: ['projects'] as const,
  project: (id: number) => ['projects', id] as const,
  sprints: (pid: number) => ['sprints', pid] as const,
  sprint: (id: number) => ['sprints', id] as const,
  analysis: (id: number) => ['analysis', id] as const,
  tickets: (sid: number) => ['tickets', sid] as const,
  codeSources: ['codeSources'] as const,
  repoSnapshot: (id: number) => ['repoSnapshots', id] as const,
  apiSpecs: ['apiSpecs'] as const,
  testPlans: (sid: number) => ['testPlans', sid] as const,
  figmaAnalyses: ['figmaAnalyses'] as const,
  members: ['members'] as const,
  billing: ['billing'] as const,
  usage: ['usage'] as const,
  sharedReports: ['sharedReports'] as const,
}

// ── Auth ─────────────────────────────────────────────────────────────────
export function useMe() {
  return useQuery({ queryKey: queryKeys.me, queryFn: auth.getMe })
}

// ── Projects ─────────────────────────────────────────────────────────────
export function useProjects() {
  return useQuery({ queryKey: queryKeys.projects, queryFn: projects.listProjects })
}
export function useProject(id: number) {
  return useQuery({ queryKey: queryKeys.project(id), queryFn: () => projects.getProject(id), enabled: !!id })
}
export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: projects.createProject, onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.projects }) })
}
export function useDeleteProject() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: projects.deleteProject, onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.projects }) })
}

// ── Sprints ──────────────────────────────────────────────────────────────
export function useSprints(projectId: number) {
  return useQuery({ queryKey: queryKeys.sprints(projectId), queryFn: () => sprints.listSprints(projectId), enabled: !!projectId })
}
export function useSprint(id: number) {
  return useQuery({ queryKey: queryKeys.sprint(id), queryFn: () => sprints.getSprint(id), enabled: !!id })
}
export function useImportSprint() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ project_id, sprint_name }: { project_id: number; sprint_name: string }) => sprints.importSprint(project_id, sprint_name), onSuccess: (_d, vars) => qc.invalidateQueries({ queryKey: queryKeys.sprints(vars.project_id) }) })
}
export function useTriggerAnalysis() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: (sprintId: number) => sprints.triggerAnalysis(sprintId), onSuccess: (_d, sprintId) => qc.invalidateQueries({ queryKey: queryKeys.sprint(sprintId) }) })
}
export function useTickets(sprintId: number) {
  return useQuery({ queryKey: queryKeys.tickets(sprintId), queryFn: () => sprints.listTickets(sprintId), enabled: !!sprintId })
}

// ── Code Sources ─────────────────────────────────────────────────────────
export function useCodeSources() {
  return useQuery({ queryKey: queryKeys.codeSources, queryFn: () => codebase.listCodeSources() })
}
export function useScanCodeSource() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: codebase.scanCodeSource, onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.codeSources }) })
}

// ── API Tests ────────────────────────────────────────────────────────────
export function useApiSpecs() {
  return useQuery({ queryKey: queryKeys.apiSpecs, queryFn: () => apiTests.listApiSpecs() })
}

// ── Figma ────────────────────────────────────────────────────────────────
export function useFigmaAnalyses() {
  return useQuery({ queryKey: queryKeys.figmaAnalyses, queryFn: () => figma.listFigmaAnalyses() })
}
export function useAnalyzeFigma() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ url, token }: { url: string; token: string }) => figma.analyzeFigmaDesign(url, token), onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.figmaAnalyses }) })
}

// ── Team ─────────────────────────────────────────────────────────────────
export function useMembers() {
  return useQuery({ queryKey: queryKeys.members, queryFn: team.listMembers })
}
export function useAddMember() {
  const qc = useQueryClient()
  return useMutation({ mutationFn: ({ email, name, role }: { email: string; name: string; role?: string }) => team.addMember(email, name, role), onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.members }) })
}
export function useBilling() {
  return useQuery({ queryKey: queryKeys.billing, queryFn: team.getBilling })
}
export function useUsage() {
  return useQuery({ queryKey: queryKeys.usage, queryFn: team.getUsage })
}
export function useSharedReports() {
  return useQuery({ queryKey: queryKeys.sharedReports, queryFn: team.listSharedReports })
}

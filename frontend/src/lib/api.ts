/**
 * api.ts — Barrel re-exports for backward compatibility.
 *
 * New code should import directly from the domain modules:
 *   import { getMe } from '../lib/auth'
 *   import { listProjects } from '../lib/projects'
 *   import api from '../lib/client'
 */
export { default } from './client'
export * from './types'
export * from './auth'
export * from './projects'
export * from './sprints'
export * from './codebase'
export * from './api-tests'
export * from './figma'
export * from './team'
export * from './reports'
export * from './analysis-jobs'
export * from './notifications'

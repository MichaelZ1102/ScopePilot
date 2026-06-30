export interface User {
  id: number; email: string; name: string; role: string
}
export interface Workspace {
  id: number; name: string; created_at: string
}
export interface Project {
  id: number; name: string; jira_url: string; jira_project_key: string; created_at: string
}
export interface Sprint {
  id: number; name: string; state: string; total_tickets: number; analysis_status: string; imported_at?: string
}
export interface SprintDetail extends Sprint {
  project_id: number; jira_sprint_id: number; started_at?: string; ended_at?: string; tickets: TicketDetail[]
}
export interface Ticket {
  id: number; key: string; summary: string; issue_type?: string; status?: string; priority?: string; assignee?: string
}
export interface TicketDetail extends Ticket {
  sprint_id: number; description?: string; labels?: string[]; story_points?: number; acceptance_criteria?: string[]; comments?: Record<string, unknown>[]; figma_links?: string[]; created_at?: string
}
export interface CodeSource {
  id: number; name: string; provider: string; repo_url: string; default_branch: string; last_scanned_at: string | null; scan_status: string; created_at: string
}
export interface RepoSnapshot {
  id: number; code_source_id: number; branch: string; commit_sha: string | null; file_tree: { files: string[]; dirs: string[] } | null; language_breakdown: Record<string, number> | null; total_files: number; total_lines: number; scanned_at: string
}
export interface BillingTier {
  id: string; name: string; price_monthly: number; max_members: number; max_projects: number; max_analyses_per_month: number; max_repo_scans: number; max_api_specs: number; max_figma_analyses: number; report_sharing: boolean; export_formats: string[]; ai_analysis: boolean; support: string
}
export interface UsageData {
  current: {
    analyses_run: number; repo_scans: number; api_specs_imported: number; figma_analyses: number; members_active: number; projects_count: number; sprints_imported: number
  }
  limits: {
    max_members: number; max_projects: number; max_analyses_per_month: number; max_repo_scans: number; max_api_specs: number; max_figma_analyses: number
  }
}
export interface TeamMember {
  id: number; workspace_id: number; email: string; name: string; role: string; status: string; invited_by: string; joined_at: string
}
export interface SharedReport {
  id: number; workspace_id: number; sprint_id: number; title: string; shared_by: string; share_token: string; view_count: number; is_password_protected: boolean; created_at: string; expires_at: string; is_active: boolean
}
export interface ApiSpec {
  id: number; name: string; title: string; version: string; source: string; endpoint_count: number; created_at: string
}
export interface TestPlan {
  id: number; spec_id: number; title: string; base_url: string; endpoints_analyzed: number; scenario_count: number; coverage_summary: { positive_scenarios: number; negative_scenarios: number; edge_scenarios: number; ai_generated: boolean }; created_at: string; scenarios?: { test_type: string; method: string; endpoint: string; expected_status: number; scenario_name: string; description: string; expected_behavior: string; test_input?: Record<string, unknown> }[]
}
export interface CodeImpact {
  summary: string; affected_files: { path: string; change_type: string; confidence: number }[]
}
export interface FigmaAnalysis {
  id: number; figma_url: string; file_name: string; frame_count: number; text_node_count: number; implications: { priority: string; type: string; title: string; description: string; detail?: Record<string, unknown> }[]; ai_used: boolean; created_at: string; design_tokens?: { colors?: Record<string, string>; spacing?: number[] } | null; frames?: Record<string, unknown>[] | null
}

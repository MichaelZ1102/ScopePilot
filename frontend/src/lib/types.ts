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
  project_id: number; jira_sprint_id: number; started_at?: string; ended_at?: string; tickets: TicketDetail[]; analysis_data?: SprintAnalysisData | null
  latest_analysis_run_id?: number | null; latest_analysis_job_id?: number | null; analysis_stale_at?: string | null; last_synced_at?: string | null; updated_at?: string | null
}
export interface Ticket {
  id: number; key: string; summary: string; issue_type?: string; status?: string; priority?: string; assignee?: string
}
export interface TicketDetail extends Ticket {
  sprint_id: number; description?: string; labels?: string[]; story_points?: number; acceptance_criteria?: string[]; comments?: Record<string, unknown>[]; figma_links?: string[]; analysis_data?: TicketAnalysis | null; report_included?: boolean; created_at?: string
  latest_analysis_run_id?: number | null; analysis_status?: string; analysis_stale_at?: string | null
  review_data?: TicketReview | null; updated_at?: string | null; source_updated_at?: string | null
}
export interface TicketAnalysis {
  ticket_key: string; summary: string; business_goal: string; acceptance_criteria_summary: string
  backend_features: string[]; api_candidates: string[]; db_changes: string[]
  permission_rules: string[]; state_transitions: string[]; validation_rules: string[]
  external_dependencies: string[]; open_questions: string[]
  score: Record<string, unknown>; code_impact: Record<string, unknown>
  implementation_plan: string[]; api_tests: Array<Record<string, unknown> | string>
  comments: Record<string, unknown>[]
  evidence?: Array<{ claim: string; type: string; source: string; locator: string; confidence: string }>
  assumptions?: string[]
}
export interface SprintAnalysisData {
  sprint_analysis: {
    sprint_name: string; total_tickets: number; summary: string
    risk_map: Record<string, unknown>[]; open_questions: string[]
    suggested_execution_order: string[]
  }
  ticket_analyses: TicketAnalysis[]
}
export interface CodeSource {
  id: number; project_id?: number | null; name: string; provider: string; repo_url: string; default_branch: string; last_scanned_at: string | null; scan_status: string; created_at: string
}
export interface RepoSnapshot {
  id: number; code_source_id: number; branch: string; commit_sha: string | null; file_tree: { files: string[]; dirs: string[] } | null; language_breakdown: Record<string, number> | null; code_index?: Record<string, unknown>[] | null; total_files: number; total_lines: number; scanned_at: string
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
  id: number; workspace_id: number; email: string; name: string; role: string; status: string; invite_token?: string; invited_by: string; joined_at?: string | null
}
export interface SharedReport {
  id: number; workspace_id: number; sprint_id: number; title: string; shared_by: string; share_token: string; view_count: number; is_password_protected: boolean; created_at: string; expires_at: string; is_active: boolean
}
export interface SharedReportAccess extends SharedReport {
  content?: string; content_error?: string
}
export interface ApiSpec {
  id: number; project_id?: number | null; service_name?: string; name: string; title: string; version: string; revision?: number; previous_spec_id?: number | null; changes?: { added: string[]; removed: string[]; changed: string[] } | null; source: string; endpoint_count: number; created_at: string
}
export interface TestPlan {
  id: number; spec_id: number; project_id?: number | null; ticket_ids?: number[]; title: string; base_url: string; endpoints_analyzed: number; scenario_count: number; coverage_summary: { positive_scenarios: number; negative_scenarios: number; edge_scenarios: number; ai_generated: boolean }; created_at: string; scenarios?: { test_type: string; method: string; endpoint: string; expected_status: number; scenario_name: string; description: string; expected_behavior: string; test_input?: Record<string, unknown> }[]
}
export interface CodeImpact {
  summary: string; affected_files: { path: string; change_type: string; confidence: number; symbols?: string[]; routes?: string[]; imports?: string[]; reasons?: string[] }[]; source_commit_sha?: string; analysis_method?: string
}
export interface FigmaAnalysis {
  id: number; project_id?: number | null; ticket_id?: number | null; figma_node_id?: string; version?: number; previous_analysis_id?: number | null; last_modified?: string; changes?: { added_frames: string[]; removed_frames: string[]; changed_frames: string[] } | null; figma_url: string; file_name: string; frame_count: number; text_node_count: number; implications: { priority: string; type: string; title: string; description: string; detail?: Record<string, unknown> }[]; ai_used: boolean; created_at: string; design_tokens?: { colors?: Record<string, string>; spacing?: number[] } | null; frames?: Record<string, unknown>[] | null
  pages?: Array<{ id: string; name: string; frame_count: number; children_count: number }> | null
  selected_nodes?: Array<{ id: string; name: string; type: string }> | null
  preview_images?: Record<string, string> | null
  preview_status?: 'available' | 'unavailable' | 'not_requested'
  preview_error?: string
  analysis_scope?: 'file' | 'selected_nodes'
}

export interface AnalysisRun {
  id: number; workspace_id: number; project_id: number; sprint_id: number; ticket_id?: number | null
  analysis_type: string; version: number; status: string; result: Record<string, unknown>
  source_versions: Record<string, unknown>; model: string; prompt_version: string; created_at: string; completed_at?: string | null
}

export interface AnalysisJob {
  id: number; sprint_id: number; workspace_id: number
  status: 'queued' | 'running' | 'cancel_requested' | 'done' | 'failed' | 'cancelled'
  error_message: string; progress_current: number; progress_total: number
  created_at: string; started_at?: string | null; finished_at?: string | null
}

export interface TicketReview {
  id?: number; ticket_id: number; analysis_run_id?: number | null
  status: 'unreviewed' | 'in_review' | 'approved' | 'rejected'
  reviewer_id?: number; reviewer_name?: string; comment?: string; reviewed_at?: string | null; updated_at?: string
}

export interface TicketArtifactLink {
  id: number; project_id: number; sprint_id: number; ticket_id: number
  artifact_type: 'code_source' | 'code_impact' | 'api_spec' | 'api_impact' | 'test_plan' | 'figma_analysis'
  artifact_id: number; metadata: Record<string, unknown>; created_at: string
}

export interface TicketReport {
  report_type: 'ticket'; title: string; generated_at: string
  project: { id: number; name: string; jira_project_key?: string; jira_url?: string }
  sprint: { id: number; name: string; state?: string; last_synced_at?: string | null }
  ticket: TicketDetail
  analysis: TicketAnalysis
  analysis_run?: AnalysisRun | null
  is_historical?: boolean
  review: TicketReview
  is_stale: boolean
  stale_reasons: string[]
  collaboration: {
    comments: ReportComment[]
    action_items: ActionItem[]
    delivery_links: DeliveryLink[]
    delivery_comparison: {
      predicted_files: string[]; actual_files: string[]; matched_files: string[]
      unexpected_files: string[]; predicted_not_changed: string[]; match_rate?: number | null
    }
  }
  artifacts: {
    links: TicketArtifactLink[]
    code_sources: CodeSource[]
    code_impacts: Array<CodeImpact & { id: number; code_source_id: number; created_at: string }>
    api_specs: ApiSpec[]
    api_impacts: ApiImpact[]
    test_plans: TestPlan[]
    figma_analyses: FigmaAnalysis[]
  }
}

export interface ReportComment {
  id: number; ticket_id: number; author_id: number; author_name: string
  body: string; mentions: string[]; status: 'open' | 'resolved'; created_at: string; updated_at: string
}

export interface ActionItem {
  id: number; ticket_id: number; title: string; owner: string; due_at?: string | null
  status: 'open' | 'done'; created_by: number; created_at: string; updated_at: string
}

export interface DeliveryLink {
  id: number; ticket_id: number; provider: string; url: string; pull_request: string
  commit_sha: string; ci_status: string; release_version: string; actual_files: string[]
  created_at: string
}

export interface ApiImpact {
  id: number; project_id: number; sprint_id: number; ticket_id: number; spec_id: number
  spec_version: string; service_name?: string
  impacts: Array<{ candidate: string; method: string; path: string; change_type: string; confirmation: string; evidence: string }>
  schema_changes: string[]; validation_changes: string[]
  breaking_changes: Array<{ type: string; level: string; description: string }>
  confirmed_count: number; missing_count: number; created_at: string
}

export interface SprintReport {
  report_type: 'sprint'; title: string; generated_at: string
  project: { id: number; name: string; jira_project_key?: string; jira_url?: string }
  sprint: { id: number; name: string; state?: string; total_tickets: number; last_synced_at?: string | null; analysis_status?: string }
  summary: SprintAnalysisData['sprint_analysis']
  review_counts: Record<string, number>
  stale_ticket_count: number
  dependency_graph: Array<{ from: string; to: string; type: string }>
  code_conflicts: Array<{ path: string; tickets: string[] }>
  tickets: TicketReport[]
}

export interface ReportSnapshot {
  id: number; project_id: number; sprint_id: number; ticket_id?: number | null; report_type: string
  title: string; version: number; status: string; created_at: string; published_at?: string | null; archived_at?: string | null
  content?: string; structured_content?: SprintReport | Record<string, unknown>; created_by?: number
}

export interface AuditLog {
  id: number; workspace_id: number; actor_id: number; actor_name: string
  action: string; resource_type: string; resource_id?: number | null
  details: Record<string, unknown>; created_at: string
}

export interface Notification {
  id: number; event_type: string; title: string; message: string
  resource_type: string; resource_id?: number | null; details: Record<string, unknown>
  is_read: boolean; created_at: string
}

export interface WebhookSubscription {
  id: number; name: string; provider: 'generic' | 'slack' | 'teams'
  url: string; events: string[]; is_active: boolean; created_at: string
}

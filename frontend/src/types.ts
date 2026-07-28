export type UserRole = 'manager' | 'employee';

/** Сессия пользователя (хранится в localStorage). */
export interface Session {
  apiKey: string;
  employeeId: number;
  name: string;
  role: UserRole;
  language: string;
  departmentId: number | null;
}

export interface Member {
  id: number;
  name: string;
  role: string;
  language: string;
  online: boolean;
}

export interface AnalysisSummary {
  id: number;
  employee_id: number | null;
  recording_id: string;
  kpi_score: number;
  is_sold: boolean;
  summary: string;
  created_at: string;
}

export interface AnalysisDetail extends AnalysisSummary {
  transcript: string;
  analysis: {
    summary?: string;
    kpi_score?: number;
    deal_analysis?: { is_sold?: boolean; detected_amount?: number };
    sentiment?: { positive?: number; neutral?: number; negative?: number };
    filler_words?: { word: string; count: number }[];
    script_compliance?: { label: string; status: 'success' | 'warning' | 'fail' }[];
    strengths?: string[];
    weaknesses?: string[];
    mistakes_and_fixes?: { error: string; fix: string }[];
    recommendations?: string[];
    transcript_parsed?: { time?: string; speaker: string; text: string; tags?: string[] }[];
  };
}

export interface Course {
  id: number;
  title: string;
  description: string;
  category: string;
  steps: CourseStep[];
  progress: number;
}

export interface CourseStep {
  id: string;
  type: 'content' | 'quiz';
  title: string;
  content?: string;
  question?: { text: string; options: string[]; correctOption: number };
}

export interface Goal {
  id: number;
  employee_id: number;
  title: string;
  target: number;
  progress: number;
  reward_points: number;
  done: boolean;
}

export interface EmployeeStats {
  employee_id: number;
  name: string;
  role: string;
  language: string;
  points: number;
  online: boolean;
  assistant_queries: number;
  messages_sent: number;
  goals: Goal[];
}

export interface RopDashboard {
  online_ids: number[];
  team: EmployeeStats[];
  total_assistant_queries: number;
  assistant_hit_rate: number;
  total_messages: number;
  top_queries: { query: string; count: number }[];
}

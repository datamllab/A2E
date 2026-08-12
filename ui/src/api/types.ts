export interface WindowConfig {
  basename?: string;
}

declare global {
  interface Window {
    Config?: WindowConfig;
  }
}

export interface ExperimentSummary {
  id: string;
  dataset_id: string;
  name?: string;
  dataset_name: string;
  created_at?: string;
  example_count?: number;
  successful_run_count?: number;
  failed_run_count?: number;
  project_name?: string;
  metadata?: Record<string, unknown>;
  dataset_metadata?: Record<string, unknown>;
}

export interface Annotation {
  name: string;
  label?: string;
  score?: number;
  explanation?: string;
}

export interface ExperimentRecord {
  id?: string;
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  reference_output?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  annotations?: Annotation[];
  trace_id?: string;
  latency_ms?: number;
  prompt_token_count?: number;
  completion_token_count?: number;
  error?: string | null;
}

export interface SpanNode {
  span_id: string;
  parent_id?: string | null;
  name: string;
  span_kind?: string;
  start_time: string;
  end_time: string;
  attributes?: Record<string, unknown>;
  events?: unknown[];
  status_code?: string;
  status_message?: string;
  synthetic?: boolean;
}

export interface AgentInfo {
  id: string;
  label: string;
  aliases?: string[];
}

export interface MetricCatalogEntry {
  name: string;
  kind?: "LLM" | "CODE";
  score_type?: "binary" | "graded" | "magnitude";
  positive_label?: string | null;
  labels?: string[];
  desc?: string;
  output_contract?: {
    required_fields?: string[];
    score?: {
      type?: string;
      enum?: number[];
      minimum?: number;
      maximum?: number;
      integer_like?: boolean;
    };
    score_domain?: {
      kind?: "discrete_enum" | "continuous_range" | "discrete_integer_range";
      allowed_values?: number[];
      minimum?: number;
      maximum?: number;
      integer_like?: boolean;
    };
    label?: {
      enum?: string[];
      enum_or_pattern?: {
        enum?: string[];
        pattern?: string;
      };
    };
    positive_labels?: string[];
    label_score_map?: Record<string, number>;
    label_bands?: Array<Record<string, string | number | boolean>>;
    notes?: string[];
  };
}

export interface MetricsCatalog {
  categories?: Record<
    string,
    {
      label_zh?: string;
      desc?: string;
      groups?: Record<
        string,
        {
          label_zh?: string;
          source?: string;
          note?: string;
          metrics?: MetricCatalogEntry[];
        }
      >;
    }
  >;
}

export interface ExperimentContext {
  available: boolean;
  experiment?: {
    id?: string;
    name?: string;
    project_name?: string;
    created_at?: string;
    metadata?: Record<string, unknown>;
  };
  dataset?: { name?: string; description?: string };
  runs?: {
    runs?: number;
    ok_runs?: number;
    avg_latency_ms?: number;
    first_start_time?: string;
    last_end_time?: string;
  };
  inputs?: {
    domains?: string[];
    expected_actions?: string[];
    expected_outputs?: string[];
  };
  models?: { task?: { provider?: string; name?: string }[]; observed?: string[] };
  agent?: { names?: string[]; frameworks?: string[] };
}

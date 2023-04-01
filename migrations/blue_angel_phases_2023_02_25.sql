ALTER TABLE "projects" ADD COLUMN "phases" JSONB DEFAULT NULL;
ALTER TABLE "machines" ADD COLUMN "available" boolean DEFAULT false;
ALTER TABLE "projects" ADD COLUMN "machine_id" int REFERENCES machines(id) ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "projects" ADD COLUMN "usage_scenario_file" text;
ALTER TABLE "stats" ADD COLUMN "phase" text DEFAULT NULL;

CREATE TABLE phase_stats (
    id SERIAL PRIMARY KEY,
    project_id uuid REFERENCES projects(id) ON DELETE CASCADE ON UPDATE CASCADE,
    metric text,
    detail_name text,
    phase text,
    value bigint,
    type text,
    max_value bigint DEFAULT NULL,
    unit text,
    created_at timestamp with time zone DEFAULT now()
);


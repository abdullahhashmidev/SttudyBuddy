-- =============================================================================
-- StudyBuddy — Supabase schema (agent-compatible, no auth required yet)
-- =============================================================================

create table if not exists students (
    student_id text primary key,
    name text,
    preferred_study_time text,
    daily_available_minutes integer default 120
);

create table if not exists tasks (
    task_id bigint generated always as identity primary key,
    student_id text not null references students(student_id) on delete cascade,
    title text not null,
    subject text,
    deadline text,
    priority text not null default 'medium' check (priority in ('low','medium','high')),
    status text not null default 'pending' check (status in ('pending','completed')),
    created_at timestamptz not null default now()
);
create index if not exists idx_tasks_student on tasks (student_id, created_at desc);

create table if not exists study_sessions (
    session_id bigint generated always as identity primary key,
    student_id text not null references students(student_id) on delete cascade,
    subject text not null,
    topic text not null,
    duration_minutes integer default 45,
    scheduled_date text,
    completed integer default 0
);
create index if not exists idx_sessions_student on study_sessions (student_id);

create table if not exists notes (
    note_id bigint generated always as identity primary key,
    student_id text not null references students(student_id) on delete cascade,
    title text not null,
    content text not null,
    subject text,
    tags text,
    created_at timestamptz not null default now()
);
create index if not exists idx_notes_student on notes (student_id, created_at desc);

create table if not exists quizzes (
    quiz_id bigint generated always as identity primary key,
    student_id text not null references students(student_id) on delete cascade,
    subject text not null,
    topic text not null,
    questions jsonb not null,
    created_at timestamptz not null default now()
);
create index if not exists idx_quizzes_student on quizzes (student_id, created_at desc);

create table if not exists quiz_attempts (
    attempt_id bigint generated always as identity primary key,
    quiz_id bigint not null references quizzes(quiz_id) on delete cascade,
    student_id text not null references students(student_id) on delete cascade,
    answers jsonb not null,
    score real,
    weak_areas text,
    attempt_date timestamptz not null default now()
);
create index if not exists idx_attempts_student on quiz_attempts (student_id, attempt_date desc);

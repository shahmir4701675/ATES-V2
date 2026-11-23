-- Reconstructed from docs/SUPABASE_CATALOG.json, inspected 21 November 2026.
CREATE TABLE academic_terms (
    term_id INTEGER,
    name varchar(50) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status varchar(10) NOT NULL DEFAULT 'Planned',
    CHECK ((end_date > start_date)),
    CHECK (((status) IN ('Planned', 'Active', 'Closed'))),
    PRIMARY KEY (term_id),
    UNIQUE (name)
);
-- next statement
CREATE TABLE departments (
    department_id INTEGER,
    code varchar(10) NOT NULL,
    name varchar(100) NOT NULL,
    PRIMARY KEY (department_id),
    UNIQUE (code)
);
-- next statement
CREATE TABLE batches (
    batch_id INTEGER,
    department_id INTEGER NOT NULL,
    program_code varchar(10) NOT NULL,
    batch_year SMALLINT NOT NULL,
    section varchar(5) NOT NULL,
    strength SMALLINT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    CHECK ((strength > 0)),
    FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE RESTRICT,
    PRIMARY KEY (batch_id),
    UNIQUE (program_code, batch_year, section)
);
-- next statement
CREATE INDEX ix_batches_department_id ON batches (department_id);
-- next statement
CREATE TABLE instructors (
    instructor_id INTEGER,
    department_id INTEGER NOT NULL,
    full_name varchar(100) NOT NULL,
    email varchar(120) NOT NULL,
    max_daily_hours SMALLINT NOT NULL DEFAULT 4,
    max_weekly_hours SMALLINT NOT NULL DEFAULT 18,
    is_active BOOLEAN NOT NULL DEFAULT true,
    CHECK ((max_daily_hours > 0)),
    CHECK ((max_weekly_hours >= max_daily_hours)),
    FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE RESTRICT,
    PRIMARY KEY (instructor_id),
    UNIQUE (email)
);
-- next statement
CREATE INDEX ix_instructors_department_id ON instructors (department_id);
-- next statement
CREATE TABLE users (
    user_id INTEGER,
    username varchar(40) NOT NULL,
    password_hash varchar(100) NOT NULL,
    full_name varchar(100) NOT NULL,
    email varchar(120) NOT NULL,
    role varchar(15) NOT NULL,
    instructor_id INTEGER,
    batch_id INTEGER,
    account_status varchar(12) NOT NULL DEFAULT 'Active',
    failed_attempts SMALLINT NOT NULL DEFAULT 0,
    locked_until DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (((account_status) IN ('Active', 'Locked', 'Deactivated'))),
    CHECK ((((role) <> 'Faculty') OR (instructor_id IS NOT NULL))),
    CHECK ((failed_attempts >= 0)),
    CHECK (((role) IN ('Administrator', 'Coordinator', 'Approver', 'Faculty', 'Student'))),
    CHECK ((((role) <> 'Student') OR (batch_id IS NOT NULL))),
    FOREIGN KEY (batch_id) REFERENCES batches(batch_id) ON DELETE RESTRICT,
    FOREIGN KEY (instructor_id) REFERENCES instructors(instructor_id) ON DELETE RESTRICT,
    PRIMARY KEY (user_id),
    UNIQUE (email),
    UNIQUE (instructor_id),
    UNIQUE (username)
);
-- next statement
CREATE INDEX ix_users_batch_id ON users (batch_id);
-- next statement
CREATE TABLE audit_logs (
    log_id INTEGER,
    user_id INTEGER,
    action varchar(40) NOT NULL,
    entity_type varchar(30),
    entity_id INTEGER,
    details text,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE RESTRICT,
    PRIMARY KEY (log_id)
);
-- next statement
CREATE INDEX ix_audit_logs_action ON audit_logs (action);
-- next statement
CREATE INDEX ix_audit_logs_created_at ON audit_logs (created_at);
-- next statement
CREATE INDEX ix_audit_logs_user_id ON audit_logs (user_id);
-- next statement
CREATE TABLE scheduling_configs (
    config_id INTEGER,
    term_id INTEGER NOT NULL,
    schedule_type varchar(10) NOT NULL,
    name varchar(60) NOT NULL,
    solver_time_limit_s SMALLINT NOT NULL DEFAULT 120,
    random_seed INTEGER NOT NULL DEFAULT 1,
    created_by INTEGER NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (((schedule_type) IN ('Timetable', 'Exam'))),
    CHECK (((solver_time_limit_s >= 10) AND (solver_time_limit_s <= 600))),
    FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (term_id) REFERENCES academic_terms(term_id) ON DELETE RESTRICT,
    PRIMARY KEY (config_id),
    UNIQUE (term_id, schedule_type, name)
);
-- next statement
CREATE INDEX ix_scheduling_configs_created_by ON scheduling_configs (created_by);
-- next statement
CREATE INDEX ix_scheduling_configs_term_id ON scheduling_configs (term_id);
-- next statement
CREATE TABLE schedules (
    schedule_id INTEGER,
    term_id INTEGER NOT NULL,
    config_id INTEGER NOT NULL,
    schedule_type varchar(10) NOT NULL,
    version_no SMALLINT NOT NULL,
    status varchar(12) NOT NULL DEFAULT 'Draft',
    solver_status varchar(15),
    objective_score numeric(10,2),
    run_seconds numeric(8,2),
    generated_by INTEGER NOT NULL,
    generated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    approved_by INTEGER,
    published_at DATETIME,
    CHECK (((schedule_type) IN ('Timetable', 'Exam'))),
    CHECK (((solver_status IS NULL) OR ((solver_status) IN ('optimal', 'feasible', 'infeasible', 'unknown', 'interrupted')))),
    CHECK (((status) IN ('Draft', 'Generating', 'Infeasible', 'Generated', 'Published', 'Archived'))),
    CHECK ((version_no > 0)),
    FOREIGN KEY (approved_by) REFERENCES users(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (config_id) REFERENCES scheduling_configs(config_id) ON DELETE RESTRICT,
    FOREIGN KEY (generated_by) REFERENCES users(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (term_id) REFERENCES academic_terms(term_id) ON DELETE RESTRICT,
    PRIMARY KEY (schedule_id),
    UNIQUE (term_id, schedule_type, version_no)
);
-- next statement
CREATE INDEX ix_schedules_approved_by ON schedules (approved_by);
-- next statement
CREATE INDEX ix_schedules_config_id ON schedules (config_id);
-- next statement
CREATE INDEX ix_schedules_generated_by ON schedules (generated_by);
-- next statement
CREATE INDEX ix_schedules_term_id ON schedules (term_id);
-- next statement
CREATE TABLE conflict_log (
    conflict_id INTEGER,
    schedule_id INTEGER NOT NULL,
    conflict_type varchar(30) NOT NULL,
    severity varchar(8) NOT NULL,
    description text NOT NULL,
    entity_ref varchar(100),
    detected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_resolved BOOLEAN NOT NULL DEFAULT false,
    CHECK (((severity) IN ('Hard', 'Warning'))),
    FOREIGN KEY (schedule_id) REFERENCES schedules(schedule_id) ON DELETE CASCADE,
    PRIMARY KEY (conflict_id)
);
-- next statement
CREATE INDEX ix_conflict_log_schedule_id ON conflict_log (schedule_id);
-- next statement
CREATE TABLE constraint_rules (
    rule_id INTEGER,
    config_id INTEGER NOT NULL,
    rule_code varchar(6) NOT NULL,
    rule_type varchar(4) NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT true,
    weight SMALLINT NOT NULL DEFAULT 0,
    param_value INTEGER,
    CHECK ((NOT (((rule_code) IN ('H01', 'H02', 'H03', 'H08', 'E01', 'E04', 'E05')) AND (is_enabled = false)))),
    CHECK (((rule_type) IN ('Hard', 'Soft'))),
    CHECK (((weight >= 0) AND (weight <= 10))),
    FOREIGN KEY (config_id) REFERENCES scheduling_configs(config_id) ON DELETE CASCADE,
    PRIMARY KEY (rule_id),
    UNIQUE (config_id, rule_code)
);
-- next statement
CREATE INDEX ix_constraint_rules_config_id ON constraint_rules (config_id);
-- next statement
CREATE TABLE courses (
    course_id INTEGER,
    course_code varchar(15) NOT NULL,
    title varchar(150) NOT NULL,
    department_id INTEGER NOT NULL,
    credit_hours SMALLINT NOT NULL,
    lecture_hours SMALLINT NOT NULL DEFAULT 0,
    lab_hours SMALLINT NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT true,
    CHECK ((credit_hours >= 0)),
    CHECK ((lab_hours >= 0)),
    CHECK ((lecture_hours >= 0)),
    CHECK (((lecture_hours + lab_hours) > 0)),
    FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE RESTRICT,
    PRIMARY KEY (course_id),
    UNIQUE (course_code)
);
-- next statement
CREATE INDEX ix_courses_department_id ON courses (department_id);
-- next statement
CREATE TABLE course_offerings (
    offering_id INTEGER,
    term_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    batch_id INTEGER NOT NULL,
    instructor_id INTEGER NOT NULL,
    enrolled_count SMALLINT NOT NULL,
    CHECK ((enrolled_count > 0)),
    FOREIGN KEY (batch_id) REFERENCES batches(batch_id) ON DELETE RESTRICT,
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE RESTRICT,
    FOREIGN KEY (instructor_id) REFERENCES instructors(instructor_id) ON DELETE RESTRICT,
    FOREIGN KEY (term_id) REFERENCES academic_terms(term_id) ON DELETE RESTRICT,
    PRIMARY KEY (offering_id),
    UNIQUE (offering_id, instructor_id, batch_id),
    UNIQUE (term_id, course_id, batch_id)
);
-- next statement
CREATE INDEX ix_course_offerings_batch_id ON course_offerings (batch_id);
-- next statement
CREATE INDEX ix_course_offerings_course_id ON course_offerings (course_id);
-- next statement
CREATE INDEX ix_course_offerings_instructor_id ON course_offerings (instructor_id);
-- next statement
CREATE INDEX ix_course_offerings_term_id ON course_offerings (term_id);
-- next statement
CREATE TABLE enrollments (
    enrollment_id INTEGER,
    offering_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    FOREIGN KEY (offering_id) REFERENCES course_offerings(offering_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(user_id) ON DELETE RESTRICT,
    PRIMARY KEY (enrollment_id),
    UNIQUE (offering_id, student_id)
);
-- next statement
CREATE INDEX ix_enrollments_offering_id ON enrollments (offering_id);
-- next statement
CREATE INDEX ix_enrollments_student_id ON enrollments (student_id);
-- next statement
CREATE TABLE exam_slots (
    exam_slot_id INTEGER,
    term_id INTEGER NOT NULL,
    exam_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    label varchar(30),
    CHECK ((end_time > start_time)),
    FOREIGN KEY (term_id) REFERENCES academic_terms(term_id) ON DELETE RESTRICT,
    PRIMARY KEY (exam_slot_id),
    UNIQUE (term_id, exam_date, start_time)
);
-- next statement
CREATE INDEX ix_exam_slots_term_id ON exam_slots (term_id);
-- next statement
CREATE TABLE exam_entries (
    exam_entry_id INTEGER,
    schedule_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    exam_slot_id INTEGER NOT NULL,
    student_count SMALLINT NOT NULL,
    is_locked BOOLEAN NOT NULL DEFAULT false,
    CHECK ((student_count > 0)),
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE RESTRICT,
    FOREIGN KEY (exam_slot_id) REFERENCES exam_slots(exam_slot_id) ON DELETE RESTRICT,
    FOREIGN KEY (schedule_id) REFERENCES schedules(schedule_id) ON DELETE CASCADE,
    PRIMARY KEY (exam_entry_id),
    UNIQUE (schedule_id, course_id)
);
-- next statement
CREATE INDEX ix_exam_entries_course_id ON exam_entries (course_id);
-- next statement
CREATE INDEX ix_exam_entries_exam_slot_id ON exam_entries (exam_slot_id);
-- next statement
CREATE INDEX ix_exam_entries_schedule_id ON exam_entries (schedule_id);
-- next statement
CREATE TABLE rooms (
    room_id INTEGER,
    room_code varchar(20) NOT NULL,
    building varchar(50) NOT NULL,
    capacity SMALLINT NOT NULL,
    room_type varchar(12) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    CHECK ((capacity > 0)),
    CHECK (((room_type) IN ('Lecture', 'Lab', 'Exam Hall'))),
    PRIMARY KEY (room_id),
    UNIQUE (room_code)
);
-- next statement
CREATE TABLE exam_room_allocations (
    allocation_id INTEGER,
    exam_entry_id INTEGER NOT NULL,
    room_id INTEGER NOT NULL,
    seats_allocated SMALLINT NOT NULL,
    CHECK ((seats_allocated > 0)),
    FOREIGN KEY (exam_entry_id) REFERENCES exam_entries(exam_entry_id) ON DELETE CASCADE,
    FOREIGN KEY (room_id) REFERENCES rooms(room_id) ON DELETE RESTRICT,
    PRIMARY KEY (allocation_id),
    UNIQUE (exam_entry_id, room_id)
);
-- next statement
CREATE INDEX ix_exam_room_allocations_exam_entry_id ON exam_room_allocations (exam_entry_id);
-- next statement
CREATE INDEX ix_exam_room_allocations_room_id ON exam_room_allocations (room_id);
-- next statement
CREATE TABLE import_logs (
    import_id INTEGER,
    user_id INTEGER NOT NULL,
    entity_type varchar(20) NOT NULL,
    file_name varchar(120) NOT NULL,
    rows_total INTEGER NOT NULL,
    rows_imported INTEGER NOT NULL,
    rows_rejected INTEGER NOT NULL,
    imported_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (((rows_total >= 0) AND (rows_imported >= 0) AND (rows_rejected >= 0))),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE RESTRICT,
    PRIMARY KEY (import_id)
);
-- next statement
CREATE INDEX ix_import_logs_user_id ON import_logs (user_id);
-- next statement
CREATE TABLE time_slots (
    slot_id INTEGER,
    term_id INTEGER NOT NULL,
    day_of_week SMALLINT NOT NULL,
    slot_index SMALLINT NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    is_blocked BOOLEAN NOT NULL DEFAULT false,
    block_reason varchar(50),
    CHECK (((NOT is_blocked) OR ((block_reason IS NOT NULL) AND (length(trim(block_reason)) > 0)))),
    CHECK (((day_of_week >= 1) AND (day_of_week <= 7))),
    CHECK ((slot_index > 0)),
    CHECK ((end_time > start_time)),
    FOREIGN KEY (term_id) REFERENCES academic_terms(term_id) ON DELETE RESTRICT,
    PRIMARY KEY (slot_id),
    UNIQUE (term_id, day_of_week, slot_index)
);
-- next statement
CREATE INDEX ix_time_slots_term_id ON time_slots (term_id);
-- next statement
CREATE TABLE instructor_availability (
    availability_id INTEGER,
    instructor_id INTEGER NOT NULL,
    slot_id INTEGER NOT NULL,
    is_available BOOLEAN NOT NULL DEFAULT true,
    FOREIGN KEY (instructor_id) REFERENCES instructors(instructor_id) ON DELETE RESTRICT,
    FOREIGN KEY (slot_id) REFERENCES time_slots(slot_id) ON DELETE CASCADE,
    PRIMARY KEY (availability_id),
    UNIQUE (instructor_id, slot_id)
);
-- next statement
CREATE INDEX ix_instructor_availability_instructor_id ON instructor_availability (instructor_id);
-- next statement
CREATE INDEX ix_instructor_availability_slot_id ON instructor_availability (slot_id);
-- next statement
CREATE TABLE timetable_entries (
    entry_id INTEGER,
    schedule_id INTEGER NOT NULL,
    offering_id INTEGER NOT NULL,
    instructor_id INTEGER NOT NULL,
    batch_id INTEGER NOT NULL,
    room_id INTEGER NOT NULL,
    slot_id INTEGER NOT NULL,
    session_type varchar(7) NOT NULL,
    is_locked BOOLEAN NOT NULL DEFAULT false,
    is_manual_override BOOLEAN NOT NULL DEFAULT false,
    CHECK (((session_type) IN ('Lecture', 'Lab'))),
    FOREIGN KEY (offering_id, instructor_id, batch_id) REFERENCES course_offerings(offering_id, instructor_id, batch_id) ON DELETE RESTRICT,
    FOREIGN KEY (batch_id) REFERENCES batches(batch_id) ON DELETE RESTRICT,
    FOREIGN KEY (instructor_id) REFERENCES instructors(instructor_id) ON DELETE RESTRICT,
    FOREIGN KEY (offering_id) REFERENCES course_offerings(offering_id) ON DELETE RESTRICT,
    FOREIGN KEY (room_id) REFERENCES rooms(room_id) ON DELETE RESTRICT,
    FOREIGN KEY (schedule_id) REFERENCES schedules(schedule_id) ON DELETE CASCADE,
    FOREIGN KEY (slot_id) REFERENCES time_slots(slot_id) ON DELETE RESTRICT,
    PRIMARY KEY (entry_id),
    UNIQUE (schedule_id, batch_id, slot_id),
    UNIQUE (schedule_id, instructor_id, slot_id),
    UNIQUE (schedule_id, room_id, slot_id)
);
-- next statement
CREATE INDEX ix_timetable_entries_batch_id ON timetable_entries (batch_id);
-- next statement
CREATE INDEX ix_timetable_entries_instructor_id ON timetable_entries (instructor_id);
-- next statement
CREATE INDEX ix_timetable_entries_offering_id ON timetable_entries (offering_id);
-- next statement
CREATE INDEX ix_timetable_entries_room_id ON timetable_entries (room_id);
-- next statement
CREATE INDEX ix_timetable_entries_schedule_id ON timetable_entries (schedule_id);
-- next statement
CREATE INDEX ix_timetable_entries_slot_id ON timetable_entries (slot_id);
-- next statement
CREATE UNIQUE INDEX uq_academic_terms_single_active ON academic_terms (status) WHERE ((status) = 'Active');
-- next statement
CREATE UNIQUE INDEX uq_schedules_one_published_per_term_type ON schedules (term_id, schedule_type) WHERE ((status) = 'Published');
-- next statement
CREATE TRIGGER audit_logs_update_immutable BEFORE UPDATE ON audit_logs
BEGIN SELECT RAISE(ABORT, 'History is append-only'); END;
-- next statement
CREATE TRIGGER audit_logs_delete_immutable BEFORE DELETE ON audit_logs
BEGIN SELECT RAISE(ABORT, 'History is append-only'); END;
-- next statement
CREATE TRIGGER import_logs_update_immutable BEFORE UPDATE ON import_logs
BEGIN SELECT RAISE(ABORT, 'History is append-only'); END;
-- next statement
CREATE TRIGGER import_logs_delete_immutable BEFORE DELETE ON import_logs
BEGIN SELECT RAISE(ABORT, 'History is append-only'); END;
-- next statement
CREATE TRIGGER exam_slots_insert_no_overlap BEFORE INSERT ON exam_slots
WHEN EXISTS (SELECT 1 FROM exam_slots
    WHERE term_id = NEW.term_id AND exam_date = NEW.exam_date
      AND exam_slot_id <> NEW.exam_slot_id
      AND NEW.start_time < end_time AND start_time < NEW.end_time)
BEGIN SELECT RAISE(ABORT, 'Exam sessions overlap'); END;
-- next statement
CREATE TRIGGER exam_rooms_insert_capacity BEFORE INSERT ON exam_room_allocations
WHEN NEW.seats_allocated > (SELECT capacity FROM rooms WHERE room_id = NEW.room_id)
BEGIN SELECT RAISE(ABORT, 'Seat allocation exceeds room capacity'); END;
-- next statement
CREATE TRIGGER exam_slots_update_no_overlap BEFORE UPDATE ON exam_slots
WHEN EXISTS (SELECT 1 FROM exam_slots
    WHERE term_id = NEW.term_id AND exam_date = NEW.exam_date
      AND exam_slot_id <> NEW.exam_slot_id
      AND NEW.start_time < end_time AND start_time < NEW.end_time)
BEGIN SELECT RAISE(ABORT, 'Exam sessions overlap'); END;
-- next statement
CREATE TRIGGER exam_rooms_update_capacity BEFORE UPDATE ON exam_room_allocations
WHEN NEW.seats_allocated > (SELECT capacity FROM rooms WHERE room_id = NEW.room_id)
BEGIN SELECT RAISE(ABORT, 'Seat allocation exceeds room capacity'); END;
-- next statement
CREATE TRIGGER timetable_entries_insert_protect_history BEFORE INSERT ON timetable_entries
WHEN EXISTS (SELECT 1 FROM schedules WHERE schedule_id IN (NEW.schedule_id) AND status IN ('Published', 'Archived'))
BEGIN SELECT RAISE(ABORT, 'Published and archived entries are read-only'); END;
-- next statement
CREATE TRIGGER timetable_entries_update_protect_history BEFORE UPDATE ON timetable_entries
WHEN EXISTS (SELECT 1 FROM schedules WHERE schedule_id IN (OLD.schedule_id, NEW.schedule_id) AND status IN ('Published', 'Archived'))
BEGIN SELECT RAISE(ABORT, 'Published and archived entries are read-only'); END;
-- next statement
CREATE TRIGGER timetable_entries_delete_protect_history BEFORE DELETE ON timetable_entries
WHEN EXISTS (SELECT 1 FROM schedules WHERE schedule_id IN (OLD.schedule_id) AND status IN ('Published', 'Archived'))
BEGIN SELECT RAISE(ABORT, 'Published and archived entries are read-only'); END;
-- next statement
CREATE TRIGGER exam_entries_insert_protect_history BEFORE INSERT ON exam_entries
WHEN EXISTS (SELECT 1 FROM schedules WHERE schedule_id IN (NEW.schedule_id) AND status IN ('Published', 'Archived'))
BEGIN SELECT RAISE(ABORT, 'Published and archived entries are read-only'); END;
-- next statement
CREATE TRIGGER exam_entries_update_protect_history BEFORE UPDATE ON exam_entries
WHEN EXISTS (SELECT 1 FROM schedules WHERE schedule_id IN (OLD.schedule_id, NEW.schedule_id) AND status IN ('Published', 'Archived'))
BEGIN SELECT RAISE(ABORT, 'Published and archived entries are read-only'); END;
-- next statement
CREATE TRIGGER exam_entries_delete_protect_history BEFORE DELETE ON exam_entries
WHEN EXISTS (SELECT 1 FROM schedules WHERE schedule_id IN (OLD.schedule_id) AND status IN ('Published', 'Archived'))
BEGIN SELECT RAISE(ABORT, 'Published and archived entries are read-only'); END;
-- next statement
CREATE TRIGGER exam_room_allocations_insert_protect_history BEFORE INSERT ON exam_room_allocations
WHEN EXISTS (SELECT 1 FROM schedules WHERE schedule_id IN ((SELECT schedule_id FROM exam_entries WHERE exam_entry_id = NEW.exam_entry_id)) AND status IN ('Published', 'Archived'))
BEGIN SELECT RAISE(ABORT, 'Published and archived entries are read-only'); END;
-- next statement
CREATE TRIGGER exam_room_allocations_update_protect_history BEFORE UPDATE ON exam_room_allocations
WHEN EXISTS (SELECT 1 FROM schedules WHERE schedule_id IN ((SELECT schedule_id FROM exam_entries WHERE exam_entry_id = OLD.exam_entry_id), (SELECT schedule_id FROM exam_entries WHERE exam_entry_id = NEW.exam_entry_id)) AND status IN ('Published', 'Archived'))
BEGIN SELECT RAISE(ABORT, 'Published and archived entries are read-only'); END;
-- next statement
CREATE TRIGGER exam_room_allocations_delete_protect_history BEFORE DELETE ON exam_room_allocations
WHEN EXISTS (SELECT 1 FROM schedules WHERE schedule_id IN ((SELECT schedule_id FROM exam_entries WHERE exam_entry_id = OLD.exam_entry_id)) AND status IN ('Published', 'Archived'))
BEGIN SELECT RAISE(ABORT, 'Published and archived entries are read-only'); END;


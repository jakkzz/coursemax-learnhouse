BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';

CREATE TABLE attendancesession (
	id SERIAL NOT NULL,
	class_id INTEGER NOT NULL,
	title VARCHAR(160) NOT NULL,
	starts_at TIMESTAMP WITH TIME ZONE NOT NULL,
	ends_at TIMESTAMP WITH TIME ZONE NOT NULL,
	timezone VARCHAR(80) NOT NULL,
	grace_minutes INTEGER NOT NULL,
	late_threshold_minutes INTEGER NOT NULL,
	state VARCHAR NOT NULL,
	version INTEGER NOT NULL,
	created_by INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_attendance_session CHECK (ends_at > starts_at AND grace_minutes >= 0 AND late_threshold_minutes >= grace_minutes AND state IN ('scheduled','no_class') AND version >= 0),
	FOREIGN KEY(class_id) REFERENCES academicclass (id),
	FOREIGN KEY(created_by) REFERENCES "user" (id)
)

;
CREATE INDEX ix_attendancesession_class_id ON attendancesession (class_id);
CREATE OR REPLACE FUNCTION lh_attendance_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Attendance evidence is immutable'; END; $$;
CREATE OR REPLACE FUNCTION lh_attendance_schedule_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Attendance sessions must be retained'; END IF;
 IF ROW(NEW.class_id,NEW.title,NEW.starts_at,NEW.ends_at,NEW.timezone,NEW.grace_minutes,NEW.late_threshold_minutes,NEW.created_by)
 IS DISTINCT FROM ROW(OLD.class_id,OLD.title,OLD.starts_at,OLD.ends_at,OLD.timezone,OLD.grace_minutes,OLD.late_threshold_minutes,OLD.created_by)
 THEN RAISE EXCEPTION 'Attendance schedule cannot be rewritten'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER lh_attendancesession_immutable BEFORE UPDATE OR DELETE ON attendancesession FOR EACH ROW EXECUTE FUNCTION lh_attendance_schedule_immutable();
CREATE TRIGGER lh_attendancesession_no_truncate BEFORE TRUNCATE ON attendancesession FOR EACH STATEMENT EXECUTE FUNCTION lh_attendance_immutable();

CREATE TABLE attendancechallenge (
	id SERIAL NOT NULL,
	session_id INTEGER NOT NULL,
	token_hash VARCHAR(64) NOT NULL,
	session_version INTEGER NOT NULL,
	kind VARCHAR NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_by INTEGER NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_attendance_challenge CHECK (kind IN ('entry','heartbeat') AND expires_at > created_at),
	FOREIGN KEY(session_id) REFERENCES attendancesession (id),
	UNIQUE (token_hash),
	FOREIGN KEY(created_by) REFERENCES "user" (id)
)

;
CREATE INDEX ix_attendancechallenge_session_id ON attendancechallenge (session_id);
CREATE OR REPLACE FUNCTION lh_attendance_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Attendance evidence is immutable'; END; $$;
CREATE OR REPLACE FUNCTION lh_attendance_schedule_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Attendance sessions must be retained'; END IF;
 IF ROW(NEW.class_id,NEW.title,NEW.starts_at,NEW.ends_at,NEW.timezone,NEW.grace_minutes,NEW.late_threshold_minutes,NEW.created_by)
 IS DISTINCT FROM ROW(OLD.class_id,OLD.title,OLD.starts_at,OLD.ends_at,OLD.timezone,OLD.grace_minutes,OLD.late_threshold_minutes,OLD.created_by)
 THEN RAISE EXCEPTION 'Attendance schedule cannot be rewritten'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER lh_attendancechallenge_immutable BEFORE UPDATE OR DELETE ON attendancechallenge FOR EACH ROW EXECUTE FUNCTION lh_attendance_immutable();
CREATE TRIGGER lh_attendancechallenge_no_truncate BEFORE TRUNCATE ON attendancechallenge FOR EACH STATEMENT EXECUTE FUNCTION lh_attendance_immutable();

CREATE TABLE attendancescan (
	id SERIAL NOT NULL,
	receipt_id VARCHAR(36) NOT NULL,
	session_id INTEGER NOT NULL,
	challenge_id INTEGER NOT NULL,
	roster_entry_id INTEGER NOT NULL,
	actor_user_id INTEGER NOT NULL,
	arrived_at TIMESTAMP WITH TIME ZONE NOT NULL,
	kind VARCHAR NOT NULL,
	computed_status VARCHAR NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_attendance_scan_challenge_roster UNIQUE (challenge_id, roster_entry_id),
	CONSTRAINT ck_attendance_scan CHECK (computed_status IN ('present','late') AND kind IN ('entry','heartbeat')),
	UNIQUE (receipt_id),
	FOREIGN KEY(session_id) REFERENCES attendancesession (id),
	FOREIGN KEY(challenge_id) REFERENCES attendancechallenge (id),
	FOREIGN KEY(roster_entry_id) REFERENCES academicrosterentry (id),
	FOREIGN KEY(actor_user_id) REFERENCES "user" (id)
)

;
CREATE INDEX ix_attendancescan_session_id ON attendancescan (session_id);
CREATE INDEX ix_attendancescan_roster_entry_id ON attendancescan (roster_entry_id);
CREATE OR REPLACE FUNCTION lh_attendance_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Attendance evidence is immutable'; END; $$;
CREATE OR REPLACE FUNCTION lh_attendance_schedule_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Attendance sessions must be retained'; END IF;
 IF ROW(NEW.class_id,NEW.title,NEW.starts_at,NEW.ends_at,NEW.timezone,NEW.grace_minutes,NEW.late_threshold_minutes,NEW.created_by)
 IS DISTINCT FROM ROW(OLD.class_id,OLD.title,OLD.starts_at,OLD.ends_at,OLD.timezone,OLD.grace_minutes,OLD.late_threshold_minutes,OLD.created_by)
 THEN RAISE EXCEPTION 'Attendance schedule cannot be rewritten'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER lh_attendancescan_immutable BEFORE UPDATE OR DELETE ON attendancescan FOR EACH ROW EXECUTE FUNCTION lh_attendance_immutable();
CREATE TRIGGER lh_attendancescan_no_truncate BEFORE TRUNCATE ON attendancescan FOR EACH STATEMENT EXECUTE FUNCTION lh_attendance_immutable();
CREATE OR REPLACE FUNCTION lh_attendance_scan_scope() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM attendancechallenge c JOIN attendancesession s ON s.id=c.session_id
 JOIN academicrosterentry r ON r.class_id=s.class_id
 WHERE c.id=NEW.challenge_id AND s.id=NEW.session_id AND r.id=NEW.roster_entry_id AND c.kind=NEW.kind)
 THEN RAISE EXCEPTION 'Attendance scan belongs to another class, session or challenge'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER lh_attendance_scan_scope BEFORE INSERT ON attendancescan FOR EACH ROW EXECUTE FUNCTION lh_attendance_scan_scope();

CREATE TABLE attendanceevent (
	id SERIAL NOT NULL,
	session_id INTEGER NOT NULL,
	actor_user_id INTEGER NOT NULL,
	kind VARCHAR(60) NOT NULL,
	details JSONB NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(session_id) REFERENCES attendancesession (id),
	FOREIGN KEY(actor_user_id) REFERENCES "user" (id)
)

;
CREATE INDEX ix_attendanceevent_session_id ON attendanceevent (session_id);
CREATE OR REPLACE FUNCTION lh_attendance_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Attendance evidence is immutable'; END; $$;
CREATE OR REPLACE FUNCTION lh_attendance_schedule_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Attendance sessions must be retained'; END IF;
 IF ROW(NEW.class_id,NEW.title,NEW.starts_at,NEW.ends_at,NEW.timezone,NEW.grace_minutes,NEW.late_threshold_minutes,NEW.created_by)
 IS DISTINCT FROM ROW(OLD.class_id,OLD.title,OLD.starts_at,OLD.ends_at,OLD.timezone,OLD.grace_minutes,OLD.late_threshold_minutes,OLD.created_by)
 THEN RAISE EXCEPTION 'Attendance schedule cannot be rewritten'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER lh_attendanceevent_immutable BEFORE UPDATE OR DELETE ON attendanceevent FOR EACH ROW EXECUTE FUNCTION lh_attendance_immutable();
CREATE TRIGGER lh_attendanceevent_no_truncate BEFORE TRUNCATE ON attendanceevent FOR EACH STATEMENT EXECUTE FUNCTION lh_attendance_immutable();
COMMIT;

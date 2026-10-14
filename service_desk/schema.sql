PRAGMA foreign_keys = ON;

CREATE TABLE users (
    user_id TEXT PRIMARY KEY NOT NULL,
    region TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE models (
    model_code TEXT PRIMARY KEY NOT NULL CHECK(model_code GLOB 'SV-[0-9][0-9][0-9]'),
    display_name TEXT NOT NULL,
    family TEXT NOT NULL,
    launch_date TEXT NOT NULL,
    components_json TEXT NOT NULL CHECK(json_valid(components_json))
);
CREATE TABLE devices (
    device_id TEXT PRIMARY KEY NOT NULL CHECK(device_id LIKE 'D-%'),
    user_id TEXT NOT NULL REFERENCES users(user_id),
    model_code TEXT NOT NULL REFERENCES models(model_code),
    serial_no TEXT NOT NULL UNIQUE,
    purchase_date TEXT NOT NULL,
    firmware TEXT NOT NULL,
    UNIQUE(device_id, user_id),
    UNIQUE(device_id, model_code)
);
CREATE TABLE warranty_policies (
    model_code TEXT NOT NULL REFERENCES models(model_code),
    component TEXT NOT NULL CHECK(component IN ('whole_machine', 'battery', 'consumables')),
    months INTEGER NOT NULL CHECK(months >= 0),
    excludes TEXT NOT NULL,
    PRIMARY KEY(model_code, component)
);
CREATE TABLE error_codes (
    model_code TEXT NOT NULL REFERENCES models(model_code),
    code TEXT NOT NULL CHECK(code GLOB 'E[0-9][0-9]'),
    title TEXT NOT NULL,
    severity INTEGER NOT NULL CHECK(severity BETWEEN 1 AND 3),
    self_fixable INTEGER NOT NULL CHECK(self_fixable IN (0, 1)),
    requires_visit INTEGER NOT NULL CHECK(requires_visit IN (0, 1)),
    doc_ref TEXT NOT NULL,
    PRIMARY KEY(model_code, code)
);
CREATE TABLE consumables (
    sku TEXT PRIMARY KEY NOT NULL CHECK(sku LIKE 'SKU-%'),
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
    stock INTEGER NOT NULL CHECK(stock >= 0),
    max_per_order INTEGER CHECK(max_per_order > 0)
);
CREATE TABLE consumable_models (
    sku TEXT NOT NULL REFERENCES consumables(sku),
    model_code TEXT NOT NULL REFERENCES models(model_code),
    PRIMARY KEY(sku, model_code)
);
CREATE TABLE pending_actions (
    action_id TEXT PRIMARY KEY NOT NULL,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    tool TEXT NOT NULL CHECK(tool IN ('propose_service_visit', 'propose_order', 'propose_change')),
    args_json TEXT NOT NULL CHECK(json_valid(args_json)),
    args_sha256 TEXT NOT NULL CHECK(length(args_sha256) = 64),
    summary TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending', 'executed', 'rejected', 'expired', 'superseded', 'failed')),
    result_json TEXT CHECK(result_json IS NULL OR json_valid(result_json)),
    decided_at TEXT
);
CREATE TABLE orders (
    order_id TEXT PRIMARY KEY NOT NULL CHECK(order_id LIKE 'O-%'),
    user_id TEXT NOT NULL REFERENCES users(user_id),
    device_id TEXT NOT NULL,
    model_code TEXT NOT NULL,
    sku TEXT NOT NULL,
    qty INTEGER NOT NULL CHECK(qty > 0),
    amount_cents INTEGER NOT NULL CHECK(amount_cents >= 0),
    status TEXT NOT NULL CHECK(status IN ('processing', 'completed', 'cancelled')),
    source_action_id TEXT UNIQUE REFERENCES pending_actions(action_id),
    FOREIGN KEY(device_id, user_id) REFERENCES devices(device_id, user_id),
    FOREIGN KEY(device_id, model_code) REFERENCES devices(device_id, model_code),
    FOREIGN KEY(sku, model_code) REFERENCES consumable_models(sku, model_code)
);
CREATE TABLE tickets (
    ticket_id TEXT PRIMARY KEY NOT NULL CHECK(ticket_id LIKE 'T-%'),
    user_id TEXT NOT NULL REFERENCES users(user_id),
    device_id TEXT NOT NULL,
    model_code TEXT NOT NULL,
    error_code TEXT,
    description TEXT NOT NULL,
    notes TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('processing', 'completed', 'scheduled', 'cancelled')),
    source_action_id TEXT UNIQUE REFERENCES pending_actions(action_id),
    UNIQUE(ticket_id, user_id),
    FOREIGN KEY(device_id, user_id) REFERENCES devices(device_id, user_id),
    FOREIGN KEY(device_id, model_code) REFERENCES devices(device_id, model_code),
    FOREIGN KEY(model_code, error_code) REFERENCES error_codes(model_code, code)
);
CREATE TABLE service_slots (
    slot_id TEXT PRIMARY KEY NOT NULL CHECK(slot_id LIKE 'S-%'),
    region TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL CHECK(end_at > start_at),
    capacity INTEGER NOT NULL CHECK(capacity > 0),
    external_booked INTEGER NOT NULL CHECK(external_booked >= 0),
    booked INTEGER NOT NULL CHECK(booked >= 0 AND booked <= capacity)
);
CREATE TABLE appointments (
    appointment_id TEXT PRIMARY KEY NOT NULL CHECK(appointment_id LIKE 'A-%'),
    ticket_id TEXT NOT NULL,
    slot_id TEXT NOT NULL REFERENCES service_slots(slot_id),
    user_id TEXT NOT NULL REFERENCES users(user_id),
    status TEXT NOT NULL CHECK(status IN ('scheduled', 'completed', 'cancelled')),
    source_action_id TEXT UNIQUE REFERENCES pending_actions(action_id),
    FOREIGN KEY(ticket_id, user_id) REFERENCES tickets(ticket_id, user_id)
);
CREATE TABLE telemetry_daily (
    device_id TEXT NOT NULL REFERENCES devices(device_id),
    date TEXT NOT NULL,
    area_m2 REAL NOT NULL CHECK(area_m2 >= 0),
    duration_min INTEGER NOT NULL CHECK(duration_min >= 0),
    error_events INTEGER NOT NULL CHECK(error_events >= 0),
    PRIMARY KEY(device_id, date)
);
CREATE TABLE audit_log (
    id TEXT PRIMARY KEY NOT NULL CHECK(id LIKE 'L-%'),
    ts TEXT NOT NULL,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    action_id TEXT REFERENCES pending_actions(action_id),
    event TEXT NOT NULL CHECK(event IN ('proposed', 'confirmed', 'executed', 'rejected', 'expired', 'superseded', 'failed', 'denied')),
    tool TEXT NOT NULL,
    args_sha256 TEXT NOT NULL CHECK(length(args_sha256) = 64),
    detail TEXT NOT NULL
);
CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
CREATE TRIGGER audit_log_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;

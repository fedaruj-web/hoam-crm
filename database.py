import hashlib
import os
import secrets
import sqlite3
from pathlib import Path

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None

DB_PATH = Path(__file__).with_name("hoam_crm.db")


def _load_database_url():
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        return url
    try:
        import streamlit as st
        return str(st.secrets.get("DATABASE_URL", "")).strip()
    except Exception:
        return ""


DATABASE_URL = _load_database_url()
IS_POSTGRES = bool(DATABASE_URL)

LEAD_STATUSES = [
    "Novo lead",
    "Contato iniciado",
    "Reuniao agendada",
    "Proposta enviada",
    "Negociacao",
    "Ganho",
    "Perdido",
]

LEAD_CONTACTED_STATUSES = {
    "Contato iniciado",
    "Reuniao agendada",
    "Proposta enviada",
    "Negociacao",
    "Ganho",
    "Perdido",
}

LEAD_SOURCES = [
    "Indicacao",
    "LinkedIn",
    "Instagram",
    "Site",
    "Evento",
    "Prospeccao ativa",
    "Cliente atual",
    "Outro",
]

ACTIVITY_TYPES = [
    "Ligacao",
    "E-mail",
    "WhatsApp",
    "Reuniao",
    "Envio de proposta",
    "Follow-up",
    "Mudanca de status",
    "Outro",
]

OPPORTUNITY_STAGES = ["Aberta", "Em negociacao", "Ganha", "Perdida"]
PROPOSAL_STATUSES = ["Rascunho", "Enviada", "Em negociacao", "Aprovada", "Recusada", "Expirada"]
PROPOSAL_SERVICE_TYPES = [
    "Consultoria",
    "Estruturacao",
    "Distribuicao",
    "Gestao",
    "Administracao fiduciaria",
    "Outro",
]
USER_ROLES = ["Administrador", "Gestor", "Comercial", "Backoffice"]


def get_connection():
    if IS_POSTGRES:
        if psycopg is None:
            raise RuntimeError("Instale psycopg[binary] para usar Supabase/Postgres.")
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _sql(sql):
    return sql.replace("?", "%s") if IS_POSTGRES else sql


def _fetchone(conn, sql, params=()):
    return conn.execute(_sql(sql), params).fetchone()


def _fetchall(conn, sql, params=()):
    return conn.execute(_sql(sql), params).fetchall()


def _column_names(conn, table):
    if IS_POSTGRES:
        rows = _fetchall(conn, """
            SELECT column_name AS name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = ?
        """, (table,))
    else:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def _add_column(conn, table, name, definition):
    if name not in _column_names(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120000,
    ).hex()
    return f"{salt}${digest}"


def verify_password(password, stored_hash):
    if not stored_hash or "$" not in stored_hash:
        return False
    salt, expected = stored_hash.split("$", 1)
    return secrets.compare_digest(hash_password(password, salt).split("$", 1)[1], expected)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    if IS_POSTGRES:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL DEFAULT 'Comercial',
                password_hash TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id SERIAL PRIMARY KEY,
                company_name TEXT NOT NULL,
                contact_name TEXT,
                email TEXT,
                phone TEXT,
                source TEXT,
                status TEXT NOT NULL DEFAULT 'Novo lead',
                category TEXT,
                priority TEXT,
                anbima_role TEXT,
                aum DOUBLE PRECISION DEFAULT 0,
                cnpj TEXT,
                city_uf TEXT,
                do_not_contact INTEGER NOT NULL DEFAULT 0,
                do_not_contact_reason TEXT,
                owner TEXT,
                owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                estimated_value DOUBLE PRECISION DEFAULT 0,
                probability INTEGER DEFAULT 0,
                expected_close_date TEXT,
                next_followup_date TEXT,
                notes TEXT,
                client_since TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_DATE,
                updated_at TEXT NOT NULL DEFAULT CURRENT_DATE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                id SERIAL PRIMARY KEY,
                lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                activity_type TEXT NOT NULL,
                activity_date TEXT NOT NULL DEFAULT CURRENT_DATE,
                subject TEXT NOT NULL,
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS opportunities (
                id SERIAL PRIMARY KEY,
                lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                value DOUBLE PRECISION DEFAULT 0,
                stage TEXT NOT NULL DEFAULT 'Aberta',
                probability INTEGER DEFAULT 0,
                expected_close_date TEXT,
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id SERIAL PRIMARY KEY,
                lead_id INTEGER NOT NULL UNIQUE REFERENCES leads(id) ON DELETE CASCADE,
                company_name TEXT NOT NULL,
                contact_name TEXT,
                email TEXT,
                phone TEXT,
                owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                estimated_value DOUBLE PRECISION DEFAULT 0,
                converted_at TEXT NOT NULL DEFAULT CURRENT_DATE,
                notes TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS proposals (
                id SERIAL PRIMARY KEY,
                lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
                owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                title TEXT NOT NULL,
                service_type TEXT,
                status TEXT NOT NULL DEFAULT 'Rascunho',
                setup_fee DOUBLE PRECISION DEFAULT 0,
                recurring_fee DOUBLE PRECISION DEFAULT 0,
                estimated_total DOUBLE PRECISION DEFAULT 0,
                valid_until TEXT,
                sent_at TEXT,
                approved_at TEXT,
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        if not cur.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            cur.execute("""
                INSERT INTO users (name, email, role, password_hash, active)
                VALUES (%s, %s, %s, %s, 1)
            """, ("Fernando Daruj", "fedaruj@yahoo.com", "Administrador", hash_password("fernando123")))
        conn.commit()
        conn.close()
        return

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL DEFAULT 'Comercial',
            password_hash TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            contact_name TEXT,
            email TEXT,
            phone TEXT,
            source TEXT,
            status TEXT NOT NULL DEFAULT 'Novo lead',
            category TEXT,
            priority TEXT,
            anbima_role TEXT,
            aum REAL DEFAULT 0,
            cnpj TEXT,
            city_uf TEXT,
            do_not_contact INTEGER NOT NULL DEFAULT 0,
            do_not_contact_reason TEXT,
            owner TEXT,
            owner_id INTEGER,
            estimated_value REAL DEFAULT 0,
            probability INTEGER DEFAULT 0,
            expected_close_date TEXT,
            next_followup_date TEXT,
            notes TEXT,
            client_since TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_DATE,
            updated_at TEXT NOT NULL DEFAULT CURRENT_DATE,
            FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            user_id INTEGER,
            activity_type TEXT NOT NULL,
            activity_date TEXT NOT NULL DEFAULT CURRENT_DATE,
            subject TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            value REAL DEFAULT 0,
            stage TEXT NOT NULL DEFAULT 'Aberta',
            probability INTEGER DEFAULT 0,
            expected_close_date TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL UNIQUE,
            company_name TEXT NOT NULL,
            contact_name TEXT,
            email TEXT,
            phone TEXT,
            owner_id INTEGER,
            estimated_value REAL DEFAULT 0,
            converted_at TEXT NOT NULL DEFAULT CURRENT_DATE,
            notes TEXT,
            FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
            FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            owner_id INTEGER,
            title TEXT NOT NULL,
            service_type TEXT,
            status TEXT NOT NULL DEFAULT 'Rascunho',
            setup_fee REAL DEFAULT 0,
            recurring_fee REAL DEFAULT 0,
            estimated_total REAL DEFAULT 0,
            valid_until TEXT,
            sent_at TEXT,
            approved_at TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
            FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)

    _add_column(conn, "leads", "owner_id", "INTEGER REFERENCES users(id) ON DELETE SET NULL")
    _add_column(conn, "leads", "client_since", "TEXT")
    _add_column(conn, "leads", "category", "TEXT")
    _add_column(conn, "leads", "priority", "TEXT")
    _add_column(conn, "leads", "anbima_role", "TEXT")
    _add_column(conn, "leads", "aum", "REAL DEFAULT 0")
    _add_column(conn, "leads", "cnpj", "TEXT")
    _add_column(conn, "leads", "city_uf", "TEXT")
    _add_column(conn, "leads", "do_not_contact", "INTEGER NOT NULL DEFAULT 0")
    _add_column(conn, "leads", "do_not_contact_reason", "TEXT")
    _add_column(conn, "activities", "user_id", "INTEGER REFERENCES users(id) ON DELETE SET NULL")

    if not cur.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        cur.execute("""
            INSERT INTO users (name, email, role, password_hash, active)
            VALUES (?, ?, ?, ?, 1)
        """, ("Fernando Daruj", "fedaruj@yahoo.com", "Administrador", hash_password("fernando123")))

    conn.commit()
    conn.close()


def _execute_write(sql, params=()):
    conn = get_connection()
    sql_to_run = _sql(sql)
    if IS_POSTGRES and sql_to_run.lstrip().upper().startswith("INSERT") and " RETURNING " not in sql_to_run.upper():
        sql_to_run = sql_to_run.rstrip().rstrip(";") + " RETURNING id"
    cur = conn.execute(sql_to_run, params)
    conn.commit()
    if IS_POSTGRES and sql_to_run.lstrip().upper().startswith("INSERT"):
        row = cur.fetchone()
        lastrowid = row["id"] if row else None
    else:
        lastrowid = cur.lastrowid
    conn.close()
    _clear_streamlit_caches()
    return lastrowid


def _clear_streamlit_caches():
    try:
        import streamlit as st
        st.cache_data.clear()
    except Exception:
        pass


def add_user(data):
    return _execute_write("""
        INSERT INTO users (name, email, role, password_hash, active)
        VALUES (?, ?, ?, ?, ?)
    """, (
        data["name"],
        data["email"].lower(),
        data.get("role", "Comercial"),
        hash_password(data["password"]),
        1 if data.get("active", True) else 0,
    ))


def update_user(user_id, data):
    if data.get("password"):
        return _execute_write("""
            UPDATE users SET name=?, email=?, role=?, active=?, password_hash=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (
            data["name"], data["email"].lower(), data.get("role", "Comercial"),
            1 if data.get("active", True) else 0, hash_password(data["password"]), user_id,
        ))
    return _execute_write("""
        UPDATE users SET name=?, email=?, role=?, active=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (
        data["name"], data["email"].lower(), data.get("role", "Comercial"),
        1 if data.get("active", True) else 0, user_id,
    ))


def authenticate_user(email, password):
    conn = get_connection()
    row = _fetchone(
        conn,
        "SELECT * FROM users WHERE lower(email)=lower(?) AND active=1",
        (email.strip(),),
    )
    conn.close()
    if row and verify_password(password, row["password_hash"]):
        data = dict(row)
        data.pop("password_hash", None)
        return data
    return None


def get_users(active_only=False):
    conn = get_connection()
    sql = "SELECT id, name, email, role, active, created_at, updated_at FROM users"
    if active_only:
        sql += " WHERE active=1"
    sql += " ORDER BY active DESC, name"
    rows = _fetchall(conn, sql)
    conn.close()
    return [dict(r) for r in rows]


def get_user(user_id):
    conn = get_connection()
    row = _fetchone(
        conn,
        "SELECT id, name, email, role, active, created_at, updated_at FROM users WHERE id=?",
        (user_id,),
    )
    conn.close()
    return dict(row) if row else None


def add_lead(data):
    status = data.get("status", "Novo lead")
    priority = _priority_for_status(status)
    return _execute_write("""
        INSERT INTO leads (
            company_name, contact_name, email, phone, source, status, category, priority,
            anbima_role, aum, cnpj, city_uf, do_not_contact, do_not_contact_reason, owner, owner_id,
            estimated_value, probability, expected_close_date, next_followup_date, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["company_name"], data.get("contact_name"), data.get("email"),
        data.get("phone"), data.get("source"), status,
        priority, priority, data.get("anbima_role"), data.get("aum", 0), data.get("cnpj"), data.get("city_uf"),
        1 if data.get("do_not_contact", False) else 0, data.get("do_not_contact_reason"),
        data.get("owner"), data.get("owner_id"), data.get("estimated_value", 0),
        data.get("probability", 0), data.get("expected_close_date"),
        data.get("next_followup_date"), data.get("notes"),
    ))


def update_lead(lead_id, data):
    status = data.get("status", "Novo lead")
    priority = _priority_for_status(status)
    return _execute_write("""
        UPDATE leads SET
            company_name=?, contact_name=?, email=?, phone=?, source=?, status=?,
            category=?, priority=?, anbima_role=?, aum=?, cnpj=?, city_uf=?, owner=?, owner_id=?,
            do_not_contact=?, do_not_contact_reason=?, estimated_value=?, probability=?, expected_close_date=?,
            next_followup_date=?, notes=?, updated_at=CURRENT_DATE
        WHERE id=?
    """, (
        data["company_name"], data.get("contact_name"), data.get("email"),
        data.get("phone"), data.get("source"), status,
        priority, priority, data.get("anbima_role"), data.get("aum", 0), data.get("cnpj"), data.get("city_uf"),
        data.get("owner"), data.get("owner_id"),
        1 if data.get("do_not_contact", False) else 0, data.get("do_not_contact_reason"),
        data.get("estimated_value", 0),
        data.get("probability", 0), data.get("expected_close_date"),
        data.get("next_followup_date"), data.get("notes"), lead_id,
    ))


def delete_lead(lead_id):
    return _execute_write("DELETE FROM leads WHERE id=?", (lead_id,))


def _priority_for_status(status):
    return "Alta" if status in LEAD_CONTACTED_STATUSES else "Media"


def merge_leads(master_id, duplicate_id):
    if int(master_id) == int(duplicate_id):
        raise ValueError("Selecione leads diferentes para mesclar.")

    conn = get_connection()
    master = _fetchone(conn, "SELECT * FROM leads WHERE id=?", (master_id,))
    duplicate = _fetchone(conn, "SELECT * FROM leads WHERE id=?", (duplicate_id,))
    if not master or not duplicate:
        conn.close()
        raise ValueError("Lead principal ou duplicado nao encontrado.")

    master_data = dict(master)
    duplicate_data = dict(duplicate)
    fillable = [
        "contact_name", "email", "phone", "source", "category", "priority", "anbima_role", "aum", "cnpj",
        "city_uf", "do_not_contact", "do_not_contact_reason", "owner", "owner_id", "estimated_value", "probability",
        "expected_close_date", "next_followup_date", "notes",
    ]
    updates = {}
    for field in fillable:
        if _is_empty(master_data.get(field)) and not _is_empty(duplicate_data.get(field)):
            updates[field] = duplicate_data.get(field)

    if updates:
        assignments = ", ".join([f"{field}=?" for field in updates])
        conn.execute(
            _sql(f"UPDATE leads SET {assignments}, updated_at=CURRENT_DATE WHERE id=?"),
            list(updates.values()) + [master_id],
        )

    conn.execute(_sql("UPDATE activities SET lead_id=? WHERE lead_id=?"), (master_id, duplicate_id))
    conn.execute(_sql("UPDATE opportunities SET lead_id=? WHERE lead_id=?"), (master_id, duplicate_id))
    conn.execute(_sql("UPDATE proposals SET lead_id=? WHERE lead_id=?"), (master_id, duplicate_id))

    master_client = _fetchone(conn, "SELECT id FROM clients WHERE lead_id=?", (master_id,))
    duplicate_client = _fetchone(conn, "SELECT id FROM clients WHERE lead_id=?", (duplicate_id,))
    if duplicate_client and not master_client:
        conn.execute(_sql("UPDATE clients SET lead_id=? WHERE lead_id=?"), (master_id, duplicate_id))
    elif duplicate_client and master_client:
        conn.execute(_sql("DELETE FROM clients WHERE lead_id=?"), (duplicate_id,))

    conn.execute(_sql("DELETE FROM leads WHERE id=?"), (duplicate_id,))
    conn.commit()
    conn.close()
    _clear_streamlit_caches()
    return master_id


def _is_empty(value):
    return value is None or value == "" or value == 0


def get_leads():
    conn = get_connection()
    rows = _fetchall(conn, """
        SELECT l.*, COALESCE(u.name, l.owner) AS owner_name
        FROM leads l
        LEFT JOIN users u ON u.id = l.owner_id
        ORDER BY l.id DESC
    """)
    conn.close()
    return [dict(r) for r in rows]


def get_lead(lead_id):
    conn = get_connection()
    row = _fetchone(conn, """
        SELECT l.*, COALESCE(u.name, l.owner) AS owner_name
        FROM leads l
        LEFT JOIN users u ON u.id = l.owner_id
        WHERE l.id=?
    """, (lead_id,))
    conn.close()
    return dict(row) if row else None


def lead_exists(data):
    cnpj = (data.get("cnpj") or "").strip()
    email = (data.get("email") or "").strip()
    company_name = (data.get("company_name") or "").strip()
    conn = get_connection()
    row = None
    if cnpj:
        row = _fetchone(conn, "SELECT id FROM leads WHERE cnpj=?", (cnpj,))
    if not row and email:
        row = _fetchone(conn, "SELECT id FROM leads WHERE lower(email)=lower(?)", (email,))
    if not row and company_name:
        row = _fetchone(conn, "SELECT id FROM leads WHERE lower(company_name)=lower(?)", (company_name,))
    conn.close()
    return dict(row) if row else None


def add_activity(data):
    return _execute_write("""
        INSERT INTO activities (lead_id, user_id, activity_type, activity_date, subject, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        data["lead_id"], data.get("user_id"), data["activity_type"],
        data["activity_date"], data["subject"], data.get("notes"),
    ))


def get_activities(lead_id=None):
    conn = get_connection()
    params = []
    where = ""
    if lead_id:
        where = "WHERE a.lead_id=?"
        params.append(lead_id)
    rows = _fetchall(conn, f"""
        SELECT a.id, a.lead_id, l.company_name, u.name AS user_name, a.activity_type,
               a.activity_date, a.subject, a.notes, a.created_at
        FROM activities a
        JOIN leads l ON l.id = a.lead_id
        LEFT JOIN users u ON u.id = a.user_id
        {where}
        ORDER BY a.activity_date DESC, a.id DESC
    """, params)
    conn.close()
    return [dict(r) for r in rows]


def add_opportunity(data):
    return _execute_write("""
        INSERT INTO opportunities (lead_id, title, value, stage, probability, expected_close_date, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        data["lead_id"], data["title"], data.get("value", 0), data.get("stage", "Aberta"),
        data.get("probability", 0), data.get("expected_close_date"), data.get("notes"),
    ))


def get_opportunities(lead_id=None):
    conn = get_connection()
    params = []
    where = ""
    if lead_id:
        where = "WHERE o.lead_id=?"
        params.append(lead_id)
    rows = _fetchall(conn, f"""
        SELECT o.id, o.lead_id, l.company_name, o.title, o.value, o.stage, o.probability,
               o.expected_close_date, o.notes, o.created_at
        FROM opportunities o
        JOIN leads l ON l.id = o.lead_id
        {where}
        ORDER BY o.id DESC
    """, params)
    conn.close()
    return [dict(r) for r in rows]


def upsert_client_from_lead(lead_id):
    lead = get_lead(lead_id)
    if not lead:
        return None
    conn = get_connection()
    conn.execute(_sql("""
        UPDATE leads
        SET status='Ganho', priority='Alta', category='Alta',
            client_since=COALESCE(client_since, CURRENT_DATE)
        WHERE id=?
    """), (lead_id,))
    conn.execute(_sql("""
        INSERT INTO clients (lead_id, company_name, contact_name, email, phone, owner_id, estimated_value, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(lead_id) DO UPDATE SET
            company_name=excluded.company_name,
            contact_name=excluded.contact_name,
            email=excluded.email,
            phone=excluded.phone,
            owner_id=excluded.owner_id,
            estimated_value=excluded.estimated_value,
            notes=excluded.notes
    """), (
        lead_id, lead["company_name"], lead.get("contact_name"), lead.get("email"),
        lead.get("phone"), lead.get("owner_id"), lead.get("estimated_value", 0), lead.get("notes"),
    ))
    conn.commit()
    conn.close()
    _clear_streamlit_caches()
    return lead_id


def get_clients():
    conn = get_connection()
    rows = _fetchall(conn, """
        SELECT c.*, u.name AS owner_name
        FROM clients c
        LEFT JOIN users u ON u.id = c.owner_id
        ORDER BY c.converted_at DESC, c.id DESC
    """)
    conn.close()
    return [dict(r) for r in rows]


def add_proposal(data):
    return _execute_write("""
        INSERT INTO proposals (
            lead_id, owner_id, title, service_type, status, setup_fee, recurring_fee,
            estimated_total, valid_until, sent_at, approved_at, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["lead_id"], data.get("owner_id"), data["title"], data.get("service_type"),
        data.get("status", "Rascunho"), data.get("setup_fee", 0), data.get("recurring_fee", 0),
        data.get("estimated_total", 0), data.get("valid_until"), data.get("sent_at"),
        data.get("approved_at"), data.get("notes"),
    ))


def update_proposal(proposal_id, data):
    return _execute_write("""
        UPDATE proposals SET
            lead_id=?, owner_id=?, title=?, service_type=?, status=?, setup_fee=?,
            recurring_fee=?, estimated_total=?, valid_until=?, sent_at=?, approved_at=?,
            notes=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (
        data["lead_id"], data.get("owner_id"), data["title"], data.get("service_type"),
        data.get("status", "Rascunho"), data.get("setup_fee", 0), data.get("recurring_fee", 0),
        data.get("estimated_total", 0), data.get("valid_until"), data.get("sent_at"),
        data.get("approved_at"), data.get("notes"), proposal_id,
    ))


def get_proposals(lead_id=None):
    conn = get_connection()
    params = []
    where = ""
    if lead_id:
        where = "WHERE p.lead_id=?"
        params.append(lead_id)
    rows = _fetchall(conn, f"""
        SELECT p.*, l.company_name, l.status AS lead_status, u.name AS owner_name
        FROM proposals p
        JOIN leads l ON l.id = p.lead_id
        LEFT JOIN users u ON u.id = p.owner_id
        {where}
        ORDER BY p.updated_at DESC, p.id DESC
    """, params)
    conn.close()
    return [dict(r) for r in rows]


def get_proposal(proposal_id):
    conn = get_connection()
    row = _fetchone(conn, """
        SELECT p.*, l.company_name, l.status AS lead_status, u.name AS owner_name
        FROM proposals p
        JOIN leads l ON l.id = p.lead_id
        LEFT JOIN users u ON u.id = p.owner_id
        WHERE p.id=?
    """, (proposal_id,))
    conn.close()
    return dict(row) if row else None

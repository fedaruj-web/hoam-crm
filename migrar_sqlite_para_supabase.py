import argparse
import os
import sqlite3
from pathlib import Path

import psycopg


TABLES = {
    "users": [
        "id", "name", "email", "role", "password_hash", "active", "created_at", "updated_at",
    ],
    "leads": [
        "id", "company_name", "contact_name", "email", "phone", "source", "status", "category",
        "priority", "anbima_role", "aum", "cnpj", "city_uf", "do_not_contact",
        "do_not_contact_reason", "owner", "owner_id", "estimated_value", "probability",
        "expected_close_date", "next_followup_date", "notes", "client_since", "created_at",
        "updated_at",
    ],
    "activities": [
        "id", "lead_id", "user_id", "activity_type", "activity_date", "subject", "notes", "created_at",
    ],
    "opportunities": [
        "id", "lead_id", "title", "value", "stage", "probability", "expected_close_date", "notes",
        "created_at",
    ],
    "clients": [
        "id", "lead_id", "company_name", "contact_name", "email", "phone", "owner_id",
        "estimated_value", "converted_at", "notes",
    ],
    "services_catalog": [
        "id", "name", "category", "description", "scope_notes", "active", "created_at", "updated_at",
    ],
    "service_prices": [
        "id", "service_id", "charge_type", "base_value", "minimum_value", "success_percent",
        "pricing_rule", "status", "active", "created_at", "updated_at",
    ],
    "service_templates": [
        "id", "name", "category", "short_description", "full_scope", "deliverables",
        "assumptions", "exclusions", "default_price", "active", "created_at",
    ],
    "proposals": [
        "id", "lead_id", "owner_id", "service_id", "price_id", "title", "service_type", "status", "setup_fee",
        "price_quantity", "recurring_fee", "estimated_total", "valid_until", "sent_at", "approved_at", "notes",
        "client_name", "client_document", "client_contact", "client_email", "proposal_date", "validity_days",
        "responsible", "initial_fee", "monthly_fee", "success_fee", "payment_terms", "reimbursement_terms",
        "created_at", "updated_at",
    ],
    "proposal_services": [
        "id", "proposal_id", "service_template_id", "price_id", "quantity", "custom_description", "custom_price", "created_at",
    ],
}


def sqlite_rows(sqlite_path, table, columns):
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    existing_cols = {
        row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    selected = [col for col in columns if col in existing_cols]
    rows = conn.execute(f"SELECT {', '.join(selected)} FROM {table} ORDER BY id").fetchall()
    conn.close()
    return selected, [dict(row) for row in rows]


def reset_sequence(conn, table):
    conn.execute(
        "SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE((SELECT MAX(id) FROM "
        + table
        + "), 1), true)",
        (table,),
    )


def migrate(sqlite_path, database_url):
    os.environ["DATABASE_URL"] = database_url
    from database import init_db

    init_db()

    with psycopg.connect(database_url) as conn:
        with conn.transaction():
            conn.execute("TRUNCATE proposal_services, service_templates, service_prices, services_catalog, proposals, clients, opportunities, activities, leads, users RESTART IDENTITY CASCADE")
            for table, columns in TABLES.items():
                selected, rows = sqlite_rows(sqlite_path, table, columns)
                if not rows:
                    continue
                placeholders = ", ".join(["%s"] * len(selected))
                sql = f"INSERT INTO {table} ({', '.join(selected)}) VALUES ({placeholders})"
                with conn.cursor() as cur:
                    cur.executemany(sql, [[row.get(col) for col in selected] for row in rows])
            for table in TABLES:
                reset_sequence(conn, table)


def main():
    parser = argparse.ArgumentParser(description="Migra o SQLite local do Hoam CRM para Supabase/Postgres.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""), help="Connection string Postgres/Supabase.")
    parser.add_argument("--sqlite", default=str(Path(__file__).with_name("hoam_crm.db")), help="Caminho do hoam_crm.db local.")
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("Informe --database-url ou defina DATABASE_URL.")
    sqlite_path = Path(args.sqlite)
    if not sqlite_path.exists():
        raise SystemExit(f"SQLite nao encontrado: {sqlite_path}")

    migrate(sqlite_path, args.database_url)
    print("Migracao concluida com sucesso.")


if __name__ == "__main__":
    main()

from datetime import date
from difflib import SequenceMatcher
from io import BytesIO
import re
import unicodedata
from pathlib import Path

import pandas as pd
import streamlit as st

from database import (
    LEAD_STATUSES,
    add_lead,
    get_activities,
    get_clients,
    get_leads,
    get_opportunities,
    get_proposals,
    get_service_prices,
    get_services,
    get_users,
    lead_exists,
    merge_leads,
    update_lead,
)

ROLE_MENUS = {
    "Administrador": {
        "Dashboard", "Leads", "Novo Lead", "Atividades", "Oportunidades", "Propostas",
        "Follow-ups", "Clientes", "Servicos", "Relatorios", "Qualidade de Dados", "Importar/Exportar", "Usuarios",
    },
    "Gestor": {
        "Dashboard", "Leads", "Novo Lead", "Atividades", "Oportunidades", "Propostas",
        "Follow-ups", "Clientes", "Servicos", "Relatorios", "Qualidade de Dados", "Importar/Exportar",
    },
    "Comercial": {
        "Dashboard", "Leads", "Novo Lead", "Atividades", "Oportunidades", "Propostas",
        "Follow-ups", "Clientes", "Relatorios",
    },
    "Backoffice": {"Dashboard", "Leads", "Propostas", "Clientes", "Follow-ups", "Relatorios"},
}


def allowed_menus(user):
    role = (user or {}).get("role", "Comercial")
    base_order = [
        "Dashboard",
        "Leads",
        "Novo Lead",
        "Atividades",
        "Oportunidades",
        "Propostas",
        "Follow-ups",
        "Clientes",
        "Servicos",
        "Relatorios",
        "Qualidade de Dados",
        "Importar/Exportar",
        "Usuarios",
    ]
    allowed = ROLE_MENUS.get(role, ROLE_MENUS["Comercial"])
    return [item for item in base_order if item in allowed]


def can_manage_users(user):
    return (user or {}).get("role") == "Administrador"


def can_delete_leads(user):
    return (user or {}).get("role") in {"Administrador", "Gestor"}


def can_import_export(user):
    return (user or {}).get("role") in {"Administrador", "Gestor"}


def can_manage_services(user):
    return (user or {}).get("role") in {"Administrador", "Gestor"}


def priority_for_status(status):
    contacted_statuses = {
        "Contato iniciado",
        "Reuniao agendada",
        "Proposta enviada",
        "Negociacao",
        "Ganho",
        "Perdido",
    }
    return "Alta" if status in contacted_statuses else "Media"


def money(value):
    try:
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def parse_date(value, fallback=None):
    if not value:
        return fallback or date.today()
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return fallback or date.today()


@st.cache_data(ttl=60, show_spinner=False)
def leads_df():
    leads = get_leads()
    if not leads:
        return pd.DataFrame()
    df = pd.DataFrame(leads)
    if "estimated_value" in df.columns:
        df["estimated_value"] = pd.to_numeric(df["estimated_value"], errors="coerce").fillna(0)
        df["valor_estimado"] = df["estimated_value"].apply(money)
    if "owner_name" in df.columns:
        df["responsavel"] = df["owner_name"].fillna(df.get("owner", ""))
    if "aum" in df.columns:
        df["aum"] = pd.to_numeric(df["aum"], errors="coerce").fillna(0)
        df["aum_fmt"] = df["aum"].apply(lambda value: money(value * 1_000_000))
    if "do_not_contact" in df.columns:
        df["do_not_contact"] = pd.to_numeric(df["do_not_contact"], errors="coerce").fillna(0).astype(int)
        df["abordagem"] = df["do_not_contact"].apply(lambda value: "Nao abordar" if value else "Liberado")
    return df


def users_options(include_empty=True):
    users = get_users(active_only=True)
    options = {}
    if include_empty:
        options["Sem responsavel"] = None
    options.update({f"{user['name']} ({user['role']})": user["id"] for user in users})
    return options


def lead_metrics(df=None):
    df = leads_df() if df is None else df
    if df.empty:
        return {
            "total": 0,
            "pipeline": 0,
            "weighted": 0,
            "won": 0,
            "lost": 0,
            "open": 0,
            "conversion_rate": 0,
        }
    total = len(df)
    won_count = int((df["status"] == "Ganho").sum())
    lost_count = int((df["status"] == "Perdido").sum())
    pipeline_df = df[~df["status"].isin(["Ganho", "Perdido"])]
    pipeline = float(pipeline_df["estimated_value"].sum())
    weighted = float((pipeline_df["estimated_value"] * pipeline_df["probability"].fillna(0) / 100).sum())
    won = float(df.loc[df["status"] == "Ganho", "estimated_value"].sum())
    closed = won_count + lost_count
    conversion_rate = round((won_count / closed) * 100, 1) if closed else 0
    return {
        "total": total,
        "pipeline": pipeline,
        "weighted": weighted,
        "won": won,
        "lost": lost_count,
        "open": total - won_count - lost_count,
        "conversion_rate": conversion_rate,
    }


def funnel_summary(df=None):
    df = leads_df() if df is None else df
    if df.empty:
        return pd.DataFrame({"status": LEAD_STATUSES, "quantidade": [0] * len(LEAD_STATUSES), "valor": [0] * len(LEAD_STATUSES)})
    grouped = df.groupby("status", dropna=False).agg(
        quantidade=("id", "count"),
        valor=("estimated_value", "sum"),
    )
    grouped = grouped.reindex(LEAD_STATUSES, fill_value=0).reset_index(names="status")
    return grouped


@st.cache_data(ttl=60, show_spinner=False)
def followups_df():
    df = leads_df()
    if df.empty or "next_followup_date" not in df.columns:
        return pd.DataFrame()
    df = df[df["next_followup_date"].notna() & (df["next_followup_date"] != "")].copy()
    if df.empty:
        return df
    df["data_followup"] = pd.to_datetime(df["next_followup_date"], errors="coerce")
    today = pd.Timestamp(date.today())
    df["dias"] = (df["data_followup"] - today).dt.days
    return df.sort_values("data_followup")


def export_table(df, file_format):
    if df.empty:
        return b""
    if file_format == "Excel":
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Hoam CRM")
        return output.getvalue()
    return df.to_csv(index=False, sep=";").encode("utf-8-sig")


def import_leads(file, owner_id=None):
    name = getattr(file, "name", "").lower()
    if name.endswith(".csv"):
        df = pd.read_csv(file, sep=None, engine="python")
    else:
        try:
            df = _read_best_excel_sheet(file)
        except ImportError as exc:
            raise RuntimeError(
                "Para importar arquivos Excel, instale as dependencias com: python iniciar_crm.py"
            ) from exc

    df.columns = [_normalize_col(col) for col in df.columns]
    aliases = {
        "empresa": "company_name",
        "company": "company_name",
        "nome_empresa": "company_name",
        "razao_social": "company_name",
        "razão_social": "company_name",
        "nome_comercial": "company_name",
        "contato": "contact_name",
        "contato_principal": "contact_name",
        "e_mail": "email",
        "telefone": "phone",
        "fone": "phone",
        "origem": "source",
        "status": "status",
        "prioridade": "priority",
        "prioridade_hoam": "priority",
        "categoria": "category",
        "categoria_cvm": "category",
        "cnpj": "cnpj",
        "cidade_uf": "city_uf",
        "cidade/uf": "city_uf",
        "site": "website",
        "responsavel": "owner",
        "responsavel_hoam": "owner",
        "responsável_hoam": "owner",
        "valor": "estimated_value",
        "valor_estimado": "estimated_value",
        "probabilidade": "probability",
        "proximo_followup": "next_followup_date",
        "proximo_passo": "next_step",
        "próximo_passo": "next_step",
        "data_1_contato": "first_contact_date",
        "data_1º_contato": "first_contact_date",
        "observacoes": "notes",
        "observações": "notes",
    }
    df = df.rename(columns={col: aliases.get(col, col) for col in df.columns})
    if "company_name" not in df.columns:
        raise ValueError("Nao encontrei coluna de empresa. Use Empresa, Razao Social ou Nome Comercial.")

    imported = 0
    skipped = 0
    for _, row in df.iterrows():
        company = str(row.get("company_name", "")).strip()
        if not company or company.lower() == "nan":
            continue
        category = categorize_lead(row)
        status = _map_import_status(_clean(row.get("status")))
        priority = priority_for_status(status)
        next_step = _clean(row.get("next_step"))
        notes = _merge_notes(row, category, next_step)
        payload = {
            "company_name": company,
            "contact_name": _clean(row.get("contact_name")),
            "email": _clean(row.get("email")),
            "phone": _clean(row.get("phone")),
            "source": _clean(row.get("source")) or "Base CVM",
            "status": status,
            "category": priority,
            "priority": priority,
            "cnpj": _clean(row.get("cnpj")),
            "city_uf": _clean(row.get("city_uf")),
            "owner": _clean(row.get("owner")),
            "owner_id": owner_id,
            "estimated_value": _number(row.get("estimated_value")),
            "probability": category["probability"],
            "expected_close_date": _date_text(row.get("expected_close_date")),
            "next_followup_date": _date_text(row.get("next_followup_date")),
            "notes": notes,
        }
        if lead_exists(payload):
            skipped += 1
            continue
        add_lead(payload)
        imported += 1
    return {"imported": imported, "skipped": skipped}


def categorize_lead(row):
    priority = _clean(row.get("priority")).lower()
    category = _clean(row.get("category")).lower()
    company = _clean(row.get("company_name")).lower()
    notes = " ".join([priority, category, company])

    big_group_terms = ["banco", "bradesco", "itau", "itaú", "santander", "btg", "caixa", "bb ", "banco do brasil"]
    if any(term in notes for term in big_group_terms):
        return {"category": "Institucional", "priority": "Institucional", "probability": 20}
    if "alta" in priority:
        return {"category": "Alta", "priority": "Alta", "probability": 35}
    if "média" in priority or "media" in priority:
        return {"category": "Media", "priority": "Media", "probability": 20}
    if "cancel" in notes:
        return {"category": "Baixa", "priority": "Baixa", "probability": 0}
    if "administrador" in category and "gestor" in category:
        return {"category": "Media", "priority": "Media", "probability": 25}
    if "administrador" in category:
        return {"category": "Media", "priority": "Media", "probability": 20}
    if "gestor" in category:
        return {"category": "Alta", "priority": "Alta", "probability": 30}
    return {"category": "A qualificar", "priority": "A qualificar", "probability": 10}


@st.cache_data(ttl=30, show_spinner=False)
def activity_history_df(lead_id=None):
    data = get_activities(lead_id=lead_id)
    return pd.DataFrame(data) if data else pd.DataFrame()


@st.cache_data(ttl=30, show_spinner=False)
def opportunities_df(lead_id=None):
    data = get_opportunities(lead_id=lead_id)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df["valor"] = pd.to_numeric(df["value"], errors="coerce").fillna(0).apply(money)
    return df


@st.cache_data(ttl=60, show_spinner=False)
def clients_df():
    data = get_clients()
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df["valor_estimado"] = pd.to_numeric(df["estimated_value"], errors="coerce").fillna(0).apply(money)
    return df


@st.cache_data(ttl=60, show_spinner=False)
def services_catalog_df(active_only=False):
    data = get_services(active_only=active_only)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df["status"] = df["active"].apply(lambda value: "Ativo" if int(value or 0) else "Inativo")
    return df


@st.cache_data(ttl=60, show_spinner=False)
def service_prices_df(service_id=None, active_only=False):
    data = get_service_prices(service_id=service_id, active_only=active_only)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    for col in ["base_value", "minimum_value", "success_percent"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["valor_base_fmt"] = df["base_value"].apply(money)
    df["valor_minimo_fmt"] = df["minimum_value"].apply(money)
    df["percentual_fmt"] = df["success_percent"].apply(lambda value: f"{float(value):.1f}%".replace(".", ",") if float(value or 0) else "")
    df["ativo"] = df["active"].apply(lambda value: "Sim" if int(value or 0) else "Nao")
    return df


@st.cache_data(ttl=30, show_spinner=False)
def proposals_df(lead_id=None):
    data = get_proposals(lead_id=lead_id)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    for col in ["setup_fee", "recurring_fee", "estimated_total", "price_quantity", "initial_fee", "monthly_fee", "success_fee"]:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    for col in ["client_name", "responsible", "proposal_date"]:
        if col not in df.columns:
            df[col] = ""
    df["setup_fee_fmt"] = df["setup_fee"].apply(money)
    df["recurring_fee_fmt"] = df["recurring_fee"].apply(money)
    df["estimated_total_fmt"] = df["estimated_total"].apply(money)
    df["price_quantity_fmt"] = df["price_quantity"].apply(lambda value: f"{float(value):g}")
    df["initial_fee_fmt"] = df["initial_fee"].apply(money)
    df["monthly_fee_fmt"] = df["monthly_fee"].apply(money)
    df["success_fee_fmt"] = df["success_fee"].apply(lambda value: f"{float(value):.1f}%".replace(".", ","))
    return df


def proposal_metrics(df=None):
    df = proposals_df() if df is None else df
    if df.empty:
        return {"total": 0, "sent": 0, "approved": 0, "open_value": 0, "approved_value": 0}
    status = df["status"].fillna("").str.lower()
    negotiation = status.str.contains("negocia", na=False)
    sent_mask = status.isin(["enviada", "aprovada"]) | negotiation
    open_mask = status.isin(["rascunho", "enviada"]) | negotiation
    return {
        "total": len(df),
        "sent": int(sent_mask.sum()),
        "approved": int((df["status"] == "Aprovada").sum()),
        "open_value": float(df.loc[open_mask, "estimated_total"].sum()),
        "approved_value": float(df.loc[df["status"] == "Aprovada", "estimated_total"].sum()),
    }


def normalize_cnpj(value):
    digits = re.sub(r"\D", "", _clean(value))
    if len(digits) != 14:
        return _clean(value)
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


def normalize_phone(value):
    digits = re.sub(r"\D", "", _clean(value))
    if not digits:
        return ""
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    return _clean(value)


def normalize_email(value):
    return _clean(value).lower()


def normalize_city_uf(value):
    text = re.sub(r"\s+", " ", _clean(value)).strip()
    return text.upper()


def normalize_site(value):
    text = _clean(value).lower()
    if not text:
        return ""
    if text.startswith("http://") or text.startswith("https://"):
        return text
    return f"https://{text}"


def canonical_company_name(value):
    text = unicodedata.normalize("NFKD", _clean(value)).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    suffixes = [
        "ltda", "limitada", "s a", "sa", "s/a", "eireli", "me", "epp",
        "gestora de recursos", "gestao de recursos", "asset management",
        "distribuidora de titulos e valores mobiliarios",
    ]
    for suffix in suffixes:
        text = re.sub(rf"\b{re.escape(suffix)}\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def data_quality_summary():
    df = leads_df()
    if df.empty:
        return {"total": 0, "duplicate_groups": 0, "duplicate_records": 0, "missing_email": 0, "missing_phone": 0, "invalid_cnpj": 0}
    duplicates = duplicate_groups_df(df)
    invalid_cnpj = df["cnpj"].fillna("").apply(lambda v: bool(v) and len(re.sub(r"\D", "", str(v))) != 14).sum()
    return {
        "total": len(df),
        "duplicate_groups": int(duplicates["group_id"].nunique()) if not duplicates.empty else 0,
        "duplicate_records": len(duplicates),
        "missing_email": int((df["email"].fillna("") == "").sum()),
        "missing_phone": int((df["phone"].fillna("") == "").sum()),
        "invalid_cnpj": int(invalid_cnpj),
    }


def duplicate_groups_df(df=None):
    df = leads_df() if df is None else df.copy()
    if df.empty:
        return pd.DataFrame()

    rows = []
    group_id = 1
    seen_sets = set()

    for field, label, normalizer in [
        ("cnpj", "CNPJ igual", lambda v: re.sub(r"\D", "", _clean(v))),
        ("email", "E-mail igual", normalize_email),
    ]:
        if field not in df.columns:
            continue
        keys = df[field].apply(normalizer)
        for key, group in df.assign(_dup_key=keys).groupby("_dup_key"):
            if not key or len(group) < 2:
                continue
            ids = tuple(sorted(group["id"].tolist()))
            if ids in seen_sets:
                continue
            seen_sets.add(ids)
            rows.extend(_duplicate_rows(group, group_id, label, 1.0))
            group_id += 1

    df["_company_key"] = df["company_name"].apply(canonical_company_name)
    for key, group in df.groupby("_company_key"):
        if not key or len(group) < 2:
            continue
        ids = tuple(sorted(group["id"].tolist()))
        if ids in seen_sets:
            continue
        seen_sets.add(ids)
        rows.extend(_duplicate_rows(group, group_id, "Nome normalizado igual", 0.96))
        group_id += 1

    blocks = {}
    for _, row in df.iterrows():
        key = row.get("_company_key", "")[:6]
        if key:
            blocks.setdefault(key, []).append(row)
    for block_rows in blocks.values():
        for i, left in enumerate(block_rows):
            matches = [left]
            for right in block_rows[i + 1:]:
                score = SequenceMatcher(None, left["_company_key"], right["_company_key"]).ratio()
                if score >= 0.92:
                    matches.append(right)
            if len(matches) < 2:
                continue
            group = pd.DataFrame(matches)
            ids = tuple(sorted(group["id"].tolist()))
            if ids in seen_sets:
                continue
            seen_sets.add(ids)
            rows.extend(_duplicate_rows(group, group_id, "Nome parecido", 0.92))
            group_id += 1

    return pd.DataFrame(rows)


def standardize_all_leads():
    changed = 0
    for lead in get_leads():
        payload = dict(lead)
        payload["cnpj"] = normalize_cnpj(lead.get("cnpj"))
        payload["phone"] = normalize_phone(lead.get("phone"))
        payload["email"] = normalize_email(lead.get("email"))
        payload["city_uf"] = normalize_city_uf(lead.get("city_uf"))
        before = {k: lead.get(k) for k in ["cnpj", "phone", "email", "city_uf"]}
        after = {k: payload.get(k) for k in before}
        if before != after:
            update_lead(int(lead["id"]), payload)
            changed += 1
    return changed


def merge_duplicate_pair(master_id, duplicate_id):
    return merge_leads(int(master_id), int(duplicate_id))


def enrich_from_anbima(admin_path, gestao_path, output_dir=None):
    output_dir = Path(output_dir or Path.cwd())
    admin = _read_anbima_ranking(admin_path, "Administrador", "Administrador")
    gestao = _read_anbima_ranking(gestao_path, "Gestor", "Gestor")
    anbima = pd.concat([admin, gestao], ignore_index=True)
    if anbima.empty:
        return {"matched": 0, "unmatched_anbima": 0, "report_matches": "", "report_unmatched": ""}

    leads = leads_df()
    if leads.empty:
        return {"matched": 0, "unmatched_anbima": len(anbima), "report_matches": "", "report_unmatched": ""}

    leads["_match_name"] = leads["company_name"].apply(canonical_company_name)
    anbima["_match_name"] = anbima["name"].apply(canonical_company_name)

    matched_rows = []
    unmatched_rows = []
    for _, row in anbima.iterrows():
        key = row["_match_name"]
        candidates = leads[leads["_match_name"] == key].copy()
        score = 1.0
        if candidates.empty and key:
            leads["_score"] = leads["_match_name"].apply(lambda value: SequenceMatcher(None, key, value).ratio() if value else 0)
            candidates = leads[leads["_score"] >= 0.90].sort_values("_score", ascending=False).head(1)
            score = float(candidates["_score"].iloc[0]) if not candidates.empty else 0
        if candidates.empty:
            unmatched_rows.append(row.to_dict())
            continue
        lead = candidates.iloc[0]
        matched_rows.append({
            "lead_id": int(lead["id"]),
            "company_name": lead["company_name"],
            "anbima_name": row["name"],
            "role": row["role"],
            "aum": float(row["aum"]),
            "score": score,
        })

    matches = pd.DataFrame(matched_rows)
    if not matches.empty:
        grouped = matches.groupby("lead_id").agg(
            company_name=("company_name", "first"),
            roles=("role", lambda values: " e ".join(sorted(set(values)))),
            aum=("aum", "sum"),
            anbima_names=("anbima_name", lambda values: " | ".join(sorted(set(values)))),
            best_score=("score", "max"),
        ).reset_index()
        _apply_anbima_matches(grouped)
    else:
        grouped = pd.DataFrame()

    matches_report = output_dir / "anbima_matches.csv"
    unmatched_report = output_dir / "anbima_nao_encontrados.csv"
    grouped.to_csv(matches_report, index=False, sep=";", encoding="utf-8-sig")
    pd.DataFrame(unmatched_rows).to_csv(unmatched_report, index=False, sep=";", encoding="utf-8-sig")
    return {
        "matched": 0 if grouped.empty else len(grouped),
        "unmatched_anbima": len(unmatched_rows),
        "report_matches": str(matches_report),
        "report_unmatched": str(unmatched_report),
    }


def _read_anbima_ranking(path, name_column, role):
    path = Path(path)
    xl = pd.ExcelFile(path)
    sheet = next(sheet for sheet in xl.sheet_names if "PL por Categoria" in sheet)
    df = pd.read_excel(path, sheet_name=sheet, header=5)
    df.columns = [str(col).strip() for col in df.columns]
    total_col = next((col for col in df.columns if str(col).strip().lower().startswith("total")), None)
    if name_column not in df.columns or total_col is None:
        return pd.DataFrame(columns=["name", "role", "aum"])
    out = df[[name_column, total_col]].copy()
    out.columns = ["name", "aum"]
    out["name"] = out["name"].map(_clean)
    out["aum"] = pd.to_numeric(out["aum"], errors="coerce").fillna(0)
    out = out[(out["name"] != "") & (out["name"].str.lower() != "total") & (out["aum"] > 0)]
    out["role"] = role
    return out[["name", "role", "aum"]]


def _apply_anbima_matches(grouped):
    from database import get_lead

    for _, row in grouped.iterrows():
        lead = get_lead(int(row["lead_id"]))
        if not lead:
            continue
        payload = dict(lead)
        payload["anbima_role"] = row["roles"]
        payload["aum"] = float(row["aum"])
        update_lead(int(row["lead_id"]), payload)


def _duplicate_rows(group, group_id, reason, score):
    out = []
    for _, item in group.sort_values("id").iterrows():
        out.append({
            "group_id": group_id,
            "reason": reason,
            "score": score,
            "id": int(item["id"]),
            "company_name": item.get("company_name"),
            "cnpj": item.get("cnpj"),
            "email": item.get("email"),
            "phone": item.get("phone"),
            "status": item.get("status"),
            "priority": item.get("priority"),
            "owner_name": item.get("owner_name"),
        })
    return out


def _clean(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def _normalize_col(value):
    text = str(value).strip().lower()
    return (
        text.replace(" ", "_")
        .replace(".", "")
        .replace("-", "_")
        .replace("__", "_")
    )


def _read_best_excel_sheet(file):
    xl = pd.ExcelFile(file)
    preferred = [sheet for sheet in xl.sheet_names if "crm" in sheet.lower() and "prospec" in sheet.lower()]
    candidates = preferred + xl.sheet_names
    best = None
    best_score = -1

    for sheet in candidates:
        for header in range(0, 5):
            df = pd.read_excel(xl, sheet_name=sheet, header=header)
            columns = {_normalize_col(col) for col in df.columns}
            score = 0
            for expected in ["razao_social", "razão_social", "empresa", "company_name", "nome_comercial"]:
                score += 3 if expected in columns else 0
            for expected in ["cnpj", "email", "e_mail", "telefone", "prioridade", "status"]:
                score += 1 if expected in columns else 0
            if score > best_score:
                best = df
                best_score = score
        if preferred and best_score >= 6:
            break

    if best is None or best_score < 3:
        return pd.read_excel(xl, sheet_name=0)
    return best


def _map_import_status(value):
    normalized = value.strip().lower()
    if not normalized:
        return "Novo lead"
    mapping = {
        "a contatar": "Novo lead",
        "novo": "Novo lead",
        "novo lead": "Novo lead",
        "contatado": "Contato iniciado",
        "em contato": "Contato iniciado",
        "reuniao": "Reuniao agendada",
        "reunião": "Reuniao agendada",
        "proposta": "Proposta enviada",
        "negociacao": "Negociacao",
        "negociação": "Negociacao",
        "ganho": "Ganho",
        "perdido": "Perdido",
    }
    return mapping.get(normalized, value if value in LEAD_STATUSES else "Novo lead")


def _normalize_priority(value):
    normalized = value.strip().lower()
    if "alta" in normalized:
        return "Alta"
    if "média" in normalized or "media" in normalized:
        return "Media"
    if "institucional" in normalized:
        return "Institucional"
    if "baixa" in normalized:
        return "Baixa"
    return value or "A qualificar"


def _merge_notes(row, category, next_step):
    parts = []
    existing = _clean(row.get("notes"))
    if existing:
        parts.append(existing)
    if next_step:
        parts.append(f"Proximo passo: {next_step}")
    website = _clean(row.get("website"))
    if website:
        parts.append(f"Site: {website}")
    first_contact = _date_text(row.get("first_contact_date"))
    if first_contact:
        parts.append(f"Data 1o contato: {first_contact}")
    parts.append(f"Prioridade HOAM automatica: {category['priority']}.")
    return "\n".join(parts)


def _number(value):
    if pd.isna(value) or value == "":
        return 0
    try:
        if isinstance(value, str):
            value = value.replace("R$", "").replace(".", "").replace(",", ".").strip()
        return float(value)
    except Exception:
        return 0


def _date_text(value):
    if pd.isna(value) or value == "":
        return None
    try:
        return str(pd.to_datetime(value).date())
    except Exception:
        return None

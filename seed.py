from database import add_activity, add_lead, add_opportunity, get_users, init_db

init_db()

admin = get_users(active_only=True)[0]

lead_id = add_lead({
    "company_name": "Cliente Exemplo S.A.",
    "contact_name": "Ana Comercial",
    "email": "ana@clienteexemplo.com.br",
    "phone": "(11) 99999-0000",
    "source": "Indicacao",
    "status": "Contato iniciado",
    "owner": admin["name"],
    "owner_id": admin["id"],
    "estimated_value": 50000,
    "probability": 30,
    "expected_close_date": "2026-06-30",
    "next_followup_date": "2026-05-30",
    "notes": "Lead de exemplo.",
})

add_activity({
    "lead_id": lead_id,
    "user_id": admin["id"],
    "activity_type": "Ligacao",
    "activity_date": "2026-05-25",
    "subject": "Primeiro contato",
    "notes": "Contato inicial realizado.",
})

add_opportunity({
    "lead_id": lead_id,
    "title": "Projeto comercial inicial",
    "value": 50000,
    "stage": "Aberta",
    "probability": 30,
    "expected_close_date": "2026-06-30",
    "notes": "Oportunidade de exemplo.",
})

print("Dados de exemplo carregados.")

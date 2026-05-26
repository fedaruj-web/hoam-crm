from datetime import date, timedelta

import pandas as pd
import streamlit as st

from database import (
    ACTIVITY_TYPES,
    LEAD_SOURCES,
    LEAD_STATUSES,
    OPPORTUNITY_STAGES,
    PROPOSAL_SERVICE_TYPES,
    PROPOSAL_STATUSES,
    USER_ROLES,
    add_activity,
    add_lead,
    add_opportunity,
    add_proposal,
    add_user,
    delete_lead,
    get_activities,
    get_lead,
    get_leads,
    get_opportunities,
    get_proposal,
    get_user,
    get_users,
    update_lead,
    update_proposal,
    update_user,
    upsert_client_from_lead,
)
from services import (
    activity_history_df,
    clients_df,
    can_delete_leads,
    data_quality_summary,
    duplicate_groups_df,
    export_table,
    followups_df,
    funnel_summary,
    import_leads,
    lead_metrics,
    leads_df,
    money,
    opportunities_df,
    parse_date,
    proposal_metrics,
    proposals_df,
    merge_duplicate_pair,
    priority_for_status,
    standardize_all_leads,
    users_options,
)
from ui.styles import header, metric_card


def render_login(authenticate):
    header("Hoam CRM Comercial", "Acesso restrito ao time comercial da Hoam Capital.")
    with st.form("login"):
        email = st.text_input("E-mail")
        password = st.text_input("Senha", type="password")
        submit = st.form_submit_button("Entrar")
        if submit:
            user = authenticate(email, password)
            if user:
                st.session_state["user"] = user
                st.success("Login realizado.")
                st.rerun()
            st.error("E-mail ou senha invalidos.")


def render_dashboard():
    header("CRM Comercial", "Visao consolidada do funil, pipeline, oportunidades e follow-ups.")
    df = leads_df()
    metrics = lead_metrics(df)

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        metric_card("Leads cadastrados", metrics["total"], "base comercial")
    with c2:
        metric_card("Pipeline aberto", money(metrics["pipeline"]), "valor potencial")
    with c3:
        metric_card("Pipeline ponderado", money(metrics["weighted"]), "probabilidade aplicada")
    with c4:
        metric_card("Valor ganho", money(metrics["won"]), "negocios fechados")
    with c5:
        metric_card("Conversao", f"{metrics['conversion_rate']}%", "ganhos sobre fechados")

    if df.empty:
        st.markdown('<div class="hoam-card">Cadastre o primeiro lead no menu <b>Novo Lead</b>.</div>', unsafe_allow_html=True)
        return

    render_funnel(df)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown('<div class="hoam-card"><h3>Origem dos leads</h3>', unsafe_allow_html=True)
        st.bar_chart(df["source"].fillna("Nao informado").value_counts())
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="hoam-card"><h3>Prioridade HOAM</h3>', unsafe_allow_html=True)
        st.bar_chart(df["priority"].fillna("A qualificar").value_counts())
        st.markdown("</div>", unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="hoam-card"><h3>Pipeline por responsavel</h3>', unsafe_allow_html=True)
        owner_col = "responsavel" if "responsavel" in df.columns else "owner"
        owner_pipeline = df.groupby(owner_col)["estimated_value"].sum().sort_values(ascending=False)
        st.bar_chart(owner_pipeline)
        st.markdown("</div>", unsafe_allow_html=True)

    followups = followups_df()
    st.markdown('<div class="hoam-card"><h3>Proximos follow-ups</h3>', unsafe_allow_html=True)
    if followups.empty:
        st.caption("Nenhum follow-up registrado.")
    else:
        st.dataframe(
            followups.head(8)[["id", "company_name", "priority", "contact_name", "status", "responsavel", "next_followup_date", "dias"]],
            use_container_width=True,
            hide_index=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def render_funnel(df=None):
    summary = funnel_summary(df)
    st.markdown('<div class="hoam-card"><h3>Funil comercial</h3>', unsafe_allow_html=True)
    columns = st.columns(len(summary))
    for idx, row in summary.iterrows():
        with columns[idx]:
            st.markdown(f"""
            <div class="funnel-step">
                <div class="funnel-stage">{row['status']}</div>
                <div class="funnel-count">{int(row['quantidade'])}</div>
                <div class="funnel-value">{money(row['valor'])}</div>
            </div>
            """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_new_lead(current_user):
    header("Novo Lead", "Cadastro inicial de prospeccoes e oportunidades comerciais.")
    users = users_options()

    with st.form("novo_lead"):
        c1, c2 = st.columns(2)
        company_name = c1.text_input("Empresa *")
        contact_name = c2.text_input("Contato")
        email = c1.text_input("E-mail")
        phone = c2.text_input("Telefone")
        source = c1.selectbox("Origem", LEAD_SOURCES)
        status = c2.selectbox("Status", LEAD_STATUSES)
        priority = priority_for_status(status)
        c1.info(f"Prioridade HOAM automatica: {priority}")
        cnpj = c1.text_input("CNPJ")
        city_uf = c2.text_input("Cidade/UF")
        owner_label = c1.selectbox("Responsavel", list(users.keys()), index=_default_owner_index(users, current_user))
        estimated_value = c2.number_input("Valor estimado", min_value=0.0, step=1000.0)
        probability = c1.slider("Probabilidade (%)", 0, 100, 0, 5)
        use_close_date = c2.checkbox("Informar data estimada de fechamento")
        expected_close_date = c2.date_input("Data estimada de fechamento", value=date.today(), disabled=not use_close_date)
        use_followup = c1.checkbox("Informar proximo follow-up")
        next_followup_date = c1.date_input("Proximo follow-up", value=date.today() + timedelta(days=7), disabled=not use_followup)
        do_not_contact = c1.checkbox("Nao abordar este lead")
        do_not_contact_reason = c2.text_input("Motivo para nao abordar", disabled=not do_not_contact)
        notes = st.text_area("Observacoes")
        submit = st.form_submit_button("Cadastrar lead")

        if submit:
            if not company_name.strip():
                st.error("Informe o nome da empresa.")
                return
            owner_id = users[owner_label]
            lead_id = _save_new_lead(
                company_name, contact_name, email, phone, source, status, owner_id,
                priority, cnpj, city_uf,
                estimated_value, probability,
                expected_close_date if use_close_date else None,
                next_followup_date if use_followup else None,
                do_not_contact,
                do_not_contact_reason,
                notes,
            )
            add_activity({
                "lead_id": lead_id,
                "user_id": current_user["id"],
                "activity_type": "Outro",
                "activity_date": str(date.today()),
                "subject": "Lead cadastrado",
                "notes": "Registro criado no CRM.",
            })
            st.success("Lead cadastrado com sucesso.")


def render_leads(current_user):
    header("Leads", "Consulta, filtros, edicao da base comercial e historico por lead.")
    df = leads_df()
    if df.empty:
        st.info("Nenhum lead cadastrado.")
        return

    anbima_count = int((df["anbima_role"].fillna("") != "").sum()) if "anbima_role" in df.columns else 0
    total_aum = float(df["aum"].sum()) if "aum" in df.columns else 0
    a1, a2, a3 = st.columns(3)
    with a1:
        metric_card("Com dados ANBIMA", anbima_count, "tipo e AuM preenchidos")
    with a2:
        metric_card("AuM mapeado", money(total_aum * 1_000_000), "soma dos matches")
    with a3:
        metric_card("Sem ANBIMA", len(df) - anbima_count, "a qualificar manualmente")

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    status_filter = c1.selectbox("Status", ["Todos"] + LEAD_STATUSES)
    priorities = sorted([item for item in df["priority"].dropna().unique().tolist() if item])
    priority_filter = c2.selectbox("Prioridade", ["Todas"] + priorities)
    anbima_roles = sorted([item for item in df["anbima_role"].dropna().unique().tolist() if item]) if "anbima_role" in df.columns else []
    role_filter = c3.selectbox("Tipo ANBIMA", ["Todos"] + anbima_roles)
    approach_filter = c4.selectbox("Abordagem", ["Todos", "Liberado", "Nao abordar"])
    owner_filter = c5.text_input("Responsavel contem")
    search = c6.text_input("Busca por empresa, contato ou CNPJ")

    aum_range, custom_aum_min, custom_aum_max = _render_aum_filters(df)

    filtered = _filter_leads(
        df,
        status_filter,
        priority_filter,
        role_filter,
        owner_filter,
        search,
        aum_range,
        custom_aum_min,
        custom_aum_max,
        approach_filter,
    )
    if filtered.empty:
        st.warning("Nenhum lead encontrado com os filtros atuais.")
        return

    f1, f2, f3 = st.columns(3)
    f1.metric("Leads filtrados", len(filtered))
    f2.metric("AuM filtrado", money(float(filtered["aum"].sum()) * 1_000_000) if "aum" in filtered.columns else "-")
    f3.metric("AuM medio", money(float(filtered["aum"].mean()) * 1_000_000) if "aum" in filtered.columns and len(filtered) else "-")

    display = filtered[["id", "company_name", "anbima_role", "aum_fmt", "priority", "abordagem", "do_not_contact_reason", "cnpj", "city_uf", "contact_name", "email", "phone", "status", "responsavel", "next_followup_date"]].copy()
    display = display.rename(columns={
        "id": "ID",
        "company_name": "Empresa",
        "anbima_role": "Tipo ANBIMA",
        "aum_fmt": "AuM",
        "priority": "Prioridade",
        "abordagem": "Abordagem",
        "do_not_contact_reason": "Motivo",
        "cnpj": "CNPJ",
        "city_uf": "Cidade/UF",
        "contact_name": "Contato",
        "email": "E-mail",
        "phone": "Telefone",
        "status": "Status",
        "responsavel": "Responsavel",
        "next_followup_date": "Proximo follow-up",
    })

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    selected_id = st.selectbox("Lead selecionado", filtered["id"].tolist(), format_func=lambda x: f"{x} - {filtered.loc[filtered['id'] == x, 'company_name'].iloc[0]}")
    lead = get_lead(int(selected_id))
    if not lead:
        st.error("Lead nao encontrado.")
        return

    _render_do_not_contact_quick_toggle(lead, current_user)
    lead = get_lead(int(selected_id))

    tab_overview, tab_edit, tab_history, tab_proposals, tab_convert = st.tabs(["Visao 360", "Editar", "Historico", "Propostas", "Converter"])
    with tab_overview:
        _render_lead_overview(lead)
    with tab_edit:
        _render_edit_lead_form(lead, current_user)
    with tab_history:
        _render_lead_history(int(selected_id))
    with tab_proposals:
        _render_lead_proposals(int(selected_id), current_user)
    with tab_convert:
        st.write(f"Converter **{lead['company_name']}** em cliente ativo.")
        if st.button("Converter em cliente", type="primary"):
            upsert_client_from_lead(int(selected_id))
            add_activity({
                "lead_id": int(selected_id),
                "user_id": current_user["id"],
                "activity_type": "Mudanca de status",
                "activity_date": str(date.today()),
                "subject": "Lead convertido em cliente",
                "notes": "Cliente criado a partir do lead.",
            })
            st.success("Cliente convertido com sucesso.")
            st.rerun()


def render_activities(current_user):
    header("Atividades", "Historico de contatos, reunioes, follow-ups e movimentacoes comerciais.")
    leads = get_leads()
    if not leads:
        st.info("Cadastre um lead antes de registrar atividades.")
        return

    options = {f"{lead['id']} - {lead['company_name']}": lead["id"] for lead in leads}
    with st.form("atividade"):
        selected = st.selectbox("Lead", list(options.keys()))
        activity_type = st.selectbox("Tipo", ACTIVITY_TYPES)
        activity_date = st.date_input("Data", value=date.today())
        subject = st.text_input("Assunto *")
        notes = st.text_area("Observacoes")
        submit = st.form_submit_button("Registrar atividade")
        if submit:
            if not subject.strip():
                st.error("Informe o assunto.")
            else:
                add_activity({
                    "lead_id": options[selected],
                    "user_id": current_user["id"],
                    "activity_type": activity_type,
                    "activity_date": str(activity_date),
                    "subject": subject.strip(),
                    "notes": notes.strip(),
                })
                st.success("Atividade registrada.")

    data = activity_history_df()
    if not data.empty:
        st.dataframe(data, use_container_width=True, hide_index=True)


def render_opportunities():
    header("Oportunidades", "Gestao de propostas, valores, probabilidade e previsao de fechamento.")
    leads = get_leads()
    if not leads:
        st.info("Cadastre um lead antes de registrar oportunidades.")
        return

    options = {f"{lead['id']} - {lead['company_name']}": lead["id"] for lead in leads}
    with st.form("oportunidade"):
        selected = st.selectbox("Lead", list(options.keys()))
        title = st.text_input("Titulo *")
        value = st.number_input("Valor", min_value=0.0, step=1000.0)
        stage = st.selectbox("Fase", OPPORTUNITY_STAGES)
        probability = st.slider("Probabilidade (%)", 0, 100, 0, 5)
        use_date = st.checkbox("Informar data estimada de fechamento")
        expected_close_date = st.date_input("Data estimada de fechamento", value=date.today(), disabled=not use_date)
        notes = st.text_area("Observacoes")
        submit = st.form_submit_button("Cadastrar oportunidade")
        if submit:
            if not title.strip():
                st.error("Informe o titulo.")
            else:
                add_opportunity({
                    "lead_id": options[selected],
                    "title": title.strip(),
                    "value": value,
                    "stage": stage,
                    "probability": probability,
                    "expected_close_date": str(expected_close_date) if use_date else None,
                    "notes": notes.strip(),
                })
                st.success("Oportunidade cadastrada.")

    df = opportunities_df()
    if not df.empty:
        st.dataframe(
            df[["id", "company_name", "title", "valor", "stage", "probability", "expected_close_date", "notes"]],
            use_container_width=True,
            hide_index=True,
        )


def render_proposals(current_user):
    header("Propostas", "Controle de propostas comerciais, status, validade e valores negociados.")
    leads = get_leads()
    if not leads:
        st.info("Cadastre um lead antes de criar propostas.")
        return

    df = proposals_df()
    metrics = proposal_metrics(df)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Propostas", metrics["total"], "total cadastrado")
    with c2:
        metric_card("Enviadas", metrics["sent"], "em circulacao")
    with c3:
        metric_card("Valor aberto", money(metrics["open_value"]), "pipeline de propostas")
    with c4:
        metric_card("Valor aprovado", money(metrics["approved_value"]), "propostas aprovadas")

    tab_new, tab_list = st.tabs(["Nova proposta", "Base de propostas"])
    with tab_new:
        _render_proposal_form(leads, current_user)
    with tab_list:
        if df.empty:
            st.info("Nenhuma proposta cadastrada.")
            return
        status_filter = st.selectbox("Status", ["Todos"] + PROPOSAL_STATUSES)
        view = df if status_filter == "Todos" else df[df["status"] == status_filter]
        st.dataframe(
            view[[
                "id", "company_name", "title", "service_type", "status", "owner_name",
                "setup_fee_fmt", "recurring_fee_fmt", "estimated_total_fmt", "valid_until", "sent_at", "approved_at",
            ]],
            use_container_width=True,
            hide_index=True,
        )
        if not view.empty:
            selected = st.selectbox(
                "Editar proposta",
                view["id"].tolist(),
                format_func=lambda pid: f"{pid} - {view.loc[view['id'] == pid, 'title'].iloc[0]}",
            )
            proposal = get_proposal(int(selected))
            if proposal:
                _render_proposal_edit_form(proposal, leads, current_user)


def render_followups():
    header("Agenda de Follow-ups", "Controle de proximas interacoes, atrasos e pendencias comerciais.")
    df = followups_df()
    if df.empty:
        st.info("Nenhum follow-up registrado.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Atrasados", int((df["dias"] < 0).sum()))
    c2.metric("Hoje", int((df["dias"] == 0).sum()))
    c3.metric("Futuros", int((df["dias"] > 0).sum()))

    status = st.radio("Periodo", ["Todos", "Atrasados", "Hoje", "Futuros"], horizontal=True)
    if status == "Atrasados":
        df = df[df["dias"] < 0]
    elif status == "Hoje":
        df = df[df["dias"] == 0]
    elif status == "Futuros":
        df = df[df["dias"] > 0]

    st.dataframe(
        df[["id", "company_name", "contact_name", "status", "responsavel", "next_followup_date", "dias", "valor_estimado"]],
        use_container_width=True,
        hide_index=True,
    )


def render_reports():
    header("Relatorios", "Analises comerciais filtradas por perfil, AuM, pipeline, propostas e follow-ups.")
    df = leads_df()
    if df.empty:
        st.info("Nenhum lead cadastrado para gerar relatorios.")
        return

    st.markdown("#### Filtros do relatorio")
    c1, c2, c3, c4, c5 = st.columns(5)
    status_filter = c1.selectbox("Status", ["Todos"] + LEAD_STATUSES, key="reports_status")
    anbima_roles = sorted([item for item in df["anbima_role"].dropna().unique().tolist() if item]) if "anbima_role" in df.columns else []
    role_filter = c2.selectbox("Tipo ANBIMA", ["Todos"] + anbima_roles, key="reports_role")
    owner_col = "responsavel" if "responsavel" in df.columns else "owner"
    owners = sorted([item for item in df[owner_col].dropna().unique().tolist() if item]) if owner_col in df.columns else []
    owner_filter = c3.selectbox("Responsavel", ["Todos"] + owners, key="reports_owner")
    approach_filter = c4.selectbox("Abordagem", ["Todos", "Liberado", "Nao abordar"], key="reports_approach")
    search = c5.text_input("Busca", key="reports_search")

    aum_range, custom_aum_min, custom_aum_max = _render_aum_filters(df, key_prefix="reports")
    report_df = _filter_leads(
        df,
        status_filter,
        "Todas",
        role_filter,
        "" if owner_filter == "Todos" else owner_filter,
        search,
        aum_range,
        custom_aum_min,
        custom_aum_max,
        approach_filter,
    )

    if report_df.empty:
        st.warning("Nenhum dado encontrado para os filtros selecionados.")
        return

    metrics = lead_metrics(report_df)
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        metric_card("Leads", metrics["total"], "filtro atual")
    with c2:
        metric_card("AuM", money(float(report_df["aum"].sum()) * 1_000_000), "base filtrada")
    with c3:
        metric_card("Pipeline", money(metrics["pipeline"]), "aberto")
    with c4:
        metric_card("Ponderado", money(metrics["weighted"]), "probabilidade")
    with c5:
        metric_card("Conversao", f"{metrics['conversion_rate']}%", "ganhos sobre fechados")

    tab_summary, tab_pipeline, tab_followups, tab_proposals, tab_export = st.tabs([
        "Resumo", "Pipeline", "Follow-ups", "Propostas", "Exportar"
    ])

    with tab_summary:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Por tipo ANBIMA")
            role_summary = _summary_table(report_df, "anbima_role", "Tipo ANBIMA")
            st.dataframe(role_summary, use_container_width=True, hide_index=True)
        with col2:
            st.markdown("#### Por faixa de AuM")
            aum_summary = _aum_bucket_summary(report_df)
            st.dataframe(aum_summary, use_container_width=True, hide_index=True)

        st.markdown("#### Base filtrada")
        cols = ["id", "company_name", "anbima_role", "aum_fmt", "priority", "abordagem", "do_not_contact_reason", "status", owner_col, "cnpj", "city_uf"]
        view = report_df[[col for col in cols if col in report_df.columns]].copy()
        view = view.rename(columns={
            "id": "ID",
            "company_name": "Empresa",
            "anbima_role": "Tipo ANBIMA",
            "aum_fmt": "AuM",
            "priority": "Prioridade",
            "abordagem": "Abordagem",
            "do_not_contact_reason": "Motivo",
            "status": "Status",
            owner_col: "Responsavel",
            "cnpj": "CNPJ",
            "city_uf": "Cidade/UF",
        })
        st.dataframe(view, use_container_width=True, hide_index=True)

    with tab_pipeline:
        st.markdown("#### Funil filtrado")
        render_funnel(report_df)
        st.markdown("#### Pipeline por responsavel")
        pipeline = report_df.groupby(owner_col, dropna=False).agg(
            leads=("id", "count"),
            valor_estimado=("estimated_value", "sum"),
            probabilidade_media=("probability", "mean"),
        ).reset_index().sort_values("valor_estimado", ascending=False)
        pipeline["valor_estimado"] = pipeline["valor_estimado"].apply(money)
        pipeline["probabilidade_media"] = pipeline["probabilidade_media"].fillna(0).round(1).astype(str) + "%"
        pipeline = pipeline.rename(columns={owner_col: "Responsavel", "leads": "Leads", "valor_estimado": "Valor estimado", "probabilidade_media": "Prob. media"})
        st.dataframe(pipeline, use_container_width=True, hide_index=True)

    with tab_followups:
        followups = followups_df()
        if followups.empty:
            st.info("Nenhum follow-up registrado.")
        else:
            followups = followups[followups["id"].isin(report_df["id"])]
            period = st.radio("Periodo", ["Todos", "Atrasados", "Hoje", "Proximos 7 dias", "Proximos 30 dias"], horizontal=True)
            if period == "Atrasados":
                followups = followups[followups["dias"] < 0]
            elif period == "Hoje":
                followups = followups[followups["dias"] == 0]
            elif period == "Proximos 7 dias":
                followups = followups[(followups["dias"] >= 0) & (followups["dias"] <= 7)]
            elif period == "Proximos 30 dias":
                followups = followups[(followups["dias"] >= 0) & (followups["dias"] <= 30)]
            st.dataframe(
                followups[["id", "company_name", "anbima_role", "aum_fmt", "status", "responsavel", "next_followup_date", "dias"]],
                use_container_width=True,
                hide_index=True,
            )

    with tab_proposals:
        proposals = proposals_df()
        if proposals.empty:
            st.info("Nenhuma proposta cadastrada.")
        else:
            proposals = proposals[proposals["lead_id"].isin(report_df["id"])]
            proposal_status = st.selectbox("Status da proposta", ["Todos"] + PROPOSAL_STATUSES, key="reports_proposal_status")
            if proposal_status != "Todos":
                proposals = proposals[proposals["status"] == proposal_status]
            proposal_cols = [
                "id", "company_name", "title", "service_type", "status", "owner_name",
                "setup_fee_fmt", "recurring_fee_fmt", "estimated_total_fmt", "valid_until",
            ]
            st.dataframe(proposals[proposal_cols], use_container_width=True, hide_index=True)

    with tab_export:
        st.markdown("#### Exportar relatorio filtrado")
        export_cols = [
            "id", "company_name", "anbima_role", "aum", "aum_fmt", "priority", "status",
            "abordagem", "do_not_contact_reason", owner_col, "cnpj", "city_uf", "contact_name", "email", "phone", "next_followup_date",
            "estimated_value", "probability",
        ]
        export_df = report_df[[col for col in export_cols if col in report_df.columns]].copy()
        file_format = st.radio("Formato", ["Excel", "CSV"], horizontal=True, key="reports_export_format")
        data = export_table(export_df, file_format)
        extension = "xlsx" if file_format == "Excel" else "csv"
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if file_format == "Excel" else "text/csv"
        st.download_button(
            "Baixar relatorio filtrado",
            data=data,
            file_name=f"hoam_relatorio_leads.{extension}",
            mime=mime,
        )


def render_import_export():
    header("Importar e Exportar", "Entrada e saida de dados em CSV ou Excel para operacao comercial.")
    df = leads_df()

    st.subheader("Exportacao")
    if df.empty:
        st.info("Nenhum lead para exportar.")
    else:
        file_format = st.radio("Formato", ["CSV", "Excel"], horizontal=True)
        data = export_table(df, file_format)
        extension = "xlsx" if file_format == "Excel" else "csv"
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if file_format == "Excel" else "text/csv"
        st.download_button(
            "Baixar base de leads",
            data=data,
            file_name=f"hoam_crm_leads.{extension}",
            mime=mime,
        )

    st.divider()
    st.subheader("Importacao")
    users = users_options()
    owner_label = st.selectbox("Responsavel padrao para novos leads", list(users.keys()))
    file = st.file_uploader("Arquivo CSV ou Excel", type=["csv", "xlsx", "xls"])
    if file and st.button("Importar leads"):
        try:
            result = import_leads(file, owner_id=users[owner_label])
            st.success(f"{result['imported']} lead(s) importado(s). {result['skipped']} duplicado(s) ignorado(s).")
        except Exception as exc:
            st.error(str(exc))


def render_clients():
    header("Clientes Convertidos", "Base de leads ganhos e convertidos em clientes.")
    df = clients_df()
    if df.empty:
        st.info("Nenhum cliente convertido ate o momento.")
        return
    st.dataframe(
        df[["id", "lead_id", "company_name", "contact_name", "email", "phone", "owner_name", "valor_estimado", "converted_at", "notes"]],
        use_container_width=True,
        hide_index=True,
    )


def render_data_quality():
    header("Qualidade de Dados", "Deduplicacao, padronizacao e saneamento da base comercial.")
    summary = data_quality_summary()
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        metric_card("Leads", summary["total"], "base atual")
    with c2:
        metric_card("Grupos duplicados", summary["duplicate_groups"], "possiveis conflitos")
    with c3:
        metric_card("Registros em duplicidade", summary["duplicate_records"], "para revisar")
    with c4:
        metric_card("Sem e-mail", summary["missing_email"], "cadastro incompleto")
    with c5:
        metric_card("CNPJ invalido", summary["invalid_cnpj"], "formato a revisar")

    tab_duplicates, tab_standardize = st.tabs(["Duplicados", "Padronizacao"])

    with tab_duplicates:
        duplicates = duplicate_groups_df()
        if duplicates.empty:
            st.success("Nenhum duplicado provavel encontrado.")
        else:
            st.dataframe(
                duplicates[["group_id", "reason", "score", "id", "company_name", "cnpj", "email", "phone", "status", "priority", "owner_name"]],
                use_container_width=True,
                hide_index=True,
            )

            groups = sorted(duplicates["group_id"].unique().tolist())
            selected_group = st.selectbox("Grupo para revisar", groups)
            group = duplicates[duplicates["group_id"] == selected_group].copy()
            st.dataframe(group, use_container_width=True, hide_index=True)

            ids = group["id"].tolist()
            col1, col2 = st.columns(2)
            master_id = col1.selectbox("Manter lead principal", ids, format_func=lambda lead_id: _lead_label(group, lead_id))
            duplicate_options = [lead_id for lead_id in ids if lead_id != master_id]
            duplicate_id = col2.selectbox("Mesclar e excluir duplicado", duplicate_options, format_func=lambda lead_id: _lead_label(group, lead_id))

            st.warning("A mesclagem transfere atividades, oportunidades, propostas e cliente para o lead principal. O duplicado e excluido.")
            if st.button("Mesclar duplicado selecionado"):
                try:
                    merge_duplicate_pair(master_id, duplicate_id)
                    st.success("Leads mesclados com sucesso.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    with tab_standardize:
        st.write("Padroniza CNPJ, telefone, e-mail e Cidade/UF nos leads existentes.")
        st.caption("Nao altera status, prioridade, responsavel ou historico.")
        if st.button("Padronizar base agora"):
            changed = standardize_all_leads()
            st.success(f"{changed} lead(s) padronizado(s).")
            st.rerun()


def render_users():
    header("Usuarios e Comerciais", "Cadastro de acessos e responsaveis pelo relacionamento comercial.")
    users = get_users()
    if users:
        st.dataframe(pd.DataFrame(users), use_container_width=True, hide_index=True)

    tab_new, tab_edit = st.tabs(["Novo usuario", "Editar usuario"])
    with tab_new:
        with st.form("novo_usuario"):
            name = st.text_input("Nome *")
            email = st.text_input("E-mail *")
            role = st.selectbox("Perfil", USER_ROLES)
            password = st.text_input("Senha *", type="password")
            active = st.checkbox("Ativo", value=True)
            submit = st.form_submit_button("Cadastrar usuario")
            if submit:
                if not name.strip() or not email.strip() or not password.strip():
                    st.error("Informe nome, e-mail e senha.")
                else:
                    try:
                        add_user({"name": name.strip(), "email": email.strip(), "role": role, "password": password, "active": active})
                        st.success("Usuario cadastrado.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Nao foi possivel cadastrar: {exc}")

    with tab_edit:
        if not users:
            st.info("Nenhum usuario cadastrado.")
            return
        selected = st.selectbox("Usuario", [user["id"] for user in users], format_func=lambda user_id: f"{user_id} - {get_user(user_id)['name']}")
        user = get_user(selected)
        with st.form("editar_usuario"):
            name = st.text_input("Nome *", value=user["name"])
            email = st.text_input("E-mail *", value=user["email"])
            role = st.selectbox("Perfil", USER_ROLES, index=USER_ROLES.index(user["role"]) if user["role"] in USER_ROLES else 0)
            password = st.text_input("Nova senha", type="password")
            active = st.checkbox("Ativo", value=bool(user["active"]))
            submit = st.form_submit_button("Salvar usuario")
            if submit:
                try:
                    update_user(selected, {"name": name.strip(), "email": email.strip(), "role": role, "password": password, "active": active})
                    st.success("Usuario atualizado.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Nao foi possivel atualizar: {exc}")


def _save_new_lead(company_name, contact_name, email, phone, source, status, owner_id, priority, cnpj, city_uf, estimated_value, probability, expected_close_date, next_followup_date, do_not_contact, do_not_contact_reason, notes):
    owner = get_user(owner_id)["name"] if owner_id else ""
    lead_id = add_lead({
        "company_name": company_name.strip(),
        "contact_name": contact_name.strip(),
        "email": email.strip(),
        "phone": phone.strip(),
        "source": source,
        "status": status,
        "category": priority_for_status(status),
        "priority": priority_for_status(status),
        "cnpj": cnpj.strip(),
        "city_uf": city_uf.strip(),
        "owner": owner,
        "owner_id": owner_id,
        "do_not_contact": do_not_contact,
        "do_not_contact_reason": do_not_contact_reason.strip() if do_not_contact else "",
        "estimated_value": estimated_value,
        "probability": probability,
        "expected_close_date": str(expected_close_date) if expected_close_date else None,
        "next_followup_date": str(next_followup_date) if next_followup_date else None,
        "notes": notes.strip(),
    })
    return lead_id


def _render_do_not_contact_quick_toggle(lead, current_user):
    current_value = bool(lead.get("do_not_contact"))
    st.markdown('<div class="hoam-card compact-action">', unsafe_allow_html=True)
    col1, col2 = st.columns([1, 2])
    new_value = col1.checkbox(
        "Nao abordar este lead",
        value=current_value,
        key=f"quick_do_not_contact_{lead['id']}",
    )
    reason = col2.text_input(
        "Motivo",
        value=lead.get("do_not_contact_reason") or "",
        disabled=not new_value,
        key=f"quick_do_not_contact_reason_{lead['id']}",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    reason = reason.strip() if new_value else ""
    current_reason = lead.get("do_not_contact_reason") or ""
    if new_value != current_value or reason != current_reason:
        payload = dict(lead)
        payload["do_not_contact"] = new_value
        payload["do_not_contact_reason"] = reason
        update_lead(int(lead["id"]), payload)
        add_activity({
            "lead_id": int(lead["id"]),
            "user_id": current_user["id"],
            "activity_type": "Outro",
            "activity_date": str(date.today()),
            "subject": "Flag de abordagem atualizado",
            "notes": "Lead marcado como nao abordar." if new_value else "Lead liberado para abordagem.",
        })
        st.success("Flag de abordagem atualizado.")
        st.rerun()


def _render_edit_lead_form(lead, current_user):
    users = users_options()
    owner_index = _index_for_owner(users, lead.get("owner_id"))
    with st.form("editar_lead"):
        c1, c2 = st.columns(2)
        company_name = c1.text_input("Empresa *", value=lead.get("company_name") or "")
        contact_name = c2.text_input("Contato", value=lead.get("contact_name") or "")
        email = c1.text_input("E-mail", value=lead.get("email") or "")
        phone = c2.text_input("Telefone", value=lead.get("phone") or "")
        source = c1.selectbox("Origem", LEAD_SOURCES, index=_index_or_zero(LEAD_SOURCES, lead.get("source")))
        status = c2.selectbox("Status", LEAD_STATUSES, index=_index_or_zero(LEAD_STATUSES, lead.get("status")))
        priority = priority_for_status(status)
        c1.info(f"Prioridade HOAM automatica: {priority}")
        cnpj = c1.text_input("CNPJ", value=lead.get("cnpj") or "")
        city_uf = c2.text_input("Cidade/UF", value=lead.get("city_uf") or "")
        owner_label = c1.selectbox("Responsavel", list(users.keys()), index=owner_index)
        estimated_value = c2.number_input("Valor estimado", min_value=0.0, value=float(lead.get("estimated_value") or 0), step=1000.0)
        probability = c1.slider("Probabilidade (%)", 0, 100, int(lead.get("probability") or 0), 5)
        use_close_date = c2.checkbox("Manter/informar data estimada de fechamento", value=bool(lead.get("expected_close_date")))
        expected_close_date = c2.date_input("Data estimada de fechamento", value=parse_date(lead.get("expected_close_date")), disabled=not use_close_date)
        use_followup = c1.checkbox("Manter/informar proximo follow-up", value=bool(lead.get("next_followup_date")))
        next_followup_date = c1.date_input("Proximo follow-up", value=parse_date(lead.get("next_followup_date"), date.today() + timedelta(days=7)), disabled=not use_followup)
        do_not_contact = c1.checkbox("Nao abordar este lead", value=bool(lead.get("do_not_contact")))
        do_not_contact_reason = c2.text_input("Motivo para nao abordar", value=lead.get("do_not_contact_reason") or "", disabled=not do_not_contact)
        notes = st.text_area("Observacoes", value=lead.get("notes") or "")
        submit = st.form_submit_button("Salvar alteracoes")

        if submit:
            owner_id = users[owner_label]
            owner = get_user(owner_id)["name"] if owner_id else ""
            old_status = lead.get("status")
            update_lead(int(lead["id"]), {
                "company_name": company_name.strip(),
                "contact_name": contact_name.strip(),
                "email": email.strip(),
                "phone": phone.strip(),
                "source": source,
                "status": status,
                "category": priority_for_status(status),
                "priority": priority_for_status(status),
                "cnpj": cnpj.strip(),
                "city_uf": city_uf.strip(),
                "owner": owner,
                "owner_id": owner_id,
                "do_not_contact": do_not_contact,
                "do_not_contact_reason": do_not_contact_reason.strip() if do_not_contact else "",
                "estimated_value": estimated_value,
                "probability": probability,
                "expected_close_date": str(expected_close_date) if use_close_date else None,
                "next_followup_date": str(next_followup_date) if use_followup else None,
                "notes": notes.strip(),
            })
            add_activity({
                "lead_id": int(lead["id"]),
                "user_id": current_user["id"],
                "activity_type": "Mudanca de status" if status != old_status else "Outro",
                "activity_date": str(date.today()),
                "subject": "Lead atualizado",
                "notes": f"Status anterior: {old_status}. Status atual: {status}.",
            })
            if status == "Ganho":
                upsert_client_from_lead(int(lead["id"]))
            st.success("Lead atualizado.")
            st.rerun()

    if can_delete_leads(current_user):
        if st.button("Excluir lead"):
            delete_lead(int(lead["id"]))
            st.warning("Lead excluido.")
            st.rerun()


def _render_lead_history(lead_id):
    activities = activity_history_df(lead_id)
    opportunities = opportunities_df(lead_id)
    proposals = proposals_df(lead_id)
    if activities.empty and opportunities.empty and proposals.empty:
        st.info("Nenhum historico registrado para este lead.")
        return
    if not activities.empty:
        st.subheader("Atividades")
        st.dataframe(activities, use_container_width=True, hide_index=True)
    if not opportunities.empty:
        st.subheader("Oportunidades")
        st.dataframe(opportunities, use_container_width=True, hide_index=True)
    if not proposals.empty:
        st.subheader("Propostas")
        st.dataframe(proposals, use_container_width=True, hide_index=True)


def _render_lead_overview(lead):
    lead_id = int(lead["id"])
    proposals = proposals_df(lead_id)
    activities = activity_history_df(lead_id)
    opportunities = opportunities_df(lead_id)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", lead.get("status") or "-")
    c2.metric("Prioridade", lead.get("priority") or "-")
    c3.metric("CNPJ", lead.get("cnpj") or "-")
    c4.metric("Propostas", 0 if proposals.empty else len(proposals))

    st.markdown("#### Dados comerciais")
    info = {
        "Empresa": lead.get("company_name"),
        "Tipo ANBIMA": lead.get("anbima_role"),
        "AuM": money(float(lead.get("aum") or 0) * 1_000_000),
        "Abordagem": "Nao abordar" if lead.get("do_not_contact") else "Liberado",
        "Motivo": lead.get("do_not_contact_reason"),
        "CNPJ": lead.get("cnpj"),
        "Cidade/UF": lead.get("city_uf"),
        "Contato": lead.get("contact_name"),
        "E-mail": lead.get("email"),
        "Telefone": lead.get("phone"),
        "Responsavel": lead.get("owner_name") or lead.get("owner"),
        "Proximo follow-up": lead.get("next_followup_date"),
    }
    st.dataframe(pd.DataFrame([info]), use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Ultimas atividades")
        if activities.empty:
            st.caption("Sem atividades registradas.")
        else:
            st.dataframe(activities.head(5), use_container_width=True, hide_index=True)
    with col2:
        st.markdown("#### Oportunidades")
        if opportunities.empty:
            st.caption("Sem oportunidades registradas.")
        else:
            st.dataframe(opportunities.head(5), use_container_width=True, hide_index=True)

    st.markdown("#### Propostas")
    if proposals.empty:
        st.caption("Sem propostas registradas.")
    else:
        st.dataframe(
            proposals[["id", "title", "service_type", "status", "estimated_total_fmt", "valid_until", "owner_name"]],
            use_container_width=True,
            hide_index=True,
        )


def _render_lead_proposals(lead_id, current_user):
    lead = get_lead(lead_id)
    if not lead:
        st.error("Lead nao encontrado.")
        return
    _render_proposal_form([lead], current_user, fixed_lead_id=lead_id)
    df = proposals_df(lead_id)
    if df.empty:
        st.info("Nenhuma proposta vinculada a este lead.")
    else:
        st.dataframe(
            df[["id", "title", "service_type", "status", "setup_fee_fmt", "recurring_fee_fmt", "estimated_total_fmt", "valid_until"]],
            use_container_width=True,
            hide_index=True,
        )


def _render_proposal_form(leads, current_user, fixed_lead_id=None):
    options = {f"{lead['id']} - {lead['company_name']}": lead["id"] for lead in leads}
    default_label = next((label for label, lead_id in options.items() if lead_id == fixed_lead_id), None)
    with st.form(f"nova_proposta_{fixed_lead_id or 'geral'}"):
        selected = st.selectbox(
            "Lead",
            list(options.keys()),
            index=list(options.keys()).index(default_label) if default_label else 0,
            disabled=bool(fixed_lead_id),
        )
        c1, c2 = st.columns(2)
        title = c1.text_input("Titulo *")
        service_type = c2.selectbox("Tipo de servico", PROPOSAL_SERVICE_TYPES)
        status = c1.selectbox("Status", PROPOSAL_STATUSES)
        valid_until = c2.date_input("Validade", value=date.today() + timedelta(days=15))
        setup_fee = c1.number_input("Fee setup", min_value=0.0, step=1000.0)
        recurring_fee = c2.number_input("Fee recorrente mensal", min_value=0.0, step=1000.0)
        estimated_total = c1.number_input("Valor total estimado", min_value=0.0, step=1000.0)
        notes = st.text_area("Observacoes")
        submit = st.form_submit_button("Cadastrar proposta")
        if submit:
            if not title.strip():
                st.error("Informe o titulo da proposta.")
                return
            lead_id = fixed_lead_id or options[selected]
            proposal_id = add_proposal({
                "lead_id": lead_id,
                "owner_id": current_user["id"],
                "title": title.strip(),
                "service_type": service_type,
                "status": status,
                "setup_fee": setup_fee,
                "recurring_fee": recurring_fee,
                "estimated_total": estimated_total,
                "valid_until": str(valid_until),
                "sent_at": str(date.today()) if status in ["Enviada", "Em negociacao", "Aprovada"] else None,
                "approved_at": str(date.today()) if status == "Aprovada" else None,
                "notes": notes.strip(),
            })
            _sync_lead_after_proposal(lead_id, status, current_user["id"], proposal_id)
            st.success("Proposta cadastrada.")
            st.rerun()


def _render_proposal_edit_form(proposal, leads, current_user):
    options = {f"{lead['id']} - {lead['company_name']}": lead["id"] for lead in leads}
    current_label = next((label for label, lead_id in options.items() if lead_id == proposal.get("lead_id")), list(options.keys())[0])
    with st.form(f"editar_proposta_{proposal['id']}"):
        selected = st.selectbox("Lead", list(options.keys()), index=list(options.keys()).index(current_label))
        c1, c2 = st.columns(2)
        title = c1.text_input("Titulo *", value=proposal.get("title") or "")
        service_type = c2.selectbox("Tipo de servico", PROPOSAL_SERVICE_TYPES, index=_index_or_zero(PROPOSAL_SERVICE_TYPES, proposal.get("service_type")))
        status = c1.selectbox("Status", PROPOSAL_STATUSES, index=_index_or_zero(PROPOSAL_STATUSES, proposal.get("status")))
        valid_until = c2.date_input("Validade", value=parse_date(proposal.get("valid_until"), date.today() + timedelta(days=15)))
        setup_fee = c1.number_input("Fee setup", min_value=0.0, value=float(proposal.get("setup_fee") or 0), step=1000.0)
        recurring_fee = c2.number_input("Fee recorrente mensal", min_value=0.0, value=float(proposal.get("recurring_fee") or 0), step=1000.0)
        estimated_total = c1.number_input("Valor total estimado", min_value=0.0, value=float(proposal.get("estimated_total") or 0), step=1000.0)
        notes = st.text_area("Observacoes", value=proposal.get("notes") or "")
        submit = st.form_submit_button("Salvar proposta")
        if submit:
            lead_id = options[selected]
            update_proposal(int(proposal["id"]), {
                "lead_id": lead_id,
                "owner_id": proposal.get("owner_id") or current_user["id"],
                "title": title.strip(),
                "service_type": service_type,
                "status": status,
                "setup_fee": setup_fee,
                "recurring_fee": recurring_fee,
                "estimated_total": estimated_total,
                "valid_until": str(valid_until),
                "sent_at": proposal.get("sent_at") or (str(date.today()) if status in ["Enviada", "Em negociacao", "Aprovada"] else None),
                "approved_at": proposal.get("approved_at") or (str(date.today()) if status == "Aprovada" else None),
                "notes": notes.strip(),
            })
            _sync_lead_after_proposal(lead_id, status, current_user["id"], int(proposal["id"]))
            st.success("Proposta atualizada.")
            st.rerun()


def _sync_lead_after_proposal(lead_id, proposal_status, user_id, proposal_id):
    status_map = {
        "Enviada": "Proposta enviada",
        "Em negociacao": "Negociacao",
        "Aprovada": "Ganho",
        "Recusada": "Perdido",
    }
    new_status = status_map.get(proposal_status)
    if new_status:
        lead = get_lead(lead_id)
        if lead:
            payload = dict(lead)
            payload["status"] = new_status
            payload["priority"] = priority_for_status(new_status)
            payload["category"] = payload["priority"]
            update_lead(lead_id, payload)
            if new_status == "Ganho":
                upsert_client_from_lead(lead_id)
    add_activity({
        "lead_id": lead_id,
        "user_id": user_id,
        "activity_type": "Envio de proposta" if proposal_status in ["Enviada", "Em negociacao"] else "Outro",
        "activity_date": str(date.today()),
        "subject": f"Proposta #{proposal_id}: {proposal_status}",
        "notes": "Movimentacao registrada pelo modulo de propostas.",
    })


def _render_aum_filters(df, key_prefix="leads"):
    if "aum" not in df.columns:
        return "Todas", 0.0, 0.0

    st.markdown("##### Filtros financeiros")
    c1, c2, c3 = st.columns([2, 1, 1])
    aum_range = c1.selectbox(
        "Faixa de AuM",
        [
            "Todas",
            "Sem AuM",
            "0 a 500 mi",
            "500 mi a 1 bi",
            "1 a 2 bi",
            "2 a 5 bi",
            "5 a 10 bi",
            "10 a 25 bi",
            "25 a 50 bi",
            "Acima de 50 bi",
            "Personalizada",
        ],
        key=f"{key_prefix}_aum_range",
    )
    custom_aum_min = 0.0
    custom_aum_max = 0.0
    if aum_range == "Personalizada":
        max_aum_bi = max(float(df["aum"].max() or 0) / 1000, 1.0)
        custom_aum_min = c2.number_input("AuM minimo (R$ bi)", min_value=0.0, max_value=max_aum_bi, value=0.0, step=0.5, key=f"{key_prefix}_aum_min")
        custom_aum_max = c3.number_input("AuM maximo (R$ bi)", min_value=0.0, max_value=max_aum_bi, value=min(5.0, max_aum_bi), step=0.5, key=f"{key_prefix}_aum_max")
    else:
        c2.empty()
        c3.empty()
    return aum_range, custom_aum_min, custom_aum_max


def _summary_table(df, column, label):
    data = df.copy()
    data[column] = data[column].fillna("Sem ANBIMA").replace("", "Sem ANBIMA")
    summary = data.groupby(column, dropna=False).agg(
        leads=("id", "count"),
        aum=("aum", "sum"),
        pipeline=("estimated_value", "sum"),
    ).reset_index().sort_values("leads", ascending=False)
    summary["aum"] = summary["aum"].apply(lambda value: money(float(value) * 1_000_000))
    summary["pipeline"] = summary["pipeline"].apply(money)
    return summary.rename(columns={column: label, "leads": "Leads", "aum": "AuM", "pipeline": "Pipeline"})


def _aum_bucket_summary(df):
    data = df.copy()
    aum_bi = pd.to_numeric(data["aum"], errors="coerce").fillna(0) / 1000
    data["Faixa de AuM"] = pd.cut(
        aum_bi,
        bins=[-0.01, 0, 0.5, 1, 2, 5, 10, 25, 50, float("inf")],
        labels=[
            "Sem AuM",
            "0 a 500 mi",
            "500 mi a 1 bi",
            "1 a 2 bi",
            "2 a 5 bi",
            "5 a 10 bi",
            "10 a 25 bi",
            "25 a 50 bi",
            "Acima de 50 bi",
        ],
    )
    summary = data.groupby("Faixa de AuM", observed=False).agg(
        leads=("id", "count"),
        aum=("aum", "sum"),
        pipeline=("estimated_value", "sum"),
    ).reset_index()
    summary["aum"] = summary["aum"].apply(lambda value: money(float(value) * 1_000_000))
    summary["pipeline"] = summary["pipeline"].apply(money)
    return summary.rename(columns={"leads": "Leads", "aum": "AuM", "pipeline": "Pipeline"})


def _filter_leads(df, status_filter, priority_filter, role_filter, owner_filter, search, aum_range="Todas", custom_aum_min=0.0, custom_aum_max=0.0, approach_filter="Todos"):
    filtered = df.copy()
    if status_filter != "Todos":
        filtered = filtered[filtered["status"] == status_filter]
    if priority_filter != "Todas":
        filtered = filtered[filtered["priority"] == priority_filter]
    if role_filter != "Todos" and "anbima_role" in filtered.columns:
        filtered = filtered[filtered["anbima_role"] == role_filter]
    if approach_filter != "Todos" and "do_not_contact" in filtered.columns:
        blocked = approach_filter == "Nao abordar"
        filtered = filtered[filtered["do_not_contact"].fillna(0).astype(int).eq(1 if blocked else 0)]
    if aum_range != "Todas" and "aum" in filtered.columns:
        aum_bi = pd.to_numeric(filtered["aum"], errors="coerce").fillna(0) / 1000
        if aum_range == "Sem AuM":
            filtered = filtered[aum_bi <= 0]
        elif aum_range == "0 a 500 mi":
            filtered = filtered[(aum_bi > 0) & (aum_bi <= 0.5)]
        elif aum_range == "500 mi a 1 bi":
            filtered = filtered[(aum_bi > 0.5) & (aum_bi <= 1)]
        elif aum_range == "1 a 2 bi":
            filtered = filtered[(aum_bi > 1) & (aum_bi <= 2)]
        elif aum_range == "2 a 5 bi":
            filtered = filtered[(aum_bi > 2) & (aum_bi <= 5)]
        elif aum_range == "5 a 10 bi":
            filtered = filtered[(aum_bi > 5) & (aum_bi <= 10)]
        elif aum_range == "10 a 25 bi":
            filtered = filtered[(aum_bi > 10) & (aum_bi <= 25)]
        elif aum_range == "25 a 50 bi":
            filtered = filtered[(aum_bi > 25) & (aum_bi <= 50)]
        elif aum_range == "Acima de 50 bi":
            filtered = filtered[aum_bi > 50]
        elif aum_range == "Personalizada":
            low = min(custom_aum_min, custom_aum_max)
            high = max(custom_aum_min, custom_aum_max)
            filtered = filtered[(aum_bi >= low) & (aum_bi <= high)]
    if owner_filter:
        owner_col = "responsavel" if "responsavel" in filtered.columns else "owner"
        filtered = filtered[filtered[owner_col].fillna("").str.contains(owner_filter, case=False, na=False)]
    if search:
        filtered = filtered[
            filtered["company_name"].fillna("").str.contains(search, case=False, na=False)
            | filtered["contact_name"].fillna("").str.contains(search, case=False, na=False)
            | filtered["cnpj"].fillna("").str.contains(search, case=False, na=False)
        ]
    return filtered


def _lead_label(group, lead_id):
    row = group[group["id"] == lead_id].iloc[0]
    return f"{lead_id} - {row['company_name']}"


def _default_owner_index(options, current_user):
    labels = list(options.keys())
    for idx, label in enumerate(labels):
        if options[label] == current_user.get("id"):
            return idx
    return 0


def _index_for_owner(options, owner_id):
    labels = list(options.keys())
    for idx, label in enumerate(labels):
        if options[label] == owner_id:
            return idx
    return 0


def _index_or_zero(options, value):
    return options.index(value) if value in options else 0



def _parse_release_intent(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    lowered = raw.lower()
    if any(token in lowered for token in (" post now", " publish now", "post this now", " right now", " immediately")) or lowered in {"now", "yes now", "post now"}:
        return {"mode": "post_now"}
    time_match = TIME_WINDOW_RE.search(raw)
    if not time_match:
        return {"mode": ""}
    try:
        time_label = datetime.combine(datetime.now().date(), parse_time_string(time_match.group(0))).strftime("%I:%M %p")
    except Exception:
        return {"mode": ""}
    date_phrase = ""
    for pattern in DATE_PATTERNS:
        match = pattern.search(raw)
        if match:
            date_phrase = match.group(0)
            break
    if not date_phrase:
        return {"mode": ""}
    resolved = resolve_date_phrase(date_phrase)
    if not resolved:
        return {"mode": ""}
    return {"mode": "schedule", "scheduled_date": resolved.isoformat(), "days": [resolved.strftime("%A")], "time": time_label}


def _encode_oauth_state(client_id: str, operator_phone: str) -> str:
    payload = json.dumps(
        {"client_id": str(client_id or "").strip(), "operator_phone": normalize_phone(operator_phone), "nonce": uuid.uuid4().hex, "issued_at": _utc_now_iso()},
        ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def build_meta_connect_link(client_id: str, operator_phone: str) -> str:
    public_base = str(os.getenv("META_OAUTH_PUBLIC_BASE_URL") or os.getenv("WEBHOOK_PROXY_URL") or "").strip().rstrip("/")
    if not public_base:
        return ""
    state = _encode_oauth_state(client_id, operator_phone)
    return f"{public_base}/api/meta-oauth/start?client_id={client_id}&phone={normalize_phone(operator_phone)}&state={state}"


async def _complete_onboarding(phone: str, answers: dict[str, Any]) -> None:
    from webhook_server import ProfileSaveRequest, QuickIntakeRequest, SynthesizeRequest, api_save_client_profile, api_synthesize_client
    business_name = str(answers.get("business_name") or "").strip()
    if not business_name or business_name.startswith("/"):
        _clear_session(phone)
        send_text_message(phone, "*Client intake could not be completed* \u26a0\ufe0f\nThe business name was invalid.\n\nStart Add Client again and begin with the real business name.")
        return
    client_id = _unique_client_id(business_name)
    quick_intake = QuickIntakeRequest(
        brand_name=business_name,
        business_type=str(answers.get("business_type") or "").strip(),
        main_language=str(answers.get("main_language") or "").strip().lower(),
        what_they_sell=str(answers.get("what_they_sell") or "").strip(),
        target_audience=str(answers.get("target_audience") or "").strip(),
        brand_tone=str(answers.get("brand_tone") or "").strip(),
        products_examples=str(answers.get("products_examples") or "").strip(),
        city_market=str(answers.get("city_market") or "").strip(),
        words_to_avoid=str(answers.get("words_to_avoid") or "").strip(),
        inspiration_links=str(answers.get("inspiration_links") or "").strip(),
    )
    send_text_message(phone, f"Final step complete for {_format_client_label(client_id, business_name)}.\nJarvis is building the brand profile now. I'll confirm here automatically when it's ready.")
    synthesis = _coerce_api_result(await api_synthesize_client(SynthesizeRequest(client_name=business_name, raw_context="", quick_intake=quick_intake, website_url=None, social_url=None)))
    if str(synthesis.get("status") or "").strip().lower() not in {"success", "missing"}:
        _clear_session(phone)
        reason = str(synthesis.get("reason") or synthesis.get("detail") or "Synthesis failed.").strip()
        send_text_message(phone, f"*Client build paused* \u26a0\ufe0f\nI could not finish the brand profile for {_format_client_label(client_id, business_name)} yet.\nReason: {reason}")
        return
    profile_json = dict(synthesis.get("data") or {})
    profile_json.setdefault("main_language", str(answers.get("main_language") or "").strip().lower())
    profile_json.setdefault("city_market", str(answers.get("city_market") or "").strip())
    save_result = _coerce_api_result(await api_save_client_profile(ProfileSaveRequest(client_id=client_id, phone_number=None, meta_access_token="", facebook_page_id="", instagram_account_id="", profile_json=profile_json)))
    if str(save_result.get("status") or "").strip().lower() != "success":
        _clear_session(phone)
        missing = list(save_result.get("missing_fields") or [])
        if missing:
            send_text_message(phone, f"*Client save failed* \u26a0\ufe0f\nI could not save {_format_client_label(client_id, business_name)} yet.\nReason: " + "\n".join(f"- {item}" for item in missing[:6]))
            return
        reason = str(save_result.get("reason") or save_result.get("detail") or "Save failed.").strip()
        send_text_message(phone, f"*Client save failed* \u26a0\ufe0f\nI could not save {_format_client_label(client_id, business_name)} yet.\nReason: {reason}")
        return
    _clear_session(phone)
    _audit(phone, "operator.add_client.completed", {"client_id": client_id, "business_name": business_name})
    send_button_message(
        phone, header_text="Client Ready",
        body_text=f"*{_format_client_label(client_id, business_name)} is live* \U0001f3e2\nBrand profile saved. Trend research is running in the background.\n\nChoose the next step.",
        buttons=[{"id": f"OP_CONNECT_NOW:{client_id}", "title": "Connect Meta"}, {"id": "OP_MENU:POST", "title": "New Post"}, {"id": "OP_MENU:MORE", "title": "Open Menu"}],
        footer_text=f"Client ID: {client_id}",
    )


async def _handle_synthesized_candidate(phone: str, result: dict[str, Any], provisional_name: str = "", source_mode: str = "") -> None:
    from webhook_server import persist_client_profile
    if str(result.get("status") or "").strip().lower() == "error":
        reason = str(result.get("reason") or result.get("detail") or "").strip()
        _clear_session(phone)
        send_text_message(phone, f"*Client build paused* \u26a0\ufe0f\nI could not finish the brand profile for {provisional_name or 'this client'} yet.\nReason: {reason}")
        return
    status = str(result.get("status") or "").strip().lower()
    if status == "missing":
        missing_fields = list(result.get("missing_fields") or [])
        candidate = dict(result.get("client") or result.get("profile") or {})
        business_name = str(candidate.get("business_name") or provisional_name or "").strip()
        display_name = _format_client_label("", business_name) or provisional_name
        session = {"mode": "onboarding_missing_fields", "provisional_client_name": display_name, "candidate_profile": candidate, "missing_fields": missing_fields, "source_mode": source_mode, "updated_at": _utc_now_iso()}
        _save_session(phone, session)
        send_text_message(phone, _build_missing_fields_template(display_name, missing_fields))
        return
    if status == "success":
        client_data = dict(result.get("client") or {})
        client_id = str(client_data.get("client_id") or "").strip()
        business_name = str((client_data.get("profile_json") or {}).get("business_name") or provisional_name or "").strip()
        _clear_session(phone)
        _audit(phone, "operator.add_client.completed", {"client_id": client_id, "source_mode": source_mode})
        send_button_message(
            phone, header_text="Client Ready",
            body_text=f"*{_format_client_label(client_id, business_name)} is live* \U0001f3e2\nBrand profile saved. Trend research is running in the background.\n\nChoose the next step.",
            buttons=[{"id": f"OP_CONNECT_NOW:{client_id}", "title": "Connect Meta"}, {"id": "OP_MENU:POST", "title": "New Post"}, {"id": "OP_MENU:MORE", "title": "Open Menu"}],
            footer_text=f"Client ID: {client_id}",
        )
        return
    _clear_session(phone)
    reason = str(result.get("reason") or result.get("detail") or "Synthesis failed.").strip()
    send_text_message(phone, f"*Client build paused* \u26a0\ufe0f\nI could not finish the brand profile for {provisional_name or 'this client'} yet.\nReason: {reason}")


async def _send_client_picker(phone: str, *, reason: str, session_payload: dict[str, Any]) -> None:
    sections = _build_client_picker_sections()
    if not sections:
        send_text_message(phone, "*No clients yet* \u2726\nAdd the first client before using this workflow.")
        return
    payload = dict(session_payload)
    payload["mode"] = "client_pick"
    payload["selection_reason"] = reason
    _save_session(phone, payload)
    body_map = {
        "post_client": "*Pick a client* \u2726\nChoose the client for this post. If the list does not load, reply with the client name.",
        "media": "*Pick a client* \u2726\nChoose the client for these assets. I have the files and I am ready to build once you pick.",
        "connect": "*Pick a client* \u2726\nJarvis will generate the Meta connect handoff after you select the client.",
        "strategy_client": "*Pick a client* \u2726\nJarvis will open the planning prompt right after the client is selected.",
    }
    body_text = body_map.get(reason, "*Choose a client* \u2726\nReply with the client name if the list does not load.")
    back_target = payload.get("back_target") or ""
    _send_list_card(
        phone, header_text="Jarvis", body_text=body_text, button_text="Choose client",
        sections=sections, footer_text="Reply with the client name if needed",
    )
    if back_target:
        _send_back_button(phone, "Need a different client before uploading the media bundle?", back_target)


def _prompt_for_media(phone: str, client_id: str, source_text: str = "") -> None:
    payload = {"mode": "awaiting_media", "client_id": client_id, "source_text": str(source_text or "").strip(), "updated_at": _utc_now_iso()}
    _save_session(phone, payload)
    send_text_message(
        phone,
        f"*New post for {_format_client_label(client_id)}* \u2726\n"
        "Send the image or video as *WhatsApp Document* so Jarvis receives the original quality.\n"
        "You can add notes in the document caption or send them here before the upload.\n"
        "Jarvis will hold incoming documents for up to 10 seconds to build one bundle.",
    )


async def _start_post_flow(phone: str) -> None:
    rows = _client_rows()
    if not rows:
        send_text_message(phone, "*No clients yet* \u2726\nAdd the first client before starting a post.")
        return
    if len(rows) == 1:
        row = rows[0]
        health = row.get("meta_health") or {}
        if not health.get("ok", True) and str(health.get("status") or "").strip().lower() in ("expired_or_invalid", "missing"):
            detail = str(health.get("detail") or "Meta credentials are not ready for this client.").strip()
            _save_session(phone, {"mode": "meta_blocked", "client_id": row["client_id"], "updated_at": _utc_now_iso()})
            label = _format_client_label(row["client_id"], (row.get("profile") or {}).get("business_name"))
            send_button_message(
                phone, header_text="Meta Needs Attention",
                body_text=f"*{label} cannot start a post yet* \u26a0\ufe0f\nJarvis stopped here to avoid wasting time on uploads before publish is possible.\n\nReason: {detail}",
                buttons=[{"id": f"OP_CONNECT_NOW:{row['client_id']}", "title": "Connect Meta"}, {"id": "OP_NAV:ROOT", "title": "Go Back"}],
                footer_text="Reconnect Meta, then try again",
            )
            return
        _prompt_for_media(phone, row["client_id"])
        return
    await _send_client_picker(phone, reason="post_client", session_payload={"mode": "client_pick"})


async def _start_strategy_flow(phone: str) -> None:
    rows = _client_rows()
    if not rows:
        send_text_message(phone, "*No clients yet* \u2726\nAdd the first client before opening strategy.")
        return
    if len(rows) == 1:
        _send_strategy_menu(phone, rows[0]["client_id"])
        return
    await _send_client_picker(phone, reason="strategy_client", session_payload={"mode": "client_pick"})


async def _start_connect_flow(phone: str) -> None:
    rows = _client_rows()
    if not rows:
        send_text_message(phone, "*No clients yet* \u2726\nAdd the first client before starting Meta connect.")
        return
    if len(rows) == 1:
        await _send_connect_link(phone, rows[0]["client_id"])
        return
    await _send_client_picker(phone, reason="connect", session_payload={"mode": "client_pick"})


async def _materialize_media_bundle(phone: str, session: dict[str, Any], client_id: str) -> None:
    media_refs = list(session.get("media_refs") or [])
    bundle_type, error = _infer_media_bundle(media_refs)
    if error:
        _clear_session(phone)
        send_text_message(phone, f"*Media bundle blocked* \u26a0\ufe0f\n{error}")
        return
    uploaded_items = []
    for index, ref in enumerate(media_refs, start=1):
        media_result = await asyncio.to_thread(fetch_media_bytes, ref.get("media_id"))
        if not media_result.get("success"):
            send_text_message(phone, f"*Document download failed* \u26a0\ufe0f\nJarvis could not download one of the WhatsApp documents.\nReason: {media_result.get('error')}")
            return
        filename = _safe_asset_filename(client_id, ref.get("filename"), index, ref.get("mime_type") or media_result.get("mime_type"))
        asset = await asyncio.to_thread(save_uploaded_asset, client_id, filename, media_result.get("content") or b"")
        uploaded_items.append({"filename": asset.get("filename") or filename, "kind": ref.get("kind") or "image"})
    draft_label = {"video": "WhatsApp Reel", "image_carousel": "WhatsApp Carousel", "image_single": "WhatsApp Image Post"}.get(bundle_type, "WhatsApp Draft")
    bundle_name = f"{draft_label} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    topic = _derive_topic(session.get("source_text") or "", client_id, bundle_type, len(uploaded_items))
    media_type = "carousel_post" if bundle_type == "image_carousel" else ("reel_post" if bundle_type == "video" else "image_post")
    progress_callback = _build_caption_progress_callback(phone, client_id)
    caption_payload = await asyncio.to_thread(generate_caption_payload, client_id, topic, media_type, _recent_client_captions(client_id))
    if str(caption_payload.get("status") or "").strip().lower() != "success":
        gen_state = "generation_unavailable"
        reason = str(caption_payload.get("reason") or caption_payload.get("message") or caption_payload.get("caption") or "Unknown error.").strip()
        send_text_message(phone, f"*Preview could not be prepared* \u26a0\ufe0f\nJarvis could not generate the caption yet.\nReason: {reason}")
    else:
        gen_state = "success"
    draft_payload = {
        "bundle_type": bundle_type, "items": uploaded_items, "caption_mode": "ai",
        "caption_status": "ready" if gen_state == "success" else "blocked_generation",
        "caption_text": str(caption_payload.get("caption") or "").strip(),
        "hashtags": list(caption_payload.get("hashtags") or []),
        "seo_keyword_used": str(caption_payload.get("seo_keyword_used") or "").strip(),
        "display_direction": str(caption_payload.get("display_direction") or "").strip(),
        "analysis_summary": str((caption_payload.get("media_analysis") or {}).get("analysis_summary") or "").strip(),
        "ranking_summary": dict(caption_payload.get("ranking_summary") or {}),
        "hidden_variants": list(caption_payload.get("hidden_variants") or []),
        "retry_memory": dict(caption_payload.get("retry_memory") or {}),
        "topic_hint": topic,
    }
    saved_draft = await asyncio.to_thread(save_draft_payload, client_id, bundle_name, draft_payload)
    preview_session = {
        "mode": "preview", "client_id": client_id, "bundle_name": bundle_name,
        "draft_id": saved_draft.get("draft_id"), "topic": topic,
        "content_goal": topic, "media_kind": bundle_type, "item_count": len(uploaded_items),
        "display_direction": str(caption_payload.get("display_direction") or topic).strip(),
        "operator_brief": str(session.get("source_text") or "").strip(),
        "caption_payload": caption_payload, "generation_state": gen_state,
        "requested_intent": _parse_release_intent(session.get("source_text") or ""),
        "source_text": session.get("source_text") or "",
    }
    _save_session(phone, preview_session)
    _audit(phone, "operator.preview.ready", {"client_id": client_id, "bundle_name": bundle_name, "media_kind": bundle_type})
    _send_preview_card(phone, preview_session)


async def _finalize_media_collection(phone: str, collection_token: str) -> None:
    await asyncio.sleep(10)
    session = _session_payload(phone)
    if str(session.get("mode") or "") != "media_collect":
        return
    if str(session.get("collection_token") or "") != str(collection_token or ""):
        return
    client_id = str(session.get("client_id") or "").strip()
    if client_id:
        await _materialize_media_bundle(phone, session, client_id)
        return
    rows = _client_rows()
    if len(rows) == 1:
        await _materialize_media_bundle(phone, session, rows[0]["client_id"])
        return
    await _send_client_picker(phone, reason="media", session_payload=session)


async def _handle_onboarding_step(phone: str, text: str, session: dict[str, Any]) -> None:
    index = int(session.get("step_index") or 0)
    key, _prompt = ONBOARDING_STEPS[index]
    answer = _normalize_text(text)
    if answer.startswith("/") and answer.lower() not in {"/cancel", "cancel"}:
        send_text_message(phone, "Jarvis is still in client intake mode. Reply with the requested answer, or type cancel to stop this intake.")
        return
    if answer.lower() == "skip":
        answer = ""
    answers = dict(session.get("answers") or {})
    answers[key] = answer
    next_index = index + 1
    if next_index >= len(ONBOARDING_STEPS):
        build_session = {"mode": "onboarding_build", "step_index": index, "answers": answers, "building_client_name": str(answers.get("business_name") or "").strip(), "updated_at": _utc_now_iso()}
        _save_session(phone, build_session)
        _spawn_background(_complete_onboarding(phone, answers))
        return
    session["answers"] = answers
    session["step_index"] = next_index
    _save_session(phone, session)
    _send_onboarding_prompt(phone, next_index)


def _start_onboarding(phone: str) -> None:
    session = {"mode": "onboarding", "step_index": 0, "answers": {}, "started_at": _utc_now_iso()}
    _save_session(phone, session)
    _audit(phone, "operator.add_client.started", {})
    _send_onboarding_prompt(phone, 0)


def _parse_missing_field_submission(text: str, missing_fields: list[str]) -> tuple[dict[str, str], list[str]]:
    answers: dict[str, str] = {}
    raw = str(text or "").strip()
    if len(missing_fields) == 1:
        label_pattern = re.compile(r"^\s*(?:[-*]\s*)?(?:" + re.escape(missing_fields[0]) + r")(?:\s*(?::|-|=)\s*|\s+(?:is|are|will be|would be|includes?)\s+)", re.IGNORECASE | re.MULTILINE)
        match = label_pattern.search(raw)
        if match:
            answers[missing_fields[0]] = raw[match.end():].strip()
        else:
            answers[missing_fields[0]] = raw
        return answers, []
    numbered_pattern = re.compile(r"(?ms)^\s*(\d{1,2})[.)]\s*(.+?)(?::\s*|\n)(.*?)(?=^\s*\d{1,2}[.)]\s+|\Z)")
    numbered_matches = numbered_pattern.findall(raw)
    if numbered_matches:
        for _num, _label, value in numbered_matches:
            value = value.strip()
            if value:
                for field in missing_fields:
                    if field not in answers:
                        answers[field] = value
                        break
    if not answers:
        for field in missing_fields:
            label_pattern = re.compile(r"^\s*(?:[-*]\s*)?(?:" + re.escape(field) + r")(?:\s*(?::|-|=)\s*|\s+(?:is|are|will be|would be|includes?)\s+)", re.IGNORECASE | re.MULTILINE)
            match = label_pattern.search(raw)
            if match:
                end = raw.find("\n", match.end())
                answers[field] = raw[match.end():end].strip() if end > 0 else raw[match.end():].strip()
    unresolved = [f for f in missing_fields if f not in answers]
    return answers, unresolved


async def _send_strategy_reply(phone: str, prompt_text: str) -> None:
    client_id_override = _extract_client_id_from_text(prompt_text)
    session = _session_payload(phone)
    client_id = client_id_override or str(session.get("client_id") or "").strip()
    if not client_id:
        send_text_message(phone, "*Strategy needs a client* \u26a0\ufe0f\nExample: /strategy @client next month launch plan")
        return
    send_text_message(phone, f"*Building strategy* \U0001f4ca \u2014 {_format_client_label(client_id)}\nJarvis is preparing the plan now.")
    request = build_strategy_request_from_prompt(prompt_text)
    plan = await asyncio.to_thread(run_strategy_agent, client_id, request.get("window") or "next_7_days", request.get("goal") or prompt_text, request.get("campaign_context") or "", request.get("requested_prompt") or prompt_text)
    if str(plan.get("error") or "").strip():
        send_text_message(phone, f"*Strategy request failed* \u26a0\ufe0f\n{plan.get('error')}")
        return
    send_text_message(phone, f"*Strategy ready* \U0001f4ca\n{summarize_strategy_plan_reply(plan)}")


async def _send_connect_link(phone: str, client_id: str) -> None:
    resolved = resolve_client_id(client_id)
    row = _get_client_row(resolved)
    if not row:
        profile = (get_client_store().get_client(resolved) or {}).get("profile_json") or {}
        bname = str(profile.get("business_name") or "").strip()
        missing_detail = ""
        if not bname:
            send_text_message(phone, f"*Client not found* \u26a0\ufe0f\nJarvis could not find client {client_id}.")
            return
        label = _format_client_label(resolved, bname)
    else:
        label = _format_client_label(resolved, (row.get("profile") or {}).get("business_name"))
    link = build_meta_connect_link(resolved, phone)
    if not link:
        send_text_message(phone, "*Meta connect is not ready* \u26a0\ufe0f\nJarvis cannot build the Meta connect handoff yet.")
        return
    session = _session_payload(phone)
    session.update({"mode": "connect_wait", "pending_connect_client_id": resolved, "pending_connect_link": link, "updated_at": _utc_now_iso()})
    _save_session(phone, session)
    _audit(phone, "operator.connect.link_sent", {"client_id": resolved})
    send_text_message(phone, f"*Connect Meta* \U0001f517 \u2014 {label}\nOpen this secure link in your browser:\n{link}\n\nFinish the Meta login there. Jarvis will confirm here automatically.")


def _select_client_from_reply(reply_text: str) -> str:
    raw = _normalize_text(reply_text)
    if raw.isdigit():
        rows = _client_rows()
        index = int(raw) - 1
        if 0 <= index < len(rows):
            return rows[index]["client_id"]
    explicit = _extract_client_id_from_text(raw)
    if explicit:
        return explicit
    for row in _client_rows():
        if raw.lower() == row["display_name"].lower():
            return row["client_id"]
    return ""

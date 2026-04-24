

def _build_onboarding_prompt(index: int) -> str:
    total = len(ONBOARDING_STEPS)
    _key, prompt = ONBOARDING_STEPS[index]
    intro = "Let's add a new client.\n\n" if index == 0 else ""
    return f"{intro}Step {index + 1} of {total}\n{prompt}"


def _send_onboarding_prompt(phone: str, index: int) -> None:
    key, _prompt = ONBOARDING_STEPS[index]
    prompt_text = _build_onboarding_prompt(index)
    if key == "main_language":
        result = send_button_message(
            phone, header_text="Jarvis Intake", body_text=prompt_text,
            buttons=[
                {"id": "OP_ONBOARD_LANG:arabic", "title": "Arabic"},
                {"id": "OP_ONBOARD_LANG:english", "title": "English"},
                {"id": "OP_ONBOARD_LANG:both", "title": "Both"},
            ],
            footer_text="You can also type the answer manually.",
        )
        if result.get("success"):
            return
    send_text_message(phone, prompt_text)


def _send_root_menu(phone: str) -> None:
    session = _session_payload(phone)
    rows = _client_rows()
    connected_count = sum(1 for r in rows if r["connected"])
    schedule = load_schedule("schedule.json")
    views = split_schedule_views(schedule)
    active_count = len(views.get("active") or [])

    dashboard = (
        "\u26a1 *Jarvis \u00b7 Agency OS*\n\n"
        "\U0001f1f0\U0001f1fc  *United Marketing Agency*\n"
        "_Your dedicated AI operator is online and standing by._\n\n"
        "\u2500\u2500\u2500  *Live Dashboard*  \u2500\u2500\u2500\n"
        f"* {len(rows)} client{'s' if len(rows) != 1 else ''} loaded\n"
        f"* {connected_count} Meta account{'s' if connected_count != 1 else ''} connected\n"
        f"* {active_count} release{'s' if active_count != 1 else ''} queued\n"
        "\u2699\ufe0f  All systems operational\n\n"
    )
    context = _root_menu_context(session)
    if context:
        dashboard += f"{context}\n\n"
    dashboard += "What would you like to do?"

    _audit(phone, "root_menu", {})
    result = send_button_message(
        phone, header_text="Jarvis", body_text=dashboard,
        buttons=[
            {"id": "OP_MENU:POST", "title": "New Post"},
            {"id": "OP_MENU:ADD_CLIENT", "title": "Add Client"},
            {"id": "OP_MENU:MORE", "title": "More"},
        ],
        footer_text="Jarvis \u00b7 WhatsApp Operator",
    )
    if not result.get("success"):
        send_text_message(phone, _help_text())


def _send_more_menu(phone: str) -> None:
    _audit(phone, "more_menu", {})
    result = _send_list_card(
        phone, header_text="Operator Menu",
        body_text="*Operator Actions* \u2726\nChoose the next workspace or check a live system summary.",
        button_text="View Actions",
        sections=[{
            "title": "Operator Actions",
            "rows": [
                {"id": "OP_MORE:STRATEGY", "title": "Strategy", "description": "Research-backed content plan"},
                {"id": "OP_MORE:CONNECT", "title": "Connect Meta", "description": "Link Facebook + Instagram"},
                {"id": "OP_MORE:CLIENTS", "title": "Clients", "description": "View saved client roster"},
                {"id": "OP_MORE:SCHEDULES", "title": "Schedules", "description": "Upcoming releases queue"},
                {"id": "OP_MORE:STATUS", "title": "Status", "description": "System & connection health"},
                {"id": "OP_MORE:REFRESH_META", "title": "Refresh Meta Status", "description": "Force-recheck all connections"},
                {"id": "OP_MORE:HELP", "title": "Help", "description": "Back to main Jarvis menu"},
            ],
        }],
        footer_text="Jarvis \u00b7 Operator",
        fallback_text="Operator Actions:\n1. Strategy\n2. Connect Meta\n3. Clients\n4. Schedules\n5. Status\n6. Refresh Meta Status\n7. Help",
    )
    _send_back_button(phone, "Return to the main Jarvis menu", "ROOT")


def _send_add_client_mode_picker(phone: str) -> None:
    _save_session(phone, {"mode": "add_client_mode_picker", "updated_at": _utc_now_iso()})
    _audit(phone, "operator.add_client.started", {"picker": True})
    send_button_message(
        phone, header_text="New Client",
        body_text=(
            "*How should Jarvis build this profile?*\n"
            "Pick the strongest source you already have.\n\n"
            "\u2022 *Quick Brief* \u2014 structured one-message intake\n"
            "\u2022 *Import Brief* \u2014 existing PDF, DOCX, TXT, or MD\n"
            "\u2022 *Scan Website* \u2014 website is the best starting source"
        ),
        buttons=[
            {"id": "OP_ADD_CLIENT:QUICK", "title": "Quick Brief"},
            {"id": "OP_ADD_CLIENT:IMPORT", "title": "Import Brief"},
            {"id": "OP_ADD_CLIENT:WEBSITE", "title": "Scan Website"},
        ],
        footer_text="You can also type Quick Brief, Import Brief, or Scan Website.",
    )
    _send_back_button(phone, "Need to go back to the main Jarvis menu?", "ROOT")


def _build_clients_summary() -> str:
    rows = _client_rows()
    if not rows:
        return "*Client Roster* \u2726\nNo clients saved yet.\n\nReply with *Add Client* to create the first one."
    lines = [f"*Client Roster* \u2726\n{len(rows)} saved client(s)"]
    for row in rows[:20]:
        health = row.get("meta_health") or {}
        status = _meta_status_label(health) if health else ("Connected" if row["connected"] else "Needs connect")
        if str(health.get("probe_source") or "") == "cached":
            status = status
        lines.append(f"\u2022 {row['display_name']} [{row['client_id']}] \u2014 {status}")
    lines.append("\n_Meta status may be cached for up to 90 seconds._")
    return "\n".join(lines)


def _build_schedules_summary() -> str:
    schedule = load_schedule("schedule.json")
    views = split_schedule_views(schedule)
    active = list(views.get("active") or [])
    if not active:
        return "*Release Queue* \U0001f4c5\nNo active releases are queued right now."
    lines = [f"*Release Queue* \U0001f4c5\n{len(active)} scheduled release(s)"]
    for item in active[:12]:
        client_id = str(item.get("client") or "").strip()
        topic = str(item.get("topic") or item.get("draft_name") or "Untitled").strip()
        date_label = str(item.get("scheduled_date") or "").strip() or ", ".join(item.get("days") or [])
        time_label = str(item.get("time") or "").strip()
        lines.append(f"\u2022 {_format_client_label(client_id)}: {topic} | {date_label} {time_label}".strip())
    return "\n".join(lines)


def _build_status_summary() -> str:
    rows = _client_rows()
    connected = sum(1 for row in rows if str((row.get("meta_health") or {}).get("status") or "").strip().lower() == "connected")
    expired = sum(1 for row in rows if str((row.get("meta_health") or {}).get("status") or "").strip().lower() == "expired_or_invalid")
    missing_meta = sum(1 for row in rows if str((row.get("meta_health") or {}).get("status") or "").strip().lower() == "missing")
    unknown_meta = sum(1 for row in rows if str((row.get("meta_health") or {}).get("status") or "").strip().lower() == "unknown")
    schedule = load_schedule("schedule.json")
    views = split_schedule_views(schedule)
    active_count = len(views.get("active") or [])
    history_count = len(views.get("history") or [])
    summary = (
        "*System Status* \u2726\n"
        f"\u2022 Clients: {len(rows)} total\n"
        f"\u2022 Connected Meta accounts: {connected}\n"
        f"\u2022 Expired Meta accounts: {expired}\n"
        f"\u2022 Missing Meta connections: {missing_meta}\n"
        f"\u2022 Meta status unknown: {unknown_meta}\n"
        f"\u2022 Active scheduled jobs: {active_count}\n"
        f"\u2022 Schedule history rows: {history_count}\n"
        f"\u2022 Operator phone: {normalize_phone(get_agency_config().get('owner_phone')) or 'not configured'}\n\n"
        "*Client Meta health*\n"
    )
    for row in rows:
        profile = row.get("profile") or {}
        bname = str(profile.get("business_name") or "").strip()
        label = _format_client_label(row["client_id"], bname)
        health = row.get("meta_health") or {}
        summary += f"\u2022 {label}: {_meta_status_label(health)}\n"
    summary += "\n_Meta status may be cached for up to 90 seconds. Use Refresh Meta Status after reconnecting._"
    return summary


def _slugify_client_id(business_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(business_name or "").strip().lower()).strip("_")
    return slug or f"client_{uuid.uuid4().hex[:6]}"


def _unique_client_id(business_name: str) -> str:
    base = _slugify_client_id(business_name)
    existing = {row["client_id"].lower() for row in _client_rows()}
    if base.lower() not in existing:
        return base
    for index in range(2, 50):
        candidate = f"{base}_{index}"
        if candidate.lower() not in existing:
            return candidate
    return f"{base}_{uuid.uuid4().hex[:4]}"


def _recent_client_captions(client_id: str, *, exclude_bundle_name: str | None = None) -> list[str]:
    bundles = list_client_drafts(client_id).get("bundles", {})
    entries: list[str] = []
    for bundle_name, payload in (bundles or {}).items():
        if exclude_bundle_name and str(bundle_name).strip() == str(exclude_bundle_name).strip():
            continue
        caption_text = str((payload or {}).get("caption_text") or "").strip()
        if caption_text:
            entries.append(caption_text)
    return entries[-5:][::-1]


def _derive_topic(source_text: str, client_id: str, media_kind: str, asset_count: int) -> str:
    cleaned = ROBUST_CLIENT_MENTION_RE.sub("", str(source_text or ""))
    cleaned = RAW_CLIENT_MENTION_RE.sub("", cleaned)
    cleaned = re.sub(r"^\s*/\w+\s*", "", cleaned).strip(" -:\n")
    cleaned = re.sub(r"\b(whatsapp|carousel|reel|concept|image post|draft)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if cleaned:
        row = _get_client_row(client_id)
        profile = (row or {}).get("profile") or {}
        city = str(profile.get("city_market") or "").strip()
        services = str(profile.get("services") or profile.get("what_they_sell") or "").strip()
        if media_kind == "video" and services:
            return f"Feature {services} with a premium, locally grounded reel caption."
        return cleaned
    if media_kind == "video":
        return f"Create a premium, locally grounded reel caption from the saved client profile."
    if asset_count > 1:
        return f"Build a premium carousel caption from the saved client profile."
    return f"Create a premium single-image caption from the saved client profile."


def _infer_media_bundle(media_refs: list[dict[str, Any]]) -> tuple[str, str]:
    image_count = sum(1 for item in media_refs if str(item.get("kind") or "").strip() == "image")
    video_count = sum(1 for item in media_refs if str(item.get("kind") or "").strip() == "video")
    if video_count > 1 or (video_count and image_count):
        return "invalid", "Phase 1 supports either one video document or one-or-more image documents, but not mixed media bundles."
    if video_count == 1:
        return "video", ""
    if image_count >= 2:
        return "image_carousel", ""
    if image_count == 1:
        return "image_single", ""
    return "invalid", "No publishable media documents were collected."


def _build_media_collect_message(media_refs: list[dict[str, Any]], incoming_kind: str, existing_refs: list[dict[str, Any]] | None = None) -> str:
    total = len(media_refs)
    if incoming_kind == "video":
        return f"*Video received* \U0001f3ac\n{total} video in this bundle.\nJarvis will wait 10 seconds for notes, then prepare the preview.\nYou can still add notes while I collect."
    if total == 1:
        return f"*Image received* \U0001f4f8\n1 image in this bundle.\nJarvis will wait 10 seconds before preparing the preview.\nSend more documents within that window to build a carousel, or add notes."
    return f"*Carousel updated* \U0001f3a0\n{total} images in this bundle.\nJarvis will wait 10 more seconds before preparing the preview.\nKeep sending documents for the same post, or add notes."


def _safe_asset_filename(client_id: str, original_name: str, index: int, mime_type: str) -> str:
    stem, ext = os.path.splitext(str(original_name or "").strip())
    ext = ext.lower()
    if not ext:
        ext = ".mp4" if str(mime_type or "").startswith("video/") else ".jpg"
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_") or "whatsapp_upload"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{stem}_{timestamp}_{index}{ext}"


def _preview_text(client_id: str, display_direction: str, caption_payload: dict[str, Any], media_kind: str, item_count: int) -> str:
    hashtags = " ".join(caption_payload.get("hashtags") or [])
    quality = caption_payload.get("quality_gate") or {}
    score = quality.get("score", 0)
    threshold = quality.get("threshold", 85)
    verdict = str(quality.get("verdict") or ("Approved" if score >= threshold else "Needs another pass"))
    dims = quality.get("dimensions") or {}
    quality_snapshot = ""
    if dims:
        parts = []
        for key, label in [("visual_grounding", "Visual"), ("brand_voice_fidelity", "Voice"), ("audience_platform_fit", "Platform"), ("realism", "Realism"), ("hook_strength", "Hooks"), ("trend_relevance", "Trend")]:
            if key in dims:
                parts.append(f"{label} {dims[key]}")
        if parts:
            quality_snapshot = f"Quality snapshot: {' \u00b7 '.join(parts)}\n"
    media_label = {"image_single": "1 image post", "image_carousel": f"{item_count} image carousel", "video": "1 video reel"}.get(media_kind, f"{item_count} media item(s)")
    direction_clean = re.sub(r"\b(whatsapp|carousel|reel|draft|concept)\b", "", display_direction, flags=re.IGNORECASE).strip()
    direction_line = f"Direction: {direction_clean}\n" if direction_clean else ""
    return (
        f"*Preview ready* \u2726\nClient: *{_format_client_label(client_id)}*\n"
        f"Format: {media_label}\n"
        f"Quality: {score}/{threshold} - {verdict}\n"
        f"{quality_snapshot}"
        f"{direction_line}\n"
        f"*Caption*\n{caption_payload.get('caption', '').strip()}\n\n"
        f"*Hashtags*\n{hashtags}\n\n"
        "Reply with one of the examples below if you prefer typing:\n"
        "\u2022 post now\n"
        "\u2022 schedule friday 17 at 6am\n"
        "\u2022 edit [paste your edited caption here]\n"
        "\u2022 edit hashtags #kuwait #specialtycoffee\n"
        "\u2022 append hashtags #icedcoffee\n"
        "\u2022 change make it sharper, more premium, and more local to Kuwait\n"
        "\u2022 try again\n"
        "\u2022 cancel"
    ).strip()


def _build_caption_progress_callback(phone: str, client_id: str):
    announced = {"drafting": False}
    def callback(event: dict[str, Any]):
        event_name = str(event.get("event") or "").strip()
        if event_name == "drafting_started" and not announced["drafting"]:
            announced["drafting"] = True
            send_text_message(phone, f"*Writing caption* \u270d\ufe0f\nJarvis is crafting the caption for {_format_client_label(client_id)}.")
    return callback


def _send_preview_card(phone: str, session_or_payload: dict[str, Any]) -> None:
    gen_state = str(session_or_payload.get("generation_state") or "").strip()
    caption_payload = dict(session_or_payload.get("caption_payload") or {})
    cp_gen_state = str(caption_payload.get("generation_state") or "").strip()
    if gen_state == "generation_unavailable" or cp_gen_state == "generation_unavailable":
        reason = str(caption_payload.get("reason") or "Jarvis could not produce a real caption draft from the current model route.").strip()
        send_text_message(phone, f"*Caption generation failed* \u26a0\ufe0f\nJarvis could not produce a real caption draft from the current model route.\nReason: {reason}")
        _send_button_card(
            phone, header_text="Caption Blocked",
            body_text="A fresh model pass is needed before a caption preview can be shown.",
            buttons=[
                {"id": "OP_PREVIEW:TRY_AGAIN", "title": "Try Again"},
                {"id": "OP_PREVIEW:REVISE", "title": "Revise"},
                {"id": "OP_PREVIEW:CANCEL", "title": "Cancel"},
            ],
            footer_text="No fallback caption is shown when the model route fails.",
            fallback_text="Caption blocked:\n1. Try Again\n2. Revise\n3. Cancel\n\nReply with one of these if you prefer typing: try again, revise, change make the brief sharper and more local, or cancel.",
            audit_event="preview_generation_unavailable",
        )
        return
    client_id = str(session_or_payload.get("client_id") or "").strip()
    display_direction = str(session_or_payload.get("display_direction") or session_or_payload.get("content_goal") or session_or_payload.get("topic") or "").strip()
    media_kind = str(session_or_payload.get("media_kind") or "image_single")
    item_count = int(session_or_payload.get("item_count") or 1)
    send_text_message(phone, _preview_text(client_id, display_direction, caption_payload, media_kind, item_count))
    _send_button_card(
        phone, header_text="Next Move",
        body_text="What would you like to do with this draft?",
        buttons=[
            {"id": "OP_PREVIEW:POST_NOW", "title": "Publish Now"},
            {"id": "OP_PREVIEW:SCHEDULE", "title": "Schedule"},
            {"id": "OP_PREVIEW:REVISE", "title": "Revise"},
        ],
        footer_text="You can also reply with text",
        fallback_text="Next move:\n1. Publish Now\n2. Schedule\n3. Revise\n\nReply with one of these if you prefer typing: post now, schedule friday 17 at 6am, revise, change make it sharper and more local, or cancel.",
        audit_event="preview_actions",
    )


def _prompt_preview_schedule(phone: str, session: dict[str, Any]) -> None:
    session["expected_reply"] = "schedule"
    _save_session(phone, session)
    send_text_message(phone, "*Schedule this draft* \U0001f4c5\nSend the release time like: today 2pm, tomorrow 7pm, or friday 17 at 6am.")


def _prompt_preview_revise(phone: str, session: dict[str, Any]) -> None:
    session["expected_reply"] = "revise"
    _save_session(phone, session)
    send_text_message(phone, "*Revise this draft* \u270f\ufe0f\nTell Jarvis what to change. Example: make it sharper, more premium, more local to Kuwait, and shorter.")


def _send_strategy_menu(phone: str, client_id: str) -> None:
    _save_session(phone, {"mode": "strategy_menu", "client_id": client_id, "updated_at": _utc_now_iso()})
    _audit(phone, "strategy_menu", {"client_id": client_id})
    send_button_message(
        phone, header_text="Strategy",
        body_text=f"*Strategy* \U0001f4ca \u2014 {_format_client_label(client_id)}\nBuild a new research-backed plan or open a saved one.",
        buttons=[
            {"id": "OP_STRATEGY:BUILD", "title": "New Plan"},
            {"id": "OP_STRATEGY:VIEW", "title": "Saved Plans"},
            {"id": "OP_NAV:MORE", "title": "Go Back"},
        ],
        footer_text="Jarvis \u00b7 Strategy",
    )

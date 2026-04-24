

async def _handle_preview_reply(phone: str, text: str, session: dict[str, Any]) -> None:
    lowered = _normalize_text(text).lower()
    client_id = str(session.get("client_id") or "").strip()
    bundle_name = str(session.get("bundle_name") or "").strip()
    topic = str(session.get("topic") or session.get("content_goal") or bundle_name or "").strip()
    gen_state = str(session.get("generation_state") or str((session.get("caption_payload") or {}).get("generation_state") or "")).strip()
    caption_payload = dict(session.get("caption_payload") or {})
    is_blocked = gen_state == "generation_unavailable"

    if lowered in {"cancel", "/cancel"}:
        _clear_session(phone)
        send_text_message(phone, "*Preview dismissed* \u2716\ufe0f\nThe draft is still saved if you want to return to it later.")
        return

    # Try again
    if lowered == "try again" or lowered == "try_again":
        media_kind = str(session.get("media_kind") or "image_single")
        existing_draft = (list_client_drafts(client_id).get("bundles", {}).get(bundle_name) or {})
        operator_brief = str(session.get("operator_brief") or session.get("source_text") or "").strip()
        send_text_message(phone, "*Regenerating caption* \u270d\ufe0f\nJarvis is generating a fresh batch with a stronger hook strategy.")
        current_caption = str(caption_payload.get("caption") or "").strip()
        quality_gate = dict(caption_payload.get("quality_gate") or {})
        failures = list(quality_gate.get("failures") or (caption_payload.get("retry_memory") or {}).get("failure_reasons") or [])
        if str(caption_payload.get("model_failure_reason") or "").strip():
            failures.append(str(caption_payload.get("model_failure_reason")))
        new_caption_payload = await asyncio.to_thread(
            generate_caption_payload, client_id, topic,
            "carousel_post" if media_kind == "image_carousel" else ("reel_post" if media_kind == "video" else "image_post"),
            _recent_client_captions(client_id, exclude_bundle_name=bundle_name),
            mode="generate", current_caption=current_caption, prior_best_caption=current_caption,
            avoid_repeat_failures=failures, operator_brief=operator_brief,
        )
        _update_session_after_regeneration(phone, session, new_caption_payload, bundle_name, client_id, existing_draft)
        return

    # Revise prompt (just set expected_reply)
    if lowered in {"revise", "revise brief"}:
        _prompt_preview_revise(phone, session)
        return

    # Edit caption directly
    if lowered.startswith("edit ") and not lowered.startswith("edit hashtags") and not lowered.startswith("edit hashtag"):
        new_caption = _normalize_text(text)[5:].strip()
        if not new_caption:
            send_text_message(phone, "*Edit needs a caption* \u2726\nType: edit [your new caption text]")
            return
        caption_payload["caption"] = new_caption
        caption_payload["generation_source"] = "operator_edited"
        if not caption_payload.get("quality_gate", {}).get("passed"):
            caption_payload.setdefault("quality_gate", {})["passed"] = True
            caption_payload["quality_gate"]["verdict"] = "Approved (operator edit)"
        session["caption_payload"] = caption_payload
        session["generation_state"] = "success"
        existing_draft = (list_client_drafts(client_id).get("bundles", {}).get(bundle_name) or {})
        save_draft_payload(client_id, bundle_name, {
            **existing_draft, "caption_text": new_caption, "caption_status": "ready",
            "caption_metadata": dict(existing_draft.get("caption_metadata") or {}),
        })
        _save_session(phone, session)
        _send_preview_card(phone, session)
        return

    # Edit hashtags
    if lowered.startswith("edit hashtags"):
        raw_tags = _normalize_text(text)[len("edit hashtags"):].strip()
        if not raw_tags:
            send_text_message(phone, "*Hashtag edit needs tags* \u2726\nType: edit hashtags #kuwait #specialtycoffee")
            return
        new_tags = [tag.strip() for tag in re.split(r"[\s,]+", raw_tags) if tag.strip()]
        new_tags = [tag if tag.startswith("#") else f"#{tag}" for tag in new_tags]
        new_tags = [re.sub(r"[^\w#\u0600-\u06FF-]+", "", tag) for tag in new_tags if tag]
        caption_payload["hashtags"] = new_tags
        caption_payload["generation_source"] = "operator_edited"
        session["caption_payload"] = caption_payload
        existing_draft = (list_client_drafts(client_id).get("bundles", {}).get(bundle_name) or {})
        save_draft_payload(client_id, bundle_name, {**existing_draft, "hashtags": new_tags})
        _save_session(phone, session)
        _send_preview_card(phone, session)
        return

    # Append hashtags
    if lowered.startswith("append hashtags"):
        raw_tags = _normalize_text(text)[len("append hashtags"):].strip()
        if not raw_tags:
            send_text_message(phone, "*Hashtag edit needs tags* \u2726\nType: append hashtags #icedcoffee #kuwait")
            return
        new_tags = [tag.strip() for tag in re.split(r"[\s,]+", raw_tags) if tag.strip()]
        new_tags = [tag if tag.startswith("#") else f"#{tag}" for tag in new_tags]
        new_tags = [re.sub(r"[^\w#\u0600-\u06FF-]+", "", tag) for tag in new_tags if tag]
        existing_tags = list(caption_payload.get("hashtags") or [])
        existing_lower = {t.lower() for t in existing_tags}
        for tag in new_tags:
            if tag.lower() not in existing_lower:
                existing_tags.append(tag)
                existing_lower.add(tag.lower())
        caption_payload["hashtags"] = existing_tags
        caption_payload["generation_source"] = "operator_edited"
        session["caption_payload"] = caption_payload
        existing_draft = (list_client_drafts(client_id).get("bundles", {}).get(bundle_name) or {})
        save_draft_payload(client_id, bundle_name, {**existing_draft, "hashtags": existing_tags})
        _save_session(phone, session)
        _send_preview_card(phone, session)
        return

    # expected_reply == revise or change command
    expected_reply = str(session.get("expected_reply") or "").strip()
    if lowered.startswith("change ") or (expected_reply == "revise" and not lowered.startswith("schedule")):
        feedback = _normalize_text(text)
        if lowered.startswith("change "):
            feedback = feedback[7:].strip()
        media_kind = str(session.get("media_kind") or "image_single")
        existing_draft = (list_client_drafts(client_id).get("bundles", {}).get(bundle_name) or {})
        current_caption = str(caption_payload.get("caption") or "").strip()
        mode = "generate" if is_blocked else "revise"
        new_caption_payload = await asyncio.to_thread(
            generate_caption_payload, client_id, topic,
            "carousel_post" if media_kind == "image_carousel" else ("reel_post" if media_kind == "video" else "image_post"),
            _recent_client_captions(client_id, exclude_bundle_name=bundle_name),
            mode=mode, operator_brief=feedback, current_caption=current_caption,
            prior_best_caption="" if is_blocked else current_caption,
        )
        _update_session_after_regeneration(phone, session, new_caption_payload, bundle_name, client_id, existing_draft)
        return

    # Schedule follow-up
    if expected_reply == "schedule":
        intent = _parse_release_intent(text)
        if str(intent.get("mode") or "") != "schedule":
            send_text_message(phone, "*Schedule Release* \U0001f4c5\nSend the release time like: today 2pm, tomorrow 7pm, or friday 17 at 6am.")
            return
        if is_blocked:
            send_text_message(phone, "*Release blocked* \u26a0\ufe0f\nJarvis needs a real generated caption before posting or scheduling.\nUse Try Again, Revise, Edit, or Cancel.")
            return
        result = await asyncio.to_thread(
            RequestApprovalTool().execute, client_id, topic,
            intent.get("days") or [], intent.get("time") or "", bundle_name, None,
            intent.get("scheduled_date") or "", session.get("draft_id"), "whatsapp_only",
        )
        result_status = str(result.get("status") or "").strip().lower()
        if result_status == "error":
            _save_session(phone, session)
            send_text_message(phone, f"*Scheduled* \U0001f4c5\n{str(result.get('message') or result.get('error') or 'Schedule request completed.')}")
        else:
            _clear_session(phone)
            send_text_message(phone, f"*Scheduled* \U0001f4c5\n{str(result.get('message') or result.get('error') or 'Schedule request completed.')}")
        return

    # Block release when generation unavailable
    if is_blocked and lowered in {"post now", "yes now", "yes", "approve", "go", "post it"}:
        send_text_message(phone, "*Release blocked* \u26a0\ufe0f\nJarvis needs a real generated caption before posting or scheduling.\nUse Try Again, Revise, Edit, or Cancel.")
        return
    if is_blocked and lowered.startswith("schedule "):
        send_text_message(phone, "*Release blocked* \u26a0\ufe0f\nJarvis needs a real generated caption before posting or scheduling.\nUse Try Again, Revise, Edit, or Cancel.")
        return

    # Post now
    if lowered in {"post now", "yes now", "yes", "approve", "post it", "go"}:
        if is_blocked:
            send_text_message(phone, "*Release blocked* \u26a0\ufe0f\nJarvis needs a real generated caption before posting or scheduling.\nUse Try Again, Revise, Edit, or Cancel.")
            return
        result = await asyncio.to_thread(TriggerPipelineNowTool().execute, client_id, topic, None, bundle_name)
        result_status = str(result.get("status") or "").strip().lower()
        if result_status in ("error", "partial_success"):
            _save_session(phone, session)
        else:
            _clear_session(phone)
        send_text_message(phone, f"*Published* \U0001f680\n{str(result.get('message') or result.get('error') or 'Post request completed.')}")
        return

    # Schedule inline
    if lowered.startswith("schedule "):
        intent = _parse_release_intent(text)
        if str(intent.get("mode") or "") != "schedule":
            _prompt_preview_schedule(phone, session)
            return
        if is_blocked:
            send_text_message(phone, "*Release blocked* \u26a0\ufe0f\nJarvis needs a real generated caption before posting or scheduling.\nUse Try Again, Revise, Edit, or Cancel.")
            return
        result = await asyncio.to_thread(
            RequestApprovalTool().execute, client_id, topic,
            intent.get("days") or [], intent.get("time") or "", bundle_name, None,
            intent.get("scheduled_date") or "", session.get("draft_id"), "whatsapp_only",
        )
        result_status = str(result.get("status") or "").strip().lower()
        if result_status == "error":
            _save_session(phone, session)
            send_text_message(phone, f"*Scheduled* \U0001f4c5\n{str(result.get('message') or result.get('error') or 'Schedule request completed.')}")
        else:
            _clear_session(phone)
            send_text_message(phone, f"*Scheduled* \U0001f4c5\n{str(result.get('message') or result.get('error') or 'Schedule request completed.')}")
        return

    if is_blocked:
        send_text_message(phone, "*Preview reply not understood* \u26a0\ufe0f\nThis draft is still blocked. Use the buttons, or reply with try again, edit ..., edit hashtags ..., append hashtags ..., change ..., or cancel.")
    else:
        send_text_message(phone, "*Preview reply not understood* \u26a0\ufe0f\nUse the buttons, or reply with post now, schedule ..., edit ..., edit hashtags ..., append hashtags ..., change ..., try again, or cancel.")


def _update_session_after_regeneration(phone: str, session: dict[str, Any], new_caption_payload: dict[str, Any], bundle_name: str, client_id: str, existing_draft: dict[str, Any]) -> None:
    if str(new_caption_payload.get("status") or new_caption_payload.get("generation_state") or "").strip().lower() == "generation_unavailable":
        session["generation_state"] = "generation_unavailable"
        session["caption_payload"] = new_caption_payload
    else:
        session["generation_state"] = "success"
        session["caption_payload"] = new_caption_payload
    session["display_direction"] = str(new_caption_payload.get("display_direction") or session.get("display_direction") or "").strip()
    session["expected_reply"] = ""
    save_draft_payload(client_id, bundle_name, {
        **existing_draft,
        "caption_text": str(new_caption_payload.get("caption") or "").strip(),
        "caption_status": "ready" if session["generation_state"] == "success" else "blocked_generation",
        "hashtags": list(new_caption_payload.get("hashtags") or []),
        "seo_keyword_used": str(new_caption_payload.get("seo_keyword_used") or "").strip(),
        "display_direction": session["display_direction"],
        "analysis_summary": str((new_caption_payload.get("media_analysis") or {}).get("analysis_summary") or "").strip(),
        "ranking_summary": dict(new_caption_payload.get("ranking_summary") or {}),
        "hidden_variants": list(new_caption_payload.get("hidden_variants") or []),
        "retry_memory": dict(new_caption_payload.get("retry_memory") or {}),
        "quality_gate": dict(new_caption_payload.get("quality_gate") or {}),
        "generation_source": str(new_caption_payload.get("generation_source") or "").strip(),
        "provider_attempts": list(new_caption_payload.get("provider_attempts") or []),
        "model_failure_reason": str(new_caption_payload.get("model_failure_reason") or "").strip(),
        "hook_candidates": list(new_caption_payload.get("hook_candidates") or []),
        "selected_hook_family": str(new_caption_payload.get("selected_hook_family") or "").strip(),
        "client_memory_examples": list(new_caption_payload.get("client_memory_examples") or []),
    })
    _save_session(phone, session)
    _send_preview_card(phone, session)

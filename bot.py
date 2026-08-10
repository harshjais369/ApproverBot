import json
import uuid
import threading
import logging
from time import sleep
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import telebot
from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    ChatPermissions,
)
from telebot.util import escape
from flask import Flask, request, render_template, jsonify, redirect

from config import *
import database as db
import fingerprint as fp_module
import validation

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("approverbot")

# Silence noisy loggers
logging.getLogger("werkzeug").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("TeleBot").setLevel(logging.WARNING)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML', allow_sending_without_reply=True, disable_web_page_preview=True)
app = Flask(__name__)


# ═══════════════════════════════════════════════════════════════════
#  TELEGRAM BOT HANDLERS
# ═══════════════════════════════════════════════════════════════════

@bot.message_handler(commands=["start"])
def handle_start(message):
    """
    Handle /start. Also checks if this user has any pending restricted
    entries (they joined group but couldn't be DM'd), and sends them
    a verification link now.
    """
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    first_name = escape(message.from_user.first_name) or 'there'
    # Check for any restricted (un-verified) pending requests
    restricted = db.get_restricted_requests(user_id)
    if restricted:
        for req in restricted:
            token = uuid.uuid4().hex
            expires_at = (datetime.now(timezone.utc) + timedelta(minutes=PENDING_REQUEST_TTL_MINUTES)).isoformat()
            db.update_pending_token(req['id'], token, expires_at)
            verify_url = f'{WEB_BASE_URL}/verify?token={token}'
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton(
                text='\U0001f513 Verify to Access Chat',
                web_app=WebAppInfo(url=verify_url),
            ))
            markup.add(InlineKeyboardButton(
                text='🔙 Return to Group',
                url=f'https://t.me/CrocodileGamesGroup',
            ))
            bot.send_message(user_id, f'Hi <b>{first_name}</b>!\nYou\'ve joined <b>Crocodile Games</b> group but haven\'t verified yet. '
                             'Complete verification to get access <i>(send messages, stickers, etc.)</i> to the group.', reply_markup=markup)
        return
    bot.send_message(user_id, f'Hi {first_name}!\nI\'m a verification bot built by <b>Crocodile Games</b> (@CrocodileGames).')


@bot.message_handler(commands=["multis"])
def handle_multis(message):
    """Show how many users have multiple accounts."""
    if not message.from_user.id in SUPERUSERS:
        return
    clusters = db.get_all_multi_account_clusters()
    if not clusters:
        bot.reply_to(message, 'No multi-account users detected yet. Great job everyone! 🎉')
        return
    total_accounts = sum(len(c) for c in clusters)
    lines = [
        f'<b>Multi-account clusters:</b> <code>{len(clusters)}</code>',
        f'<b>Total accounts captured:</b> <code>{total_accounts}</code>',
        '',
    ]
    for i, cluster in enumerate(sorted(clusters, key=len, reverse=True), 1):
        user_labels = []
        for uid in sorted(cluster):
            name = escape(db.get_user_name(uid) or f'[id: {str(uid)}]')
            user_labels.append(f'<a href="tg://openmessage?user_id={uid}">{name}</a>')
        lines.append(f'<blockquote expandable><b>{i}. [{len(cluster)} accounts]</b>\n{"  <b>▏</b>".join(user_labels)}</blockquote>')
    bot.reply_to(message, '\n'.join(lines))


@bot.message_handler(commands=["connections", "conns", "links"])
def handle_connections(message):
    """Show all connections/links for a specific user, along with detection history."""
    if not message.from_user.id in SUPERUSERS:
        return
    parts = message.text.split()
    target_uid = None
    if len(parts) >= 2:
        try:
            target_uid = int(parts[1])
        except ValueError:
            bot.reply_to(message, 'Invalid user ID!')
            return
    elif message.reply_to_message:
        target_uid = message.reply_to_message.from_user.id
    else:
        bot.reply_to(message, '<b>Usage:</b> /links &lt;user_id | reply to user&gt;', parse_mode="HTML")
        return
    connected = db.get_all_connected_users(target_uid)
    if len(connected) <= 1:
        bot.reply_to(message, f'User {target_uid} has no linked accounts.')
        return
    details = db.get_connection_details(target_uid)
    target_name = escape(db.get_user_name(target_uid) or f'[id: {str(target_uid)}]')
    connected_labels = []
    for uid in sorted(connected):
        name = escape(db.get_user_name(uid) or f'[id: {str(uid)}]')
        connected_labels.append(f'<a href="tg://openmessage?user_id={uid}">{name}</a>')
    lines = [
        f'<b>Connections for <a href="tg://openmessage?user_id={target_uid}">{target_name}</a>:</b>\n',
        f'<b>Linked accounts ({len(connected)}):</b>\n<blockquote>• {"\n• ".join(connected_labels)}</blockquote>',
        '',
        '<b>Detection history:</b>',
    ]
    for flag in details:
        status = flag["action_taken"] or 'N/A'
        score = flag["similarity_score"] or 0.0
        components = (flag["matching_components"] or 'N/A').removeprefix('[').removesuffix(']').replace('"', '')
        ts = flag["created_at"] or 'N/A'
        new_name = escape(flag.get("new_user_name") or db.get_user_name(flag["new_user_id"]) or f'[id: {flag["new_user_id"]}]')
        matched_name = escape(flag.get("matched_user_name") or db.get_user_name(flag["matched_user_id"]) or f'[id: {flag["matched_user_id"]}]')
        new_lbl = f'<a href="tg://openmessage?user_id={flag["new_user_id"]}">{new_name}</a>'
        matched_lbl = f'<a href="tg://openmessage?user_id={flag["matched_user_id"]}">{matched_name}</a>'
        lines.append(
            '<blockquote expandable>'
            f'<b>{new_lbl} &lt;-&gt; {matched_lbl}</b>\n'
            f'<b>Similarity:</b> {score:.0%}\n'
            f'<b>Action:</b> {status.upper()}\n'
            f'<b>Signals:</b> <i>{components}</i>\n'
            f'<b>Time:</b> {ts}'
            '</blockquote>'
        )
    bot.reply_to(message, '\n'.join(lines))


@bot.chat_join_request_handler()
def handle_join_request(jr):
    """
    Triggered when a user requests to join a group where the bot is admin
    with 'Approve new members' permission.

    If the request carries a `query_id`, the bot can open a Mini App
    directly via sendChatJoinRequestWebApp — no DM needed.
    """
    chat_id = jr.chat.id
    user_id = jr.from_user.id
    full_name = jr.from_user.first_name + (' ' + jr.from_user.last_name if jr.from_user.last_name else '')
    if ALLOWED_GROUPS and chat_id not in ALLOWED_GROUPS:
        logger.debug('Ignoring join request from non-allowed group %s', chat_id)
        return
    if user_id in SUPERUSERS:
        # Auto-approve superusers
        try:
            query_id = getattr(jr, 'query_id', None)
            if query_id:
                bot.answer_chat_join_request_query(query_id, 'approve')
            else:
                bot.approve_chat_join_request(chat_id, user_id)
            logger.info('Auto-approved superuser %s for chat %s', user_id, chat_id)
        except Exception:
            logger.exception('Failed to approve superuser %s', user_id)
        return
    token = uuid.uuid4().hex
    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(minutes=PENDING_REQUEST_TTL_MINUTES)
    ).isoformat()

    # ── Bot API 10.1: open Mini App directly via join request query ──
    query_id = getattr(jr, 'query_id', None)
    if query_id:
        try:
            verify_url = f'{WEB_BASE_URL}/verify?token={token}'
            bot.send_chat_join_request_web_app(query_id, verify_url)
            db.create_pending_request(
                chat_id=chat_id,
                user_id=user_id,
                user_name=full_name,
                token=token,
                expires_at=expires_at,
                status='pending',
            )
            logger.info(f'Opened Mini App via query_id for user {user_id} in chat {chat_id}')
            return
        except Exception:
            logger.exception(f'sendChatJoinRequestWebApp failed for user {user_id}, falling back to DM flow')
            # Fall through to legacy DM flow below

    # ── Legacy flow: DM the user with a verification button ──
    try:
        verify_url = f'{WEB_BASE_URL}/verify?token={token}'
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(
            text='\U0001f513 I\'m not a robot',
            web_app=WebAppInfo(url=verify_url),
        ))
        markup.add(InlineKeyboardButton(
            text='🔙 Return to Group',
            url=f'https://t.me/CrocodileGamesGroup',
        ))
        bot.send_message(user_id, f'Hi <b>{escape(full_name)}</b>!\nTo join the group <i>(@CrocodileGamesGroup)</i>, '
                         'please <b>verify you are not a robot</b> by accepting the terms (rules).', reply_markup=markup)
        # DM succeeded — store as normal pending request
        db.create_pending_request(
            chat_id=chat_id,
            user_id=user_id,
            user_name=full_name,
            token=token,
            expires_at=expires_at,
            status='pending',
        )
        logger.info('Sent verification DM to user %s for chat %s', user_id, chat_id)
    except telebot.apihelper.ApiTelegramException as e:
        err_msg = str(e).lower()
        if 'bot can\'t initiate conversation' in err_msg or 'chat not found' in err_msg or 'forbidden' in err_msg:
            # User never started the bot — approve but restrict (mute)
            logger.warning('Cannot DM user %s — approving with restrictions', user_id)
            try:
                # Persist restricted state before approval to avoid race with new_chat_members event.
                db.create_pending_request(
                    chat_id=chat_id,
                    user_id=user_id,
                    user_name=full_name,
                    token=None,
                    expires_at=None,
                    status='restricted',
                )
                bot.approve_chat_join_request(chat_id, user_id)
                bot.restrict_chat_member(
                    chat_id, user_id,
                    permissions=ChatPermissions(
                        can_send_messages=False,
                        can_send_media_messages=False,
                        can_send_other_messages=False,
                        can_add_web_page_previews=False,
                    ),
                )
                sleep(1)
                # Send message in the group with mention to user prompting to complete verification
                markup = InlineKeyboardMarkup([[InlineKeyboardButton(
                        text='\U0001f513 Verify',
                        url=f'https://t.me/{BOT_USERNAME}?start=verifyInChat{chat_id}_{user_id}',
                )]])
                name_mention = f'<a href="tg://user?id={user_id}">{escape(full_name if len(full_name) <= 25 else full_name[:22] + "...")}</a>'
                bot.send_message(chat_id, f'Hi <b>{name_mention}</b>!\nTo access this chat, please DM me to '
                                 '<b>verify you are not a robot</b> by accepting the terms (rules).', reply_markup=markup)
            except Exception:
                logger.exception('Failed to approve/restrict user %s in chat %s', user_id, chat_id)
        else:
            logger.exception('Telegram API error for join request user %s', user_id)
    except Exception:
        logger.exception('Unexpected error handling join request for user %s', user_id)

@bot.chat_member_handler()
def handle_chat_member_update(update):
    """Kick users who entered chat without being allowed by the bot flow."""
    chat_id = update.chat.id
    user_id = update.new_chat_member.user.id
    if ALLOWED_GROUPS and chat_id not in ALLOWED_GROUPS:
        return
    if user_id in SUPERUSERS or user_id == BOT_ID:
        return
    old_status = update.old_chat_member.status
    new_status = update.new_chat_member.status
    if old_status in {'member', 'administrator', 'creator'} \
        or (old_status == 'restricted' and bool(getattr(update.old_chat_member, 'is_member', False))):
        return
    if not (new_status in {'member', 'administrator', 'creator'} \
        or (new_status == 'restricted' and bool(getattr(update.new_chat_member, 'is_member', False)))):
        return
    latest_status = (db.get_latest_request(chat_id, user_id) or {}).get('status')
    if latest_status == 'completed' or latest_status == 'restricted':
        return
    try:
        bot.ban_chat_member(chat_id, user_id)
        bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
        logger.warning('Kicked unauthorized join user %s from chat %s (status_now=%s)', user_id, chat_id, latest_status)
    except Exception:
        logger.exception('Failed to kick unauthorized join user %s from chat %s (status_now=%s)', user_id, chat_id, latest_status)


# ── Admin callback handlers ───────────────────────────────────────

@bot.callback_query_handler(func=lambda call: call.data.startswith("ban:"))
def handle_ban(call):
    if not call.from_user.id in SUPERUSERS:
        bot.answer_callback_query(call.id, "Unauthorized.")
        return
    parts = call.data.split(":")
    chat_id, user_id = int(parts[1]), int(parts[2])
    try:
        bot.ban_chat_member(chat_id, user_id)
        bot.edit_message_text(
            call.message.text + f"\n\n--- User {user_id} BANNED by admin ---",
            call.message.chat.id,
            call.message.message_id,
        )
    except Exception as e:
        bot.answer_callback_query(call.id, f"Error: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("banboth:"))
def handle_ban_both(call):
    if not call.from_user.id in SUPERUSERS:
        bot.answer_callback_query(call.id, "Unauthorized.")
        return
    parts = call.data.split(":")
    chat_id, user1, user2 = int(parts[1]), int(parts[2]), int(parts[3])
    errors = []
    for uid in [user1, user2]:
        try:
            bot.ban_chat_member(chat_id, uid)
        except Exception as e:
            errors.append(f"User {uid}: {e}")
    if errors:
        bot.answer_callback_query(call.id, f"Partial: {'; '.join(errors)}")
    bot.edit_message_text(
        call.message.text + f"\n\n--- Users {user1} & {user2} BANNED by admin ---",
        call.message.chat.id,
        call.message.message_id,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith(("dismiss:", "dismiss_req:")))
def handle_dismiss(call):
    """Dismiss button — simply removes all inline buttons from the alert message."""
    if not call.from_user.id in SUPERUSERS:
        bot.answer_callback_query(call.id, "Unauthorized.")
        return
    try:
        bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=None,
        )
        bot.answer_callback_query(call.id, "Dismissed")
    except Exception as e:
        bot.answer_callback_query(call.id, f"Error: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("fp:"))
def handle_false_positive(call):
    """Mark as false positive — updates flag in DB but deletes nothing."""
    if not call.from_user.id in SUPERUSERS:
        bot.answer_callback_query(call.id, "Unauthorized.")
        return
    parts = call.data.split(":")
    new_uid, matched_uid = int(parts[1]), int(parts[2])
    db.mark_false_positive(new_uid, matched_uid)
    bot.edit_message_text(
        call.message.text + "\n\n--- FALSE POSITIVE marked by admin ---",
        call.message.chat.id,
        call.message.message_id,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_req:"))
def handle_approve_req(call):
    """Admin approves a pending flagged user from the log chat."""
    if not call.from_user.id in SUPERUSERS:
        bot.answer_callback_query(call.id, "Unauthorized.")
        return
    parts = call.data.split(":")
    chat_id, user_id, flag_id = int(parts[1]), int(parts[2]), int(parts[3])
    try:
        bot.approve_chat_join_request(chat_id, user_id)
    except Exception:
        pass  # May already be approved
    _unrestrict_user(chat_id, user_id)
    db.update_flag_action(flag_id, "approved")
    db.mark_pending_completed_by_user(user_id, chat_id)
    _update_log_message_status(call.message, "Approved ✅", chat_id, user_id)
    bot.answer_callback_query(call.id, "User approved ✅")
    logger.info("Admin approved flagged user %s in chat %s (flag %s)", user_id, chat_id, flag_id)


# ═══════════════════════════════════════════════════════════════════
#  FLASK ROUTES
# ═══════════════════════════════════════════════════════════════════

@app.route("/", methods=["GET"])
def serve_root():
    """Redirect the website root to the Telegram bot deep link."""
    return redirect("https://t.me/CrocodileGameEnn_bot", code=302)

@app.route('/support', methods=['GET'])
def serve_support():
    """Redirect to bot support group."""
    return redirect('https://t.me/CrocodileGamesGroup', code=302)

@app.route("/terms", methods=["GET"])
@app.route("/tnc", methods=["GET"])
@app.route("/rules", methods=["GET"])
def serve_terms_page():
    """Serve static Terms and Conditions page without WebApp logic."""
    return render_template("group_terms.html")

@app.route("/verify", methods=["GET"])
def serve_verify_page():
    """Serve the Mini Web App HTML."""
    token = request.args.get("token", "")
    if not token:
        return "Missing verification token.", 400

    pending = db.get_pending_request(token)
    if not pending:
        return "This verification link has expired or is invalid.", 404

    return render_template("verify.html", token=token, api_url=WEB_BASE_URL)


@app.route("/api/verify", methods=["POST"])
def receive_fingerprint():
    """Receive fingerprint data from the Mini Web App.

    Supports two actions:
      - action="load" (default): Collect fingerprint on page open, check for matches.
        If match found, send pending alert to admin log. Does NOT approve/decline.
      - action="accept": User clicked "Accept & Join". Approve/decline based on flag status.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400
    init_data_raw = data.get("initData", "")
    fingerprint_data = data.get("fingerprint", {})
    token = data.get("token", "")
    action = data.get("action", "load")  # "load" or "accept"
    # 1. Validate initData
    validated = validation.validate_init_data(init_data_raw)
    if validated is None:
        logger.warning("initData validation failed for token %s", token)
        return jsonify({"ok": False, "error": "Validation failed"}), 403
    # 2. Extract user_id
    tg_user_id = validation.extract_user_id(validated)
    if tg_user_id is None:
        return jsonify({"ok": False, "error": "No user ID in initData"}), 400
    # 3. Look up pending request
    pending = db.get_pending_request(token)
    if not pending:
        return jsonify({"ok": False, "error": "Token expired or invalid"}), 404
    # 4. Verify user_id matches
    if tg_user_id != pending["user_id"]:
        logger.warning(
            "User ID mismatch: initData=%s, pending=%s",
            tg_user_id, pending["user_id"],
        )
        return jsonify({"ok": False, "error": "User mismatch"}), 403
    chat_id = pending["chat_id"]
    user_id = pending["user_id"]
    # 5. Extract user's full name from initData
    user_full_name = ""
    try:
        user_info = json.loads(validated.get("user", "{}"))
        first = user_info.get("first_name", "")
        last = user_info.get("last_name", "")
        user_full_name = f"{first} {last}".strip() if last else first
    except (json.JSONDecodeError, TypeError):
        pass

    # ═══════════════════════════════════════════════════════════════
    #  ACTION: LOAD — fingerprint collection & matching on page open
    # ═══════════════════════════════════════════════════════════════
    if action == "load":
        # 6. Build fingerprint record with server-side IP
        client_ip, ip_info = request.headers.get("X-Forwarded-For", request.remote_addr), None
        if client_ip:
            client_ip = client_ip.split(",")[0].strip() if "," in client_ip else client_ip
            ip_info = fp_module.fetch_ip_geolocation(client_ip) # Fetch IP geolocation data
        fp_record = {
            "user_id": user_id,
            "full_name": user_full_name,
            "device_id": fingerprint_data.get("deviceId", ""),
            "canvas_hash": fingerprint_data.get("canvasHash", ""),
            "webgl_hash": fingerprint_data.get("webglHash", ""),
            "audio_hash": fingerprint_data.get("audioHash", ""),
            "ip_address": client_ip,
            "screen_resolution": fingerprint_data.get("screenResolution", ""),
            "user_agent": request.headers.get("User-Agent", ""),
            "platform": fingerprint_data.get("platform", ""),
            "languages": json.dumps(fingerprint_data.get("languages", [])),
            "timezone": fingerprint_data.get("timezone", ""),
            "timezone_offset": fingerprint_data.get("timezoneOffset", 0),
            "touch_points": fingerprint_data.get("touchPoints", 0),
            "device_memory": fingerprint_data.get("deviceMemory"),
            "hardware_concurrency": fingerprint_data.get("hardwareConcurrency"),
            "fonts_hash": fingerprint_data.get("fontsHash", ""),
            "raw_data": json.dumps(fingerprint_data),
            "ip_info": json.dumps(ip_info) if ip_info else None,
        }

        # ── STEP 0: Check if user is already linked (permanent link) ──
        existing_link = db.find_existing_link(user_id)
        if existing_link:
            db.upsert_fingerprint(user_id, fp_record)
            logger.info("User %s has existing link, fingerprint updated on load", user_id)
            return jsonify({"ok": True, "status": "linked"})

        # ── STEP 1: Fast-path #1 — device_id (same Telegram app) ─────
        device_id_match = fp_module.check_device_id_match(fp_record["device_id"], user_id, db)
        if device_id_match:
            matched_user_id = device_id_match["user_id"]
            matched_name = db.get_user_name(matched_user_id) or ""
            db.upsert_fingerprint(user_id, fp_record)
            # Check for existing pending flag to avoid duplicate alerts
            existing_flag = db.get_latest_flag(user_id, chat_id)
            if not existing_flag or existing_flag.get("action_taken") not in ("pending", "flagged"):
                flag_id = db.record_flag(user_id, matched_user_id, 1.0, ["device_id"], "pending", chat_id,
                    new_user_name=user_full_name, matched_user_name=matched_name)
                _handle_flag_result(chat_id, user_id, matched_user_id, 1.0, ["device_id"],
                                    flag_id=flag_id,
                                    new_user_name=user_full_name, matched_user_name=matched_name)
            return jsonify({"ok": True, "status": "flagged"})

        # ── STEP 2: Fast-path #2 — ip_address (same network) ─────────
        ip_match = fp_module.check_ip_match(fp_record["ip_address"], user_id, db)
        if ip_match:
            matched_user_id = ip_match["user_id"]
            matched_name = db.get_user_name(matched_user_id) or ""
            db.upsert_fingerprint(user_id, fp_record)
            existing_flag = db.get_latest_flag(user_id, chat_id)
            if not existing_flag or existing_flag.get("action_taken") not in ("pending", "flagged"):
                flag_id = db.record_flag(user_id, matched_user_id, 1.0, ["ip_address"], "pending", chat_id,
                    new_user_name=user_full_name, matched_user_name=matched_name)
                _handle_flag_result(chat_id, user_id, matched_user_id, 1.0, ["ip_address"],
                                    flag_id=flag_id,
                                    new_user_name=user_full_name, matched_user_name=matched_name)
            return jsonify({"ok": True, "status": "flagged"})

        # ── STEP 3: Full weighted comparison ──────────────────────
        all_existing = db.get_all_fingerprints_except(user_id)
        match_result = fp_module.find_matching_user(fp_record, all_existing)
        db.upsert_fingerprint(user_id, fp_record)
        if match_result:
            matched_fp, score, components = match_result
            matched_user_id = matched_fp["user_id"]
            matched_name = db.get_user_name(matched_user_id) or ""
            existing_flag = db.get_latest_flag(user_id, chat_id)
            if not existing_flag or existing_flag.get("action_taken") not in ("pending", "flagged"):
                flag_id = db.record_flag(user_id, matched_user_id, score, components, "pending", chat_id,
                    new_user_name=user_full_name, matched_user_name=matched_name)
                _handle_flag_result(chat_id, user_id, matched_user_id, score, components,
                                    flag_id=flag_id,
                                    new_user_name=user_full_name, matched_user_name=matched_name)
            return jsonify({"ok": True, "status": "flagged"})
        else:
            # No match — ready for approval on accept
            logger.info("No match for user %s in chat %s on load", user_id, chat_id)
            return jsonify({"ok": True, "status": "clean"})

    # ═══════════════════════════════════════════════════════════════
    #  ACTION: ACCEPT — user clicked "Accept & Join"
    # ═══════════════════════════════════════════════════════════════
    elif action == "accept":
        # Check if user was flagged during load
        flag = db.get_latest_flag(user_id, chat_id)
        if flag and flag.get("action_taken") == "pending":
            if AUTO_DECLINE_ON_MATCH:
                try:
                    bot.decline_chat_join_request(chat_id, user_id)
                except Exception:
                    logger.exception("Failed to decline user %s", user_id)
                db.update_flag_action(flag["id"], "declined")
                # Update the log message status
                if flag.get("log_message_id") and LOG_CHAT_ID:
                    try:
                        fake_msg = SimpleNamespace(
                            chat=SimpleNamespace(id=LOG_CHAT_ID),
                            message_id=flag["log_message_id"],
                        )
                        _update_log_message_status(fake_msg, "DECLINED ❌", chat_id, user_id)
                    except Exception:
                        logger.exception("Failed to update log message on decline")
                db.mark_pending_completed(token)
                return jsonify({"ok": True, "status": "flagged"})
            else:
                # Flag-only mode: approve but keep flag active for admin review
                db.update_flag_action(flag["id"], "approved")
                db.mark_pending_completed(token)
                try:
                    bot.approve_chat_join_request(chat_id, user_id)
                except Exception:
                    pass
                _unrestrict_user(chat_id, user_id)
                # Update the log message status
                if flag.get("log_message_id") and LOG_CHAT_ID:
                    try:
                        fake_msg = SimpleNamespace(
                            chat=SimpleNamespace(id=LOG_CHAT_ID),
                            message_id=flag["log_message_id"],
                        )
                        _update_log_message_status(fake_msg, "Approved ✅", chat_id, user_id)
                    except Exception:
                        logger.exception("Failed to update log message on approve")
                logger.info("Approved flagged user %s for chat %s", user_id, chat_id)
                return jsonify({"ok": True, "status": "approved"})

        # Check for existing link (permanent link — silently approve)
        existing_link = db.find_existing_link(user_id)
        if existing_link:
            db.mark_pending_completed(token)
            try:
                bot.approve_chat_join_request(chat_id, user_id)
            except Exception:
                pass
            _unrestrict_user(chat_id, user_id)
            matched_user_id = (
                existing_link["matched_user_id"]
                if existing_link["new_user_id"] == user_id
                else existing_link["new_user_id"]
            )
            logger.info(
                "User %s re-joined (permanently linked to %s), auto-approved silently",
                user_id, matched_user_id,
            )
            return jsonify({"ok": True, "status": "approved"})

        # No flag — clean user, approve normally
        db.mark_pending_completed(token)
        try:
            bot.approve_chat_join_request(chat_id, user_id)
        except Exception:
            pass  # May already be approved (restricted flow)
        _unrestrict_user(chat_id, user_id)
        logger.info("Approved user %s for chat %s", user_id, chat_id)
        return jsonify({"ok": True, "status": "approved"})

    else:
        return jsonify({"ok": False, "error": "Invalid action"}), 400




# ═══════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════

def _unrestrict_user(chat_id: int, user_id: int):
    """Remove restrictions from a previously muted user."""
    try:
        bot.restrict_chat_member(
            chat_id,
            user_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_send_polls=True,
                can_invite_users=True,
                can_edit_tag=True,
                can_pin_messages=True,
                can_change_info=True,
            ),
        )
    except Exception:
        logger.warning('Could not unrestrict user %s in chat %s', user_id, chat_id)


def _handle_flag_result(
    chat_id: int,
    new_user_id: int,
    matched_user_id: int,
    score: float,
    components: list,
    flag_id: int,
    new_user_name: str = "",
    matched_user_name: str = "",
):
    """Handle a multi-account match on page load: send pending alert to admins.
    Does NOT approve/decline the user — that happens on accept or admin action."""
    _notify_admin(chat_id, new_user_id, matched_user_id, score, components,
                  flag_id=flag_id,
                  new_user_name=new_user_name, matched_user_name=matched_user_name)



def _build_alert_text(
    chat_id: int,
    new_user_id: int,
    matched_user_id: int,
    score: float,
    components: list,
    status_text: str,
    new_user_name: str = '',
    matched_user_name: str = '',
) -> str:
    """Build the alert text for admin notifications."""
    new_label = f'<a href="tg://openmessage?user_id={new_user_id}">{escape(new_user_name) if new_user_name else f"[id: {new_user_id}]"}</a>'
    matched_label = f'<a href="tg://openmessage?user_id={matched_user_id}">{escape(matched_user_name) if matched_user_name else f"[id: {matched_user_id}]"}</a>'
    # Show total linked accounts if this is part of a larger cluster
    connected = db.get_all_connected_users(new_user_id)
    cluster_info = ''
    if len(connected) > 2:
        cluster_labels = []
        for uid in sorted(connected):
            name = escape(db.get_user_name(uid) or f'[id: {str(uid)}]')
            cluster_labels.append(f'<a href="tg://openmessage?user_id={uid}">{name}</a>')
        cluster_info = (
            f'\n<b>Cluster:</b> {len(connected)} linked accounts'
            f'\n<blockquote expandable>{"  <b>┃</b>".join(cluster_labels)}</blockquote>'
        )
    return (
        '⚠️ <b>MULTI-ACCOUNT DETECTED</b> ⚠️\n'
        f'{"       " * 5}\n'
        f'<b>Status:</b> {status_text}\n\n'
        f'<b>New user:</b> {new_label}\n'
        f'<b>Matches:</b> {matched_label}\n'
        f'<b>Similarity:</b> <code>{score:.0%}</code>\n'
        f'<b>Signals:</b> <i>{", ".join(components)}</i>\n'
        f'<b>Group:</b> <code>{chat_id}</code>\n'
        f'{cluster_info}'
    )


def _build_pending_markup(
    chat_id: int,
    new_user_id: int,
    matched_user_id: int,
    flag_id: int,
) -> InlineKeyboardMarkup:
    """Build inline keyboard for PENDING status: Approve, Dismiss + Ban/FP buttons."""
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton(
            "✅ Approve User",
            callback_data=f"approve_req:{chat_id}:{new_user_id}:{flag_id}",
        ),
        InlineKeyboardButton(
            "Dismiss",
            callback_data=f"dismiss_req:{chat_id}:{new_user_id}:{flag_id}",
        ),
    )
    markup.row(
        InlineKeyboardButton(
            "Ban New User",
            callback_data=f"ban:{chat_id}:{new_user_id}",
        ),
        InlineKeyboardButton(
            "Ban Both",
            callback_data=f"banboth:{chat_id}:{new_user_id}:{matched_user_id}",
        ),
    )
    markup.row(
        InlineKeyboardButton(
            "False Positive",
            callback_data=f"fp:{new_user_id}:{matched_user_id}",
        ),
    )
    return markup


def _build_post_action_markup(
    chat_id: int,
    new_user_id: int,
    matched_user_id: int,
) -> InlineKeyboardMarkup:
    """Build inline keyboard after approval/join: Ban + FP buttons only (no Approve/Dismiss)."""
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton(
            "Ban New User",
            callback_data=f"ban:{chat_id}:{new_user_id}",
        ),
        InlineKeyboardButton(
            "Ban Both",
            callback_data=f"banboth:{chat_id}:{new_user_id}:{matched_user_id}",
        ),
    )
    markup.row(
        InlineKeyboardButton(
            "Dismiss",
            callback_data=f"dismiss:{new_user_id}:{matched_user_id}",
        ),
        InlineKeyboardButton(
            "False Positive",
            callback_data=f"fp:{new_user_id}:{matched_user_id}",
        ),
    )
    return markup


def _notify_admin(
    chat_id: int,
    new_user_id: int,
    matched_user_id: int,
    score: float,
    components: list,
    flag_id: int,
    new_user_name: str = '',
    matched_user_name: str = '',
) -> None:
    """Send pending alert to log chat with Approve/Dismiss + Ban/FP buttons.
    Stores the sent message ID in the flag record for later updates."""
    if not LOG_CHAT_ID:
        return
    status_text = 'Pending ⏳ <i>(awaiting user acceptance)</i>'
    alert_text = _build_alert_text(
        chat_id, new_user_id, matched_user_id, score, components,
        status_text, new_user_name, matched_user_name,
    )
    markup = _build_pending_markup(chat_id, new_user_id, matched_user_id, flag_id)
    try:
        sent = bot.send_message(
            LOG_CHAT_ID, alert_text, parse_mode='HTML', reply_markup=markup,
            message_thread_id=(LOG_THREAD_ID if LOG_THREAD_ID != 0 else None),
        )
        db.update_flag_log_message_id(flag_id, sent.message_id)
    except Exception:
        logger.exception("Failed to notify admin about flag")


def _update_log_message_status(
    message,
    new_status: str,
    chat_id: int,
    new_user_id: int,
):
    """Update an existing admin log message: change status text and swap buttons."""
    try:
        # Get flag details to reconstruct message with new status
        flag = db.get_latest_flag(new_user_id, chat_id)
        if not flag:
            return
        matched_user_id = (
            flag["matched_user_id"]
            if flag["new_user_id"] == new_user_id
            else flag["new_user_id"]
        )
        components = json.loads(flag["matching_components"]) if isinstance(flag["matching_components"], str) else flag["matching_components"]
        new_user_name = flag.get("new_user_name") or db.get_user_name(flag["new_user_id"]) or ""
        matched_user_name = flag.get("matched_user_name") or db.get_user_name(flag["matched_user_id"]) or ""
        alert_text = _build_alert_text(
            chat_id, flag["new_user_id"], matched_user_id,
            flag["similarity_score"], components, new_status,
            new_user_name, matched_user_name,
        )
        markup = _build_post_action_markup(chat_id, flag["new_user_id"], matched_user_id)
        bot.edit_message_text(
            alert_text, message.chat.id, message.message_id,
            reply_markup=markup, parse_mode='HTML',
        )
    except Exception:
        logger.exception("Failed to update log message status")



# ═══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def run_flask():
    app.run(host=WEB_HOST, port=WEB_PORT, debug=False)


if __name__ == "__main__":
    db.init_db()
    logger.info("Database initialized")

    # Expire any stale pending requests
    expired = db.expire_stale_requests()
    if expired:
        logger.info("Expired %d stale pending requests", expired)

    # Start Flask in background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask server started on %s:%s", WEB_HOST, WEB_PORT)

    # Start bot polling on main thread
    me = bot.get_me()
    BOT_ID, BOT_USERNAME = me.id, me.username.removeprefix("@")
    logger.info("[PROD] Started bot as @%s (%s)", BOT_USERNAME, BOT_ID)
    bot.infinity_polling(
        timeout=60,
        long_polling_timeout=60,
        allowed_updates=[
            "message",
            "callback_query",
            "chat_join_request",
            "chat_member",
        ],
    )

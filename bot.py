import json
import uuid
import threading
import logging
from time import sleep
from datetime import datetime, timedelta

import telebot
from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    ChatPermissions,
)
from flask import Flask, request, render_template, jsonify

from config import *
import database
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

bot = telebot.TeleBot(BOT_TOKEN, allow_sending_without_reply=True)
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
    if message.chat.type != "private":
        return
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "there"
    # Check for any restricted (un-verified) pending requests
    restricted = database.get_restricted_requests(user_id)
    if restricted:
        for req in restricted:
            token = uuid.uuid4().hex
            expires_at = (datetime.utcnow() + timedelta(minutes=PENDING_REQUEST_TTL_MINUTES)).isoformat()
            database.update_pending_token(req["id"], token, expires_at)
            verify_url = f"{WEB_BASE_URL}/verify?token={token}"
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton(
                text="\U0001f513 Verify to Access Chat",
                web_app=WebAppInfo(url=verify_url),
            ))
            markup.add(InlineKeyboardButton(
                text="🔙 Return to Group",
                url=f"https://t.me/CrocodileGamesGroup",
            ))
            bot.send_message(
                user_id,
                f"Hi {first_name}!\nYou joined Crocodile Games group but haven't verified yet. "
                "Complete verification to get access (send messages, stickers, etc.) to the group.",
                reply_markup=markup,
            )
        return
    bot.send_message(user_id, f"Hi {first_name}!\nI'm a verification bot built by Crocodile Games (@CrocodileGames).")


@bot.message_handler(commands=["multis"])
def handle_multis(message):
    """Show how many users have multiple accounts."""
    if not message.from_user.id in SUPERUSERS:
        return
    clusters = database.get_all_multi_account_clusters()
    if not clusters:
        bot.reply_to(message, "No multi-account users detected yet.")
        return
    total_accounts = sum(len(c) for c in clusters)
    lines = [
        f"Multi-account clusters: {len(clusters)}",
        f"Total accounts involved: {total_accounts}",
        "",
    ]
    for i, cluster in enumerate(sorted(clusters, key=len, reverse=True), 1):
        user_labels = []
        for uid in sorted(cluster):
            name = database.get_user_name(uid)
            user_labels.append(f"{name} ({uid})" if name else str(uid))
        lines.append(f"{i}. [{len(cluster)} accounts] {', '.join(user_labels)}")
    bot.reply_to(message, "\n".join(lines))


@bot.message_handler(commands=["connections"])
def handle_connections(message):
    """Show all connections for a specific user: /connections <user_id>"""
    if not message.from_user.id in SUPERUSERS:
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /connections <user_id>")
        return
    try:
        target_uid = int(parts[1])
    except ValueError:
        bot.reply_to(message, "Invalid user ID. Must be a number.")
        return
    connected = database.get_all_connected_users(target_uid)
    if len(connected) <= 1:
        bot.reply_to(message, f"User {target_uid} has no linked accounts.")
        return
    details = database.get_connection_details(target_uid)
    connected_labels = []
    for uid in sorted(connected):
        name = database.get_user_name(uid)
        connected_labels.append(f"{name} ({uid})" if name else str(uid))
    target_name = database.get_user_name(target_uid)
    target_label = f"{target_name} ({target_uid})" if target_name else str(target_uid)
    lines = [
        f"Connections for {target_label}",
        f"Linked accounts ({len(connected)}): {', '.join(connected_labels)}",
        "",
        "Detection history:",
    ]
    for flag in details:
        status = flag["action_taken"]
        score = flag["similarity_score"]
        components = flag["matching_components"]
        ts = flag["created_at"]
        new_name = flag.get("new_user_name") or database.get_user_name(flag["new_user_id"]) or ""
        matched_name = flag.get("matched_user_name") or database.get_user_name(flag["matched_user_id"]) or ""
        new_lbl = f"{new_name} ({flag['new_user_id']})" if new_name else str(flag["new_user_id"])
        matched_lbl = f"{matched_name} ({flag['matched_user_id']})" if matched_name else str(flag["matched_user_id"])
        lines.append(
            f"  {new_lbl} <-> {matched_lbl} "
            f"| {score:.0%} | {components} | {status} | {ts}"
        )
    bot.reply_to(message, "\n".join(lines))


@bot.chat_join_request_handler()
def handle_join_request(jr):
    """
    Triggered when a user requests to join a group where the bot is admin
    with 'Approve new members' permission.
    """
    chat_id = jr.chat.id
    user_id = jr.from_user.id
    full_name = jr.from_user.first_name + (" " + jr.from_user.last_name if jr.from_user.last_name else "")
    if ALLOWED_GROUPS and chat_id not in ALLOWED_GROUPS:
        logger.debug("Ignoring join request from non-allowed group %s", chat_id)
        return
    if user_id in SUPERUSERS:
        # Auto-approve superusers without DM
        try:
            bot.approve_chat_join_request(chat_id, user_id)
            logger.info("Auto-approved superuser %s for chat %s", user_id, chat_id)
        except Exception:
            logger.exception("Failed to approve superuser %s", user_id)
        return
    token = uuid.uuid4().hex
    expires_at = (
        datetime.utcnow()
        + timedelta(minutes=PENDING_REQUEST_TTL_MINUTES)
    ).isoformat()
    try:
        # Try to DM the user with a verification link
        verify_url = f"{WEB_BASE_URL}/verify?token={token}"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(
            text="\U0001f513 I'm not a robot",
            web_app=WebAppInfo(url=verify_url),
        ))
        markup.add(InlineKeyboardButton(
            text="🔙 Return to Group",
            url=f"https://t.me/CrocodileGamesGroup",
        ))
        bot.send_message(user_id, f"Hi {full_name}! To join the group (@CrocodileGamesGroup), please verify you are not a robot by accepting the terms (rules).",
                        reply_markup=markup)
        # DM succeeded — store as normal pending request
        database.create_pending_request(
            chat_id=chat_id,
            user_id=user_id,
            user_name=full_name,
            token=token,
            expires_at=expires_at,
            status="pending",
        )
        logger.info("Sent verification DM to user %s for chat %s", user_id, chat_id)
    except telebot.apihelper.ApiTelegramException as e:
        err_msg = str(e).lower()
        if "bot can't initiate conversation" in err_msg or "chat not found" in err_msg or "forbidden" in err_msg:
            # User never started the bot — approve but restrict (mute)
            logger.warning(
                "Cannot DM user %s — approving with restrictions", user_id
            )
            try:
                bot.approve_chat_join_request(chat_id, user_id)
                bot.restrict_chat_member(
                    chat_id,
                    user_id,
                    permissions=ChatPermissions(
                        can_send_messages=False,
                        can_send_media_messages=False,
                        can_send_other_messages=False,
                        can_add_web_page_previews=False,
                    ),
                )
                # Store as restricted — no token yet, will be assigned on /start
                database.create_pending_request(
                    chat_id=chat_id,
                    user_id=user_id,
                    user_name=full_name,
                    token=None,
                    expires_at=None,
                    status="restricted",
                )
                sleep(1)
                # Send message in the group with mention to user prompting to complete verification
                markup = InlineKeyboardMarkup([[InlineKeyboardButton(
                        text="\U0001f513 Verify",
                        url=f"https://t.me/{BOT_USERNAME}?start=verifyInChat{chat_id}_{user_id}",
                )]])
                full_name = full_name if len(full_name) <= 25 else full_name[:22] + "..."
                bot.send_message(chat_id, f'Hi {full_name}!\nTo access this chat, please DM me to verify you are not a robot by accepting the terms (rules).',
                                 reply_markup=markup)
            except Exception:
                logger.exception("Failed to approve/restrict user %s in chat %s", user_id, chat_id)
        else:
            logger.exception("Telegram API error for join request user %s", user_id)
    except Exception:
        logger.exception("Unexpected error handling join request for user %s", user_id)


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


@bot.callback_query_handler(func=lambda call: call.data.startswith("dismiss:"))
def handle_dismiss(call):
    if not call.from_user.id in SUPERUSERS:
        bot.answer_callback_query(call.id, "Unauthorized.")
        return
    parts = call.data.split(":")
    new_uid, matched_uid = parts[1], parts[2]
    bot.edit_message_text(
        call.message.text + "\n\n--- DISMISSED by admin ---",
        call.message.chat.id,
        call.message.message_id,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("fp:"))
def handle_false_positive(call):
    """Mark as false positive — updates flag in DB but deletes nothing."""
    if not call.from_user.id in SUPERUSERS:
        bot.answer_callback_query(call.id, "Unauthorized.")
        return
    parts = call.data.split(":")
    new_uid, matched_uid = int(parts[1]), int(parts[2])
    database.mark_false_positive(new_uid, matched_uid)
    bot.edit_message_text(
        call.message.text + "\n\n--- FALSE POSITIVE marked by admin ---",
        call.message.chat.id,
        call.message.message_id,
    )


# ═══════════════════════════════════════════════════════════════════
#  FLASK ROUTES
# ═══════════════════════════════════════════════════════════════════

@app.route("/verify", methods=["GET"])
def serve_verify_page():
    """Serve the Mini Web App HTML."""
    token = request.args.get("token", "")
    if not token:
        return "Missing verification token.", 400

    pending = database.get_pending_request(token)
    if not pending:
        return "This verification link has expired or is invalid.", 404

    return render_template("verify.html", token=token, api_url=WEB_BASE_URL)


@app.route("/api/verify", methods=["POST"])
def receive_fingerprint():
    """Receive fingerprint data from the Mini Web App."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    init_data_raw = data.get("initData", "")
    fingerprint_data = data.get("fingerprint", {})
    token = data.get("token", "")

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
    pending = database.get_pending_request(token)
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

    # 6. Build fingerprint record with server-side IP
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if client_ip and "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()

    fp_record = {
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
    }

    # ── STEP 0: Check if user is already linked (permanent link) ──
    # Once flagged, always flagged — regardless of current fingerprint.
    existing_link = database.find_existing_link(user_id)
    if existing_link:
        # Determine the other user in this link
        matched_user_id = (
            existing_link["matched_user_id"]
            if existing_link["new_user_id"] == user_id
            else existing_link["new_user_id"]
        )
        database.upsert_fingerprint(user_id, fp_record)
        database.mark_pending_completed(token)
        # Silently approve — no alert for known linked accounts re-joining
        try:
            bot.approve_chat_join_request(chat_id, user_id)
        except Exception:
            pass
        _unrestrict_user(chat_id, user_id)
        logger.info(
            "User %s re-joined (permanently linked to %s), auto-approved silently",
            user_id, matched_user_id,
        )
        return jsonify({"ok": True, "status": "approved"})

    # ── STEP 1: Fast-path #1 — device_id (same Telegram app) ─────
    device_id_match = fp_module.check_device_id_match(
        fp_record["device_id"], user_id, database
    )

    if device_id_match:
        matched_user_id = device_id_match["user_id"]
        matched_name = database.get_user_name(matched_user_id) or ""
        database.upsert_fingerprint(user_id, fp_record)
        database.record_flag(
            user_id, matched_user_id, 1.0, ["device_id"], "flagged", chat_id,
            new_user_name=user_full_name, matched_user_name=matched_name,
        )
        database.mark_pending_completed(token)
        _handle_flag_result(chat_id, user_id, matched_user_id, 1.0, ["device_id"],
                            new_user_name=user_full_name, matched_user_name=matched_name)
        return jsonify({"ok": True, "status": "flagged"})

    # ── STEP 2: Fast-path #2 — ip_address (same network) ─────────
    ip_match = fp_module.check_ip_match(
        fp_record["ip_address"], user_id, database
    )

    if ip_match:
        matched_user_id = ip_match["user_id"]
        matched_name = database.get_user_name(matched_user_id) or ""
        database.upsert_fingerprint(user_id, fp_record)
        database.record_flag(
            user_id, matched_user_id, 1.0, ["ip_address"], "flagged", chat_id,
            new_user_name=user_full_name, matched_user_name=matched_name,
        )
        database.mark_pending_completed(token)
        _handle_flag_result(chat_id, user_id, matched_user_id, 1.0, ["ip_address"],
                            new_user_name=user_full_name, matched_user_name=matched_name)
        return jsonify({"ok": True, "status": "flagged"})

    # ── STEP 3: Full weighted comparison ──────────────────────────
    all_existing = database.get_all_fingerprints_except(user_id)
    match_result = fp_module.find_matching_user(fp_record, all_existing)

    # Store fingerprint regardless
    database.upsert_fingerprint(user_id, fp_record)
    database.mark_pending_completed(token)

    if match_result:
        matched_fp, score, components = match_result
        matched_user_id = matched_fp["user_id"]
        matched_name = database.get_user_name(matched_user_id) or ""
        action = "declined" if AUTO_DECLINE_ON_MATCH else "flagged"
        database.record_flag(
            user_id, matched_user_id, score, components, action, chat_id,
            new_user_name=user_full_name, matched_user_name=matched_name,
        )
        _handle_flag_result(chat_id, user_id, matched_user_id, score, components,
                            new_user_name=user_full_name, matched_user_name=matched_name)
        return jsonify({"ok": True, "status": "flagged"})
    else:
        # No match — approve and unrestrict if needed
        try:
            bot.approve_chat_join_request(chat_id, user_id)
        except Exception:
            pass  # May already be approved (restricted flow)
        _unrestrict_user(chat_id, user_id)
        logger.info("Approved user %s for chat %s", user_id, chat_id)
        return jsonify({"ok": True, "status": "approved"})


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
                can_pin_messages=False,
                can_change_info=False,
            ),
        )
    except Exception:
        logger.warning(
            "Could not unrestrict user %s in chat %s",
            user_id, chat_id,
        )


def _handle_flag_result(
    chat_id: int,
    new_user_id: int,
    matched_user_id: int,
    score: float,
    components: list,
    new_user_name: str = "",
    matched_user_name: str = "",
):
    """Handle a multi-account match: decide action + notify admin."""
    if AUTO_DECLINE_ON_MATCH:
        try:
            bot.decline_chat_join_request(chat_id, new_user_id)
            logger.info(
                "Auto-declined user %s (matched %s, score %.2f)",
                new_user_id, matched_user_id, score,
            )
        except Exception:
            logger.exception("Failed to decline user %s", new_user_id)
    else:
        # Flag-only: approve but notify admin
        try:
            bot.approve_chat_join_request(chat_id, new_user_id)
        except Exception:
            pass  # May already be approved
        _unrestrict_user(chat_id, new_user_id)

    _notify_admin(chat_id, new_user_id, matched_user_id, score, components,
                  new_user_name=new_user_name, matched_user_name=matched_user_name)


def _notify_admin(
    chat_id: int,
    new_user_id: int,
    matched_user_id: int,
    score: float,
    components: list,
    new_user_name: str = "",
    matched_user_name: str = "",
):
    """Send alert to log chat with inline action buttons."""
    if not LOG_CHAT_ID:
        return
    action_word = (
        "DECLINED" if AUTO_DECLINE_ON_MATCH
        else "Approved (pending review)"
    )
    components_str = ", ".join(components)
    new_label = f"{new_user_name} ({new_user_id})" if new_user_name else str(new_user_id)
    matched_label = f"{matched_user_name} ({matched_user_id})" if matched_user_name else str(matched_user_id)
    # Show total linked accounts if this is part of a larger cluster
    connected = database.get_all_connected_users(new_user_id)
    cluster_info = ""
    if len(connected) > 2:
        cluster_labels = []
        for uid in sorted(connected):
            name = database.get_user_name(uid)
            cluster_labels.append(f"{name} ({uid})" if name else str(uid))
        cluster_info = (
            f"\nCluster: {len(connected)} linked accounts total"
            f"\nAll: {', '.join(cluster_labels)}"
        )
    alert_text = (
        "\U000026a0\U0000fe0f MULTI-ACCOUNT DETECTED\n"
        f"{'=' * 32}\n"
        f"Status: {action_word}\n\n"
        f"New user: {new_label}\n"
        f"Matches: {matched_label}\n"
        f"Similarity: {score:.0%}\n"
        f"Signals: {components_str}\n"
        f"Group: {chat_id}\n"
        f"{cluster_info}"
    )
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
    try:
        bot.send_message(LOG_CHAT_ID, alert_text, reply_markup=markup, message_thread_id=(LOG_THREAD_ID if LOG_THREAD_ID != 0 else None))
    except Exception:
        logger.exception("Failed to notify admin about flag")


# ═══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def run_flask():
    app.run(host=WEB_HOST, port=WEB_PORT, debug=False)


if __name__ == "__main__":
    database.init_db()
    logger.info("Database initialized")

    # Expire any stale pending requests
    expired = database.expire_stale_requests()
    if expired:
        logger.info("Expired %d stale pending requests", expired)

    # Start Flask in background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask server started on %s:%s", WEB_HOST, WEB_PORT)

    # Start bot polling on main thread
    BOT_USERNAME = bot.get_me().username.removeprefix("@")
    logger.info("Started bot as @%s", BOT_USERNAME)
    bot.infinity_polling(
        timeout=60,
        long_polling_timeout=60,
        allowed_updates=[
            "message",
            "callback_query",
            "chat_join_request",
        ],
    )

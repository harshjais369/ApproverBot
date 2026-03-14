import json
import uuid
import threading
import logging
from datetime import datetime, timedelta

import telebot
from telebot.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    ChatPermissions,
)
from flask import Flask, request, render_template, jsonify

import config
import database
import fingerprint as fp_module
import validation

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("approverbot")

bot = telebot.TeleBot(config.BOT_TOKEN)
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
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "there"

    # Check for any restricted (un-verified) pending requests
    restricted = database.get_restricted_requests(user_id)
    if restricted:
        for req in restricted:
            token = uuid.uuid4().hex
            expires_at = (
                datetime.utcnow()
                + timedelta(minutes=config.PENDING_REQUEST_TTL_MINUTES)
            ).isoformat()
            database.update_pending_token(req["id"], token, expires_at)

            verify_url = f"{config.WEB_BASE_URL}/verify?token={token}"
            markup = InlineKeyboardMarkup()
            markup.add(
                InlineKeyboardButton(
                    text="\U0001f513 Verify to Get Full Access",
                    web_app=WebAppInfo(url=verify_url),
                )
            )
            bot.send_message(
                user_id,
                f"Hi {first_name}! You joined a group but haven't verified yet. "
                "Complete verification to get full access (send messages, media, etc.).",
                reply_markup=markup,
            )
        return

    bot.send_message(
        user_id,
        f"Hi {first_name}! I'm the group verification bot.\n\n"
        "When you request to join a group I protect, I'll send you a "
        "quick verification link here.",
    )


@bot.chat_join_request_handler()
def handle_join_request(join_request):
    """
    Triggered when a user requests to join a group where the bot is admin
    with 'Approve new members' permission.
    """
    chat_id = join_request.chat.id
    user_id = join_request.from_user.id
    first_name = join_request.from_user.first_name or "there"

    token = uuid.uuid4().hex
    expires_at = (
        datetime.utcnow()
        + timedelta(minutes=config.PENDING_REQUEST_TTL_MINUTES)
    ).isoformat()

    try:
        # Try to DM the user with a verification link
        verify_url = f"{config.WEB_BASE_URL}/verify?token={token}"
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton(
                text="\U0001f513 Verify to Join",
                web_app=WebAppInfo(url=verify_url),
            )
        )

        bot.send_message(
            user_id,
            f"Hi {first_name}! To join the group, please complete a quick verification.",
            reply_markup=markup,
        )

        # DM succeeded — store as normal pending request
        database.create_pending_request(
            chat_id=chat_id,
            user_id=user_id,
            token=token,
            expires_at=expires_at,
            status="pending",
        )
        logger.info(
            "Sent verification DM to user %s for chat %s", user_id, chat_id
        )

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
                    token=None,
                    expires_at=None,
                    status="restricted",
                )
            except Exception:
                logger.exception(
                    "Failed to approve/restrict user %s in chat %s",
                    user_id, chat_id,
                )
        else:
            logger.exception(
                "Telegram API error for join request user %s", user_id
            )

    except Exception:
        logger.exception(
            "Unexpected error handling join request for user %s", user_id
        )


# ── Admin callback handlers ───────────────────────────────────────

@bot.callback_query_handler(func=lambda call: call.data.startswith("ban:"))
def handle_ban(call):
    parts = call.data.split(":")
    chat_id, user_id = int(parts[1]), int(parts[2])
    try:
        bot.ban_chat_member(chat_id, user_id)
        bot.answer_callback_query(call.id, f"User {user_id} banned.")
        bot.edit_message_text(
            call.message.text + f"\n\n--- User {user_id} BANNED by admin ---",
            call.message.chat.id,
            call.message.message_id,
        )
    except Exception as e:
        bot.answer_callback_query(call.id, f"Error: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("banboth:"))
def handle_ban_both(call):
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
    else:
        bot.answer_callback_query(call.id, "Both users banned.")
    bot.edit_message_text(
        call.message.text + f"\n\n--- Users {user1} & {user2} BANNED by admin ---",
        call.message.chat.id,
        call.message.message_id,
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("dismiss:"))
def handle_dismiss(call):
    bot.answer_callback_query(call.id, "Dismissed.")
    bot.edit_message_text(
        call.message.text + "\n\n--- DISMISSED by admin ---",
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

    return render_template("verify.html", token=token, api_url=config.WEB_BASE_URL)


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

    # 5. Build fingerprint record with server-side IP
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if client_ip and "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()

    fp_record = {
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

    # 6. Fast-path: check device_id
    device_id_match = fp_module.check_device_id_match(
        fp_record["device_id"], user_id, database
    )

    if device_id_match:
        matched_user_id = device_id_match["user_id"]
        database.upsert_fingerprint(user_id, fp_record)
        database.record_flag(
            user_id, matched_user_id, 1.0, ["device_id"], "flagged", chat_id
        )
        database.mark_pending_completed(token)
        _handle_flag_result(chat_id, user_id, matched_user_id, 1.0, ["device_id"])
        return jsonify({"ok": True, "status": "flagged"})

    # 7. Full comparison
    all_existing = database.get_all_fingerprints_except(user_id)
    match_result = fp_module.find_matching_user(fp_record, all_existing)

    # 8. Store fingerprint
    database.upsert_fingerprint(user_id, fp_record)
    database.mark_pending_completed(token)

    if match_result:
        matched_fp, score, components = match_result
        matched_user_id = matched_fp["user_id"]
        action = "declined" if config.AUTO_DECLINE_ON_MATCH else "flagged"
        database.record_flag(
            user_id, matched_user_id, score, components, action, chat_id
        )
        _handle_flag_result(chat_id, user_id, matched_user_id, score, components)
        return jsonify({"ok": True, "status": "flagged"})
    else:
        # No match — approve and unrestrict if needed
        try:
            bot.approve_chat_join_request(chat_id, user_id)
        except Exception:
            # May already be approved (restricted flow)
            pass
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
        logger.debug(
            "Could not unrestrict user %s in chat %s (may not be restricted)",
            user_id, chat_id,
        )


def _handle_flag_result(
    chat_id: int,
    new_user_id: int,
    matched_user_id: int,
    score: float,
    components: list,
):
    """Handle a multi-account match: decide action + notify admin."""
    if config.AUTO_DECLINE_ON_MATCH:
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

    _notify_admin(chat_id, new_user_id, matched_user_id, score, components)


def _notify_admin(
    chat_id: int,
    new_user_id: int,
    matched_user_id: int,
    score: float,
    components: list,
):
    """Send alert to admin with inline action buttons."""
    if not config.ADMIN_CHAT_ID:
        return

    action_word = (
        "DECLINED" if config.AUTO_DECLINE_ON_MATCH
        else "FLAGGED (approved, pending review)"
    )
    components_str = ", ".join(components)

    alert_text = (
        "\U000026a0\U0000fe0f MULTI-ACCOUNT DETECTED\n"
        f"{'=' * 32}\n"
        f"Status: {action_word}\n\n"
        f"New user: {new_user_id}\n"
        f"Matches: {matched_user_id}\n"
        f"Similarity: {score:.0%}\n"
        f"Signals: {components_str}\n"
        f"Group: {chat_id}\n"
        f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
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
        )
    )

    try:
        bot.send_message(config.ADMIN_CHAT_ID, alert_text, reply_markup=markup)
    except Exception:
        logger.exception("Failed to notify admin about flag")


# ═══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def run_flask():
    app.run(host=config.WEB_HOST, port=config.WEB_PORT, debug=False)


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
    logger.info("Flask server started on %s:%s", config.WEB_HOST, config.WEB_PORT)

    # Start bot polling on main thread
    logger.info("Starting bot polling...")
    bot.infinity_polling(
        timeout=60,
        long_polling_timeout=60,
        allowed_updates=[
            "message",
            "callback_query",
            "chat_join_request",
        ],
    )

"""
Monkey-patch for pyTelegramBotAPI 4.34.0 to support Bot API 10.1
Join Request Queries (released June 11, 2026).

Adds:
  - ChatJoinRequest.query_id   (new optional field)
  - TeleBot.send_chat_join_request_web_app(query_id, web_app_url)
  - TeleBot.answer_chat_join_request_query(query_id, result)
  - Corresponding low-level helpers in apihelper

Remove this module once pyTelegramBotAPI natively supports Bot API 10.1.
"""

import types as _builtin_types

import telebot
from telebot import apihelper, types

# ─── 1. Patch ChatJoinRequest to carry `query_id` ────────────────────────────

_original_cjr_de_json = types.ChatJoinRequest.de_json.__func__   # unwrap classmethod

@classmethod
def _patched_cjr_de_json(cls, json_string):
    if json_string is None:
        return None
    obj = cls.check_json(json_string)
    # Preserve query_id before the original constructor (which uses **kwargs)
    query_id = obj.get("query_id")
    instance = _original_cjr_de_json(cls, json_string)
    instance.query_id = query_id
    return instance

types.ChatJoinRequest.de_json = _patched_cjr_de_json


# ─── 2. Add low-level API helpers ────────────────────────────────────────────

def send_chat_join_request_web_app(token, chat_join_request_query_id, web_app_url):
    """
    sendChatJoinRequestWebApp – open a Mini App for the user who
    clicked "Apply to Join".

    https://core.telegram.org/bots/api#sendchatjoinrequestwebapp
    """
    method_url = "sendChatJoinRequestWebApp"
    payload = {
        "chat_join_request_query_id": chat_join_request_query_id,
        "web_app_url": web_app_url,
    }
    return apihelper._make_request(token, method_url, params=payload, method="post")


def answer_chat_join_request_query(token, chat_join_request_query_id, result):
    """
    answerChatJoinRequestQuery – approve / decline / queue a join
    request query directly.

    https://core.telegram.org/bots/api#answerchatjoinrequestquery
    """
    method_url = "answerChatJoinRequestQuery"
    payload = {
        "chat_join_request_query_id": chat_join_request_query_id,
        "result": result,
    }
    return apihelper._make_request(token, method_url, params=payload, method="post")


# Attach to apihelper module so they can be referenced normally
apihelper.send_chat_join_request_web_app = send_chat_join_request_web_app
apihelper.answer_chat_join_request_query = answer_chat_join_request_query


# ─── 3. Add high-level methods to TeleBot ────────────────────────────────────

def _send_chat_join_request_web_app(self, chat_join_request_query_id: str, web_app_url: str) -> bool:
    """
    Open a Mini App for the user who submitted a join request query.
    Must be called within 10 seconds of receiving a ChatJoinRequest
    that contains a query_id.

    :param chat_join_request_query_id: Unique identifier of the join request query
    :param web_app_url: The URL of the Mini App to be opened
    :return: True on success
    """
    return apihelper.send_chat_join_request_web_app(
        self.token, chat_join_request_query_id, web_app_url,
    )


def _answer_chat_join_request_query(self, chat_join_request_query_id: str, result: str) -> bool:
    """
    Directly answer a join request query with a verdict.

    :param chat_join_request_query_id: Unique identifier of the join request query
    :param result: "approve", "decline", or "queue"
    :return: True on success
    """
    return apihelper.answer_chat_join_request_query(
        self.token, chat_join_request_query_id, result,
    )


telebot.TeleBot.send_chat_join_request_web_app = _send_chat_join_request_web_app
telebot.TeleBot.answer_chat_join_request_query = _answer_chat_join_request_query

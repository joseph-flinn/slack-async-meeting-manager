import atexit
import datetime
import json
import logging
import os

from dotenv import load_dotenv
from pymongo import MongoClient
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

logging.basicConfig(level=logging.DEBUG)
load_dotenv()

client = MongoClient(
    host=os.environ.get("MONGO_HOST", "localhost"),
    username=os.environ.get("MONGO_USERNAME", "default"),
    password=os.environ.get("MONGO_PASSWORD", "SECRET"),
)

db = client[os.environ.get("MONGO_DATABASE", "test")]
meetings_store = db.meetings

app = App(token=os.environ.get("SLACK_BOT_TOKEN", "SECRET"))


@app.command("/samm")
def handle_command(body, ack, respond, client, logger):
    ack()

    metadata = {
        "channel_id": body["channel_id"],
    }

    res = client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "create-meeting",
            "private_metadata": json.dumps(metadata),
            "title": {
                "type": "plain_text",
                "text": "New Async Meeting",
            },
            "submit": {
                "type": "plain_text",
                "text": "Submit",
            },
            "close": {
                "type": "plain_text",
                "text": "Cancel",
            },
            "blocks": [
                {
                    "type": "input",
                    "block_id": "input_name",
                    "label": {"type": "plain_text", "text": "Name"},
                    "element": {"type": "plain_text_input", "action_id": "name"},
                },
                {
                    "type": "input",
                    "block_id": "input_required",
                    "label": {"type": "plain_text", "text": "Required"},
                    "element": {"type": "multi_users_select", "action_id": "required"},
                },
                {
                    "type": "input",
                    "block_id": "input_optional",
                    "label": {"type": "plain_text", "text": "Optional"},
                    "element": {"type": "multi_users_select", "action_id": "optional"},
                    "optional": True,
                },
                {
                    "type": "input",
                    "block_id": "input_agenda",
                    "label": {"type": "plain_text", "text": "Agenda"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "agenda",
                        "multiline": True,
                    },
                },
                {
                    "type": "input",
                    "block_id": "input_end",
                    "label": {"type": "plain_text", "text": "Meeting End"},
                    "element": {"type": "datetimepicker", "action_id": "end"},
                },
                {
                    "type": "input",
                    "block_id": "input_reminder",
                    "label": {
                        "type": "plain_text",
                        "text": "Reminder Frequency (Hours)",
                    },
                    "element": {
                        "type": "number_input",
                        "is_decimal_allowed": False,
                        "initial_value": os.environ.get(
                            "SAMM_DEFAULT_REMINDER_PERIOD", "33"
                        ),
                        "action_id": "reminder",
                    },
                },
            ],
        },
    )


@app.view("create-meeting")
def view_submission(ack, body, client, view, logger):
    ack()
    logger.info(body)

    metadata = json.loads(body["view"]["private_metadata"])

    modal_data = {
        "name": view["state"]["values"]["input_name"]["name"]["value"],
        "required": view["state"]["values"]["input_required"]["required"][
            "selected_users"
        ],
        "optional": view["state"]["values"]["input_optional"]["optional"][
            "selected_users"
        ],
        "agenda": view["state"]["values"]["input_agenda"]["agenda"]["value"],
        "reminder": view["state"]["values"]["input_reminder"]["reminder"]["value"],
        "end": view["state"]["values"]["input_end"]["end"]["selected_date_time"],
    }

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{modal_data['name']}"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Required Attendees:* {', '.join([f'<@{user}>' for user in modal_data['required']])}\n"
                    f"*Optional Attendees:* {', '.join([f'<@{user}>' for user in modal_data['optional']])}\n"
                    f"*Ends:* {datetime.datetime.fromtimestamp(modal_data['end'])} (UTC)\n"
                    f"*Reminder:* {modal_data['reminder']} hr"
                ),
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Agenda:*\n{modal_data['agenda']}"},
        },
    ]

    response = client.chat_postMessage(
        channel=metadata["channel_id"], blocks=blocks, text=f"{modal_data['name']}"
    )
    logger.info(response)

    meeting_data = {
        "channel": response["channel"],
        "ts": response["ts"],
        "bot_id": response["message"]["bot_id"],
        "responses": [],
        "finished": False,
        **modal_data,
    }
    meetings_store.insert_one(meeting_data)


@app.event("reaction_added")
def handle_reaction_added(event, say, logger):
    logger.info(event)

    event_data = {
        "user": event["user"],
        "reaction": event["reaction"],
        "channel": event["item"]["channel"],
        "ts": event["item"]["ts"],
    }

    meeting_query = {"channel": event_data["channel"], "ts": event_data["ts"]}
    meeting = meetings_store.find_one(meeting_query)

    logger.info(meeting)

    if (
        not meeting["finished"]
        and event_data["reaction"] == "white_check_mark"
        and event_data["user"] in meeting["required"]
        and event_data["user"] not in meeting["responses"]
    ):
        meetings_store.update_one(
            meeting_query, {"$push": {"responses": event_data["user"]}}
        )

        if set(meeting["required"]) == set([event_data["user"], *meeting["responses"]]):
            meetings_store.update_one(meeting_query, {"$set": {"finished": True}})


@app.event("message")
def handle_message(event, logger):
    if event.get("thread_ts", None):
        logger.info(event)

        message_data = {
            "user": event["user"],
            "ts": event["ts"],
            "thread_ts": event.get("thread_ts", None),
            "channel": event["channel"],
        }

        logger.info(json.dumps(message_data, indent=2))

        meeting_query = {
            "channel": message_data["channel"],
            "ts": message_data["thread_ts"],
        }
        meeting = meetings_store.find_one(meeting_query)

        if (
            not meeting["finished"]
            and message_data["user"] in meeting["required"]
            and message_data["user"] not in meeting["responses"]
        ):
            meetings_store.update_one(
                meeting_query, {"$push": {"responses": message_data["user"]}}
            )

            if set(meeting["required"]) == set(
                [message_data["user"], *meeting["responses"]]
            ):
                meetings_store.update_one(meeting_query, {"$set": {"finished": True}})


@atexit.register
def cleanup():
    client.close()


if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()

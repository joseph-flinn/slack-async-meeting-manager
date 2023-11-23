import logging
import os

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

logging.basicConfig(level=logging.DEBUG)
load_dotenv()

app = App(token=os.environ["SLACK_BOT_TOKEN"])


@app.middleware  # or app.use(log_request)
def log_request(logger, body, next):
    logger.debug(body)
    return next()


@app.command("/samm")
def handle_command(body, ack, respond, client, logger):
    logger.info(body)
    logger.info(body['channel_id'])
    ack()

    res = client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "create-meeting",
            "private_metadata": body['channel_id'],
            "title": {
                "type": "plain_text",
                "text": "My App",
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
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "name"
                    },
                },
                {
                    "type": "input",
                    "block_id": "input_data",
                    "label": {"type": "plain_text", "text": "Data"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "data",
                        "multiline": True
                    },
                },
            ],
        },
    )



@app.view("create-meeting")
def view_submission(ack, body, client, view, logger):
    ack()
    logger.info(body)

    channel_id = body['view']['private_metadata']

    name = view['state']['values']['input_name']['name']['value']
    data = view['state']['values']['input_data']['data']['value']

    msg = f'\n  name: {name}\n  data: {data}\n  channel_id: {channel_id}'
    logger.info(msg)

    client.chat_postMessage(channel=channel_id, text=msg)


if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()

# pip install slack_bolt
# export SLACK_SIGNING_SECRET=***
# export SLACK_BOT_TOKEN=xoxb-***
# python modals_app.py

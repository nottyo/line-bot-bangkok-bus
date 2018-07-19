from flask import Flask, request, abort
import os
import sys
import requests
from linebot import (
    WebhookHandler, LineBotApi
)

from linebot.models import (
    LocationMessage, MessageEvent, TextSendMessage, LocationSendMessage, ConfirmTemplate, PostbackAction,
    TemplateSendMessage, PostbackEvent
)
from linebot.exceptions import (
    LineBotApiError, InvalidSignatureError
)

channel_secret = os.getenv('LINE_CHANNEL_SECRET', None)
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None)
if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)

handler = WebhookHandler(channel_secret)
line_bot_api = LineBotApi(channel_access_token)
app = Flask(__name__)

api_url = 'http://www.cityglide.com/api.php'

@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except LineBotApiError as e:
        print("Got exception from LINE Messaging API: %s\n" % e.message)
        for m in e.error.details:
            print("  %s: %s" % (m.property, m.message))
        print("\n")
    except InvalidSignatureError:
        abort(400)

    return 'OK'


@app.route('/')
def hello_world():
    return 'Hello World!'


def get_nearest_bus_stop(lat, lng, address):
    payload = {
        'nearest_station': '{0}, {1}'.format(lat, lng),
        'MODE': 'get_marker_all_station',
        'nearest_station_lat': lat,
        'nearest_station_lng': lng,
        'keyword_station': address
    }
    response = requests.post(api_url, data=payload)
    return response


def get_arrival_data(stop_name):
    print('stop_name: \'{0}\''.format(stop_name))
    payload = {
        'origin': '{0}'.format(stop_name),
        'MODE': 'get_poly_origin'
    }
    response = requests.post(api_url, data=payload)
    if response.status_code == 200:
        json = response.json()
        text = 'สายที่กำลังจะเข้ามา: \n'
        for number, route_data in json.items():
            text += 'สาย {0} รออีก {1}\n'.format(route_data['bus_line'], route_data['duration_text'])
        return text
    else:
        return ''


@handler.add(PostbackEvent)
def handle_postback(event):
    if 'answer=YES' in event.postback.data:
        stop_name = str(event.postback.data).split('&')[1].split('=')[1]
        result = get_arrival_data(stop_name)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=result))


@handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    lat = event.message.latitude
    lng = event.message.longitude
    address = event.message.address
    response = get_nearest_bus_stop(lat, lng, address)
    reply_messages = []
    if response.status_code == 200:
        json = response.json()
        for stop_id, stop_data in json.items():
            if stop_data['radius'] < 0.1:
                text = 'ป้ายที่ใกล้ที่สุด: {0}\n'.format(stop_data['stop_name'])
                text += 'สายรถเมล์ขาเข้า: {0}\n'.format(stop_data['bus_line_inbound'])
                text += 'สายรถเมล์ขาออก: {0}'.format(stop_data['bus_line_outbound'])

                reply_messages.append(TextSendMessage(text=text))
                reply_messages.append(LocationSendMessage(
                    title=stop_data["stop_name"],
                    address=stop_data["stop_name"],
                    latitude=stop_data["latitude"],
                    longitude=stop_data["longitude"]
                ))
                confirm_template = ConfirmTemplate(
                    text="คำนวณเวลามาถึง?",
                    actions=[
                        PostbackAction(label='YES', data='answer=YES&stop_name={0}'.format(stop_data['stop_name']), display_text='YES'),
                        PostbackAction(label='NO', data='No', display_text='NO')
                    ]
                )
                break

    reply_messages.append(TemplateSendMessage(template=confirm_template, alt_text='Confirm Arrival Time!'))
    line_bot_api.reply_message(event.reply_token, messages=reply_messages)


if __name__ == '__main__':
    app.run()

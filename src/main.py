import time
import os
from math import pi
from functools import lru_cache

import telebot
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from FlightRadar24.api import FlightRadar24API
from haversine import inverse_haversine, haversine, Direction

from utils import get_logger


TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHECK_DISTANCE = int(os.getenv('CHECK_DISTANCE'))

logger = get_logger('main')
bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode=None)
fr_api = FlightRadar24API()
results = {}


def get_square(lat, lon, distance):
    point = (lat, lon)
    
    west = inverse_haversine(point, distance, Direction.WEST)
    west_north = inverse_haversine(west, distance, Direction.NORTH)
    
    east = inverse_haversine(point, distance, Direction.EAST)
    east_south = inverse_haversine(east, distance, Direction.SOUTH)
    
    return west_north, east_south


def convert_square_to_bounds(p1, p2):
    return '{},{},{},{}'.format(p1[0],p2[0],p1[1],p2[1])


@lru_cache()
def get_details(flight_id, ttl_hash=None):
    return fr_api.get_flight_details(flight_id)

def get_ttl_hash(seconds=3600):
    """Return the same value withing `seconds` time period"""
    return round(time.time() / seconds)


def get_plane_data(chat_id, message_id, n):
    items = results[chat_id][message_id]
    item = get_details(items[n].id, ttl_hash=get_ttl_hash())
    
    photo = ''
    if 'images' in item['aircraft']:
        if item['aircraft']['images'] is None:
            photo = 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/No_image_available.svg/2048px-No_image_available.svg.png'
        else:
            if 'large' in item['aircraft']['images']:
                photo = item['aircraft']['images']['large'][0]['src']

    caption = 'Code: {}'.format(item['identification']['callsign'])
    if 'model' in item['aircraft']:
        caption += '\nModel: {}'.format(item['aircraft']['model']['text'])
    if 'airline' in item and 'name' in item['airline']:
        caption += '\nAirline: {}'.format(item['airline']['name'])
    if 'airport' in item:
        if 'origin' in item['airport'] and item['airport']['origin'] is not None:
            caption += '\nFrom: {}'.format(item['airport']['origin']['name'])
        if 'destination' in item['airport'] and item['airport']['destination'] is not None:
            caption += '\nTo: {}'.format(item['airport']['destination']['name'])
    
    markup = InlineKeyboardMarkup()
    markup.row_width = 3
    if n > 0:
        but_prev = '<'
        cb_prev = 'cb_show_{}_{}_{}'.format(chat_id, message_id, n-1)
    else:
        but_prev = '|'
        cb_prev = 'cb_show_{}_{}_{}'.format(chat_id, message_id, -1)
    if n < len(items)-1:
        but_next = '>'
        cb_next = 'cb_show_{}_{}_{}'.format(chat_id, message_id, n+1)
    else:
        but_next = '|'
        cb_next = 'cb_show_{}_{}_{}'.format(chat_id, message_id, -1)   
    markup.add(
        InlineKeyboardButton(but_prev, callback_data=cb_prev),
        InlineKeyboardButton('{}/{}'.format(n+1, len(items)), callback_data="cb_count"),
        InlineKeyboardButton(but_next, callback_data=cb_next)
    )
    
    return photo, caption, markup


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    logger.info('{}: welcome message'.format(message.chat.id))

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    itembtn1 = KeyboardButton('Scan', request_location=True)
    markup.add(itembtn1)
    bot.reply_to(message, "Hey there! Send me your location with the Scan button and I'll show you the planes around", reply_markup=markup)


@bot.message_handler(content_types=['location']) 
def location_message(message):
    logger.info('{}: location message'.format(message.chat.id))
    #print(message)
    
    p = message.location.latitude, message.location.longitude
    distance = CHECK_DISTANCE # km
    p1, p2 = get_square(message.location.latitude, message.location.longitude, distance)
    bounds = convert_square_to_bounds(p1, p2)
    flights = fr_api.get_flights(bounds = bounds)
    flights_sorted = sorted(flights, key=lambda x: haversine(p, (x.latitude, x.longitude)))
    res = []
    for f in flights_sorted:
        if f.on_ground > 0:
            continue
        if f.ground_speed == 0:
            continue
        res.append(f)
        
    #print(len(res))
    if len(res) == 0:
        logger.info('{}: no flights found'.format(message.chat.id))
        bot.send_message(message.chat.id, 'No flights around')
        return
    
    print(res)
    if message.chat.id not in results:
        results[message.chat.id] = {}
    results[message.chat.id][message.id] = res
    
    photo, caption, markup = get_plane_data(message.chat.id, message.id, 0)
    r = bot.send_photo(message.chat.id, photo, caption=caption, reply_markup=markup)
    logger.info('{}: sent {} flights'.format(message.chat.id, len(res)))
    #print(r)
    

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):    
    #print(call)
    arr = call.data.split('_')
    if arr[1] == 'show':
        chat_id = int(arr[2])
        message_id = int(arr[3])
        n = int(arr[4])

        logger.info('{}: callback request to get {} - {}'.format(chat_id, message_id, n))
        
        if chat_id not in results:
            logger.warning('{}: callback request failed (no chat id stored)'.format(chat_id))
            return
        if message_id not in results[chat_id]:
            logger.warning('{}: callback request failed (no message {} stored)'.format(chat_id, message_id))
            return
        
        if n >= 0:
            photo, caption, markup = get_plane_data(chat_id, message_id, n)
            bot.edit_message_media(
                media=types.InputMediaPhoto(media=photo, caption=caption), 
                message_id=call.message.id, 
                chat_id=call.message.chat.id,
                reply_markup=markup
            )


def main():
    logger.info('bot started')
    bot.infinity_polling()


if __name__ == '__main__':
    main()
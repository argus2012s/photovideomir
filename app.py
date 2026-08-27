from flask import Flask, request, jsonify
from telethon import TelegramClient, functions, types
import requests
import asyncio
import os

app = Flask(__name__)

API_ID = 39042175
API_HASH = '659ed9b7bd42de190eb95a82d77db89d'
SESSION_NAME = 'my_personal_account'

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

async def post_story_with_sticker(media_url, link):
    await client.connect()
    
       ext = media_url.split('.')[-1][:4] if '.' in media_url else 'jpg'
    file_path = f"temp_story.{ext}"
    img_data = requests.get(media_url).content
    with open(file_path, 'wb') as handler:
        handler.write(img_data)

    try:
        # 2. Загружаем файл на сервер Telegram
        uploaded_file = await client.upload_file(file_path)
        
        # Определяем тип медиа
        if file_path.endswith(('mp4', 'mov')):
            media = types.InputMediaUploadedDocument(
                file=uploaded_file, mime_type='video/mp4',
                attributes=[types.DocumentAttributeVideo(0, 0, 0)]
            )
        else:
            media = types.InputMediaUploadedPhoto(file=uploaded_file)

        # 3. Настраиваем стикер-ссылку (Link Sticker)
        # Координаты задаются в процентах от 0.0 до 100.0
        # x=50, y=80 
        coords = types.MediaAreaCoordinates(x=50.0, y=85.0, w=30.0, h=8.0, rotation=0.0)
        
        link_area = types.InputMediaArea(
            coordinates=coords,
            info=types.MediaAreaUrl(url=link, coordinates=coords)
        )

        # 4. Публикуем Историю
        await client(functions.stories.SendStoryRequest(
            peer=await client.get_me(),
            media=media,
            privacy_rules=[types.InputPrivacyValueAllowAll()], # Видно всем
            media_areas=[link_area] # Прикрепляем стикер-ссылку
        ))
        return True
    except Exception as e:
        print(f"Ошибка: {e}")
        return False
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    media_url = data.get('media_url')
    link = data.get('link')

    if not media_url or not link:
        return jsonify({"error": "Missing data"}), 400

    # Запускаем асинхронную функцию публикации
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    success = loop.run_until_complete(post_story_with_sticker(media_url, link))
    
    if success:
        return jsonify({"status": "success"}), 200
    else:
        return jsonify({"status": "error"}), 500

if __name__ == '__main__':
    # При первом запуске скрипт попросит код из Telegram для авторизации
    client.start()
    app.run(host='0.0.0.0', port=5000)

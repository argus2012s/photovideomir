from flask import Flask, request, jsonify
from telethon import TelegramClient, functions, types
from telethon.sessions import StringSession
import requests
import asyncio
import os
import traceback

app = Flask(__name__)

# Берем настройки (Клиента пока НЕ создаем)
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
SESSION_STRING = os.environ.get('SESSION_STRING', '')

async def post_story_with_sticker(media_url, link):
    try:
        # ИЗМЕНЕНИЕ ЗДЕСЬ: Создаем клиента прямо внутри функции, 
        # чтобы он был жестко привязан к текущему потоку (event loop)
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        
        # Конструкция "async with" автоматически подключится к Телеграм 
        # и безопасно отключится после публикации
        async with client:
            
            # 1. Скачиваем медиа
            ext = media_url.split('.')[-1][:4] if '.' in media_url else 'jpg'
            file_path = f"temp_story.{ext}"
            
            img_data = requests.get(media_url).content
            with open(file_path, 'wb') as handler:
                handler.write(img_data)

            # 2. Загружаем файл на сервер Телеграм
            uploaded_file = await client.upload_file(file_path)
            
            if file_path.endswith(('mp4', 'mov')):
                media = types.InputMediaUploadedDocument(
                    file=uploaded_file, mime_type='video/mp4',
                    attributes=[types.DocumentAttributeVideo(0, 0, 0)]
                )
            else:
                media = types.InputMediaUploadedPhoto(file=uploaded_file)

            # 3. Настраиваем стикер-ссылку
            coords = types.MediaAreaCoordinates(x=50.0, y=85.0, w=40.0, h=8.0, rotation=0.0)
            link_area = types.InputMediaArea(
                coordinates=coords,
                info=types.MediaAreaUrl(url=link, coordinates=coords)
            )

            # 4. Отправляем Историю
            await client(functions.stories.SendStoryRequest(
                peer=await client.get_me(),
                media=media,
                privacy_rules=[types.InputPrivacyValueAllowAll()],
                media_areas=[link_area]
            ))
            
        # Удаляем временный файл с картинкой
        if os.path.exists(file_path):
            os.remove(file_path)
            
        return "SUCCESS"
        
    except Exception as e:
        return f"Telegram Error: {str(e)}"

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400

        media_url = data.get('media_url')
        link = data.get('link')

        if not media_url or not link:
            return jsonify({"error": "Missing url or link"}), 400

        # Создаем поток и запускаем публикацию
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(post_story_with_sticker(media_url, link))
        
        # Закрываем поток, чтобы не было утечек памяти
        loop.close() 
        
        if result == "SUCCESS":
            return jsonify({"status": "success"}), 200
        else:
            return jsonify({"error": result}), 500

    except Exception as e:
        error_trace = traceback.format_exc()
        print(error_trace)
        return jsonify({"error": f"Crash: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

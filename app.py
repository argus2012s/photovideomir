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
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        
        async with client:
            
            # 1. Скачиваем медиа "умным" способом
            response = requests.get(media_url)
            content_type = response.headers.get('Content-Type', '')
            
            # Определяем, видео это или картинка, по реальным данным от сервера
            if 'video' in content_type or 'mp4' in media_url.lower():
                ext = 'mp4'
            else:
                ext = 'jpg'
                
            file_path = f"temp_story.{ext}"
            
            # Сохраняем файл
            with open(file_path, 'wb') as handler:
                handler.write(response.content)

            # 2. Загружаем файл на сервер Телеграм
            uploaded_file = await client.upload_file(file_path)
            
            if ext == 'mp4':
                media = types.InputMediaUploadedDocument(
                    file=uploaded_file, mime_type='video/mp4',
                    attributes=[types.DocumentAttributeVideo(0, 0, 0)]
                )
            else:
                media = types.InputMediaUploadedPhoto(file=uploaded_file)

            # 3. Настраиваем стикер-ссылку
            coords = types.MediaAreaCoordinates(x=50.0, y=85.0, w=40.0, h=8.0, rotation=0.0)
            link_area = types.InputMediaAreaUrl(
                coordinates=coords,
                url=link
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

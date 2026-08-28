from flask import Flask, request, jsonify
from telethon import TelegramClient, functions, types
from telethon.sessions import StringSession
import requests
import asyncio
import os
import traceback
from PIL import Image, ImageFilter # НОВЫЕ БИБЛИОТЕКИ ДЛЯ ГРАФИКИ

app = Flask(__name__)

API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH', '')
SESSION_STRING = os.environ.get('SESSION_STRING', '')

async def post_story_with_sticker(media_url, link):
    try:
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        
        async with client:
            
            # 1. Скачиваем медиа
            response = requests.get(media_url)
            content_type = response.headers.get('Content-Type', '')
            
            if 'video' in content_type or 'mp4' in media_url.lower():
                ext = 'mp4'
            else:
                ext = 'jpg'
                
            file_path = f"temp_story.{ext}"
            
            with open(file_path, 'wb') as handler:
                handler.write(response.content)

            # ====================================================
            # НОВЫЙ БЛОК: ОБРАБОТКА КАРТИНКИ (ТОЛЬКО ДЛЯ ФОТО)
            # ====================================================
            if ext == 'jpg':
                try:
                    img = Image.open(file_path).convert("RGB")
                    target_w, target_h = 1080, 1920
                    
                    # 1. Создаем размытый фон
                    img_ratio = img.width / img.height
                    target_ratio = target_w / target_h
                    
                    if img_ratio > target_ratio:
                        bg_h = target_h
                        bg_w = int(bg_h * img_ratio)
                    else:
                        bg_w = target_w
                        bg_h = int(bg_w / img_ratio)
                        
                    bg = img.resize((bg_w, bg_h), Image.Resampling.LANCZOS)
                    left = (bg_w - target_w) / 2
                    top = (bg_h - target_h) / 2
                    bg = bg.crop((left, top, left + target_w, top + target_h))
                    bg = bg.filter(ImageFilter.GaussianBlur(radius=40)) # Сильное размытие
                    
                    # 2. Подгоняем основную картинку по ширине (1080px)
                    fg_w = target_w
                    fg_h = int(img.height * (target_w / img.width))
                    fg = img.resize((fg_w, fg_h), Image.Resampling.LANCZOS)
                    
                    # 3. Накладываем картинку по центру
                    paste_y = (target_h - fg_h) // 2
                    bg.paste(fg, (0, paste_y))
                    
                    # 4. Сохраняем готовую Историю
                    bg.save(file_path, "JPEG", quality=95)
                except Exception as img_err:
                    print(f"Ошибка обработки изображения: {img_err}")
            # ====================================================

            # 2. Загружаем файл на сервер Телеграм
            uploaded_file = await client.upload_file(file_path)
            
            if ext == 'mp4':
                media = types.InputMediaUploadedDocument(
                    file=uploaded_file, mime_type='video/mp4',
                    attributes=[types.DocumentAttributeVideo(0, 0, 0)]
                )
            else:
                media = types.InputMediaUploadedPhoto(file=uploaded_file)

            # 3. Настраиваем стикер-ссылку (опустил её чуть ниже - y=85.0)
            coords = types.MediaAreaCoordinates(x=50.0, y=85.0, w=45.0, h=7.0, rotation=0.0)
            link_area = types.MediaAreaUrl(
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

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(post_story_with_sticker(media_url, link))
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

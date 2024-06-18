import google.generativeai as genai
from flask import Flask, request, jsonify
import requests
import os
from google.cloud import vision
from google.oauth2 import service_account

wa_token = os.environ.get("WA_TOKEN")
genai.configure(api_key=os.environ.get("GEN_API"))
phone_id = os.environ.get("PHONE_ID")
bot_name = "عمرو"
model_name = "gemini-1.5-flash-latest"

app = Flask(__name__)

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 0,
    "max_output_tokens": 8192,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

model = genai.GenerativeModel(model_name=model_name,
                              generation_config=generation_config,
                              safety_settings=safety_settings)

conversations = {}

def send(phone, answer):
    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {
        'Authorization': f'Bearer {wa_token}',
        'Content-Type': 'application/json'
    }
    data = {
        "messaging_product": "whatsapp",
        "to": f"{phone}",
        "type": "text",
        "text": {"body": f"{answer}"},
    }

    response = requests.post(url, headers=headers, json=data)
    return response

def remove(*file_paths):
    for file in file_paths:
        if os.path.exists(file):
            os.remove(file)

@app.route("/", methods=["GET", "POST"])
def index():
    return "Bot"

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == "BOT":
            return challenge, 200
        else:
            return "Failed", 403
    elif request.method == "POST":
        try:
            data = request.get_json()["entry"][0]["changes"][0]["value"]["messages"][0]
            phone = data["from"]
            if phone not in conversations:
                conversations[phone] = model.start_chat(history=[])
            convo = conversations[phone]
            if data["type"] == "text":
                prompt = data["text"]["body"]
                convo.send_message(prompt)
                send(phone, convo.last.text)
            elif data["type"] == "image":
                media_url_endpoint = f'https://graph.facebook.com/v18.0/{data["image"]["id"]}/'
                headers = {'Authorization': f'Bearer {wa_token}'}
                media_response = requests.get(media_url_endpoint, headers=headers)
                media_url = media_response.json()["url"]
                media_download_response = requests.get(media_url, headers=headers)

                filename = "/tmp/temp_image.jpg"
                with open(filename, "wb") as temp_media:
                    temp_media.write(media_download_response.content)
                
                # استخدام Google Vision API لاستخراج النص من الصورة
                credentials = service_account.Credentials.from_service_account_file("path_to_your_service_account.json")
                client = vision.ImageAnnotatorClient(credentials=credentials)

                with open(filename, "rb") as image_file:
                    content = image_file.read()
                
                image = vision.Image(content=content)
                response = client.text_detection(image=image)
                texts = response.text_annotations

                if texts:
                    extracted_text = texts[0].description.strip()
                else:
                    extracted_text = "لم أتمكن من استخراج أي نص من الصورة."

                comment = data.get("caption", "")
                answer = f"{comment}\nالنص المستخرج: {extracted_text}"
                convo.send_message(answer)
                send(phone, convo.last.text)
                remove(filename)
            else:
                send(phone, "هذا التنسيق غير مدعوم من قبل البوت ☹")
                return jsonify({"status": "ok"}), 200

        except Exception as e:
            print(f"Error: {e}")
        return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(debug=True, port=8000)

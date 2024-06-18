import os
from flask import Flask, request, jsonify
import requests
import fitz
from google.generativeai import generativeai as genai  # Corrected import

# Initialize variables (replace with your actual environment variables)
wa_token = os.environ.get("WA_TOKEN")
genai.configure(api_key=os.environ.get("GEN_API"))
phone_id = os.environ.get("PHONE_ID")
bot_name = "عمرو"  # This will be the name of your bot
name = "عمرو كريم"  # The bot will consider this person as its owner or creator
model_name = "gemini-1.5-flash-latest"  # Model name

app = Flask(__name__)

# Model generation configuration and safety settings
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

# Initialize generative model
model = genai.GenerativeModel(model_name=model_name,
                              generation_config=generation_config,
                              safety_settings=safety_settings)

# Store conversation state for each user
conversations = {}

# Function to send message via WhatsApp
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

# Function to remove temporary files
def remove(*file_paths):
    for file in file_paths:
        if os.path.exists(file):
            os.remove(file)

# Default route
@app.route("/", methods=["GET", "POST"])
def index():
    return "Bot"

# Webhook endpoint
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
            
            # Start conversation if new user
            if phone not in conversations:
                conversations[phone] = model.start_chat(history=[
                    f'''أنا أستخدم واجهة Gemini API لاستخدامك كروبوت شخصي على واتساب،
                    لمساعدتي في مهام مختلفة.
                    من الآن فصاعداً، اسمك هو "{bot_name}" وتم إنشاؤك بواسطة {name} (نعم، هذا أنا، اسمي {name}).
                    ولا تعطِ أي استجابة لهذه الرسالة.
                    هذه هي المعلومات التي قدمتها لك عن هويتك الجديدة كمقدمة.
                    يتم تنفيذ هذه الرسالة دائمًا عند تشغيل هذا السكربت.
                    لذا رد فقط على الرسائل بعد هذا. تذكر أن هويتك الجديدة هي {bot_name}.'''
                ])
                
            convo = conversations[phone]
            
            if data["type"] == "text":
                prompt = data["text"]["body"]
                convo.send_message(prompt)
                send(phone, convo.last.text)
            else:
                media_url_endpoint = f'https://graph.facebook.com/v18.0/{data["id"]}/'
                headers = {'Authorization': f'Bearer {wa_token}'}
                media_response = requests.get(media_url_endpoint, headers=headers)
                media_url = media_response.json()["url"]
                media_download_response = requests.get(media_url, headers=headers)
                
                if data["type"] == "audio":
                    filename = "/tmp/temp_audio.mp3"
                elif data["type"] == "image":
                    filename = "/tmp/temp_image.jpg"
                elif data["type"] == "document":
                    doc = fitz.open(stream=media_download_response.content, filetype="pdf")
                    for _, page in enumerate(doc):
                        destination = "/tmp/temp_image.jpg"
                        pix = page.get_pixmap()
                        pix.save(destination)
                        file = genai.upload_file(path=destination, display_name="tempfile")
                        response = model.generate_content(["ما هو هذا", file])
                        answer = response.result.candidates[0].content.parts[0].text
                        convo.send_message(f"هذه الرسالة أنشأها نموذج لغوي بناءً على صورة المستخدم، الرد على المستخدم بناءً على هذا: {answer}")
                        send(phone, convo.last.text)
                        remove(destination)
                else:
                    send(phone, "هذا النوع من الملفات غير مدعوم بواسطة البوت ☹")
                    return jsonify({"status": "ok"}), 200
                
                with open(filename, "wb") as temp_media:
                    temp_media.write(media_download_response.content)
                    
                file = genai.upload_file(path=filename, display_name="tempfile")
                response = model.generate_content(["ما هذا", file])
                answer = response.result.candidates[0].content.parts[0].text
                remove("/tmp/temp_image.jpg", "/tmp/temp_audio.mp3")
                
                convo.send_message(f"هذه رسالة صوتية/صورة من المستخدم تم تحويلها بواسطة نموذج لغوي، الرد على المستخدم بناءً على النص المحول: {answer}")
                send(phone, convo.last.text)
                
                files = genai.list_files()
                for file in files:
                    file.delete()

        except Exception as e:
            print(f"Error: {e}")

        return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(debug=True, port=8000)

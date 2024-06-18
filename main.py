import os
from flask import Flask, request, jsonify
import requests
import fitz
from google.generativeai import generativeai as genai

# Initialize variables
wa_token = os.environ.get("WA_TOKEN")
genai.configure(api_key=os.environ.get("GEN_API"))
phone_id = os.environ.get("PHONE_ID")
bot_name = "عمرو"
name = "عمرو كريم"
model_name = "gemini-1.5-flash-latest"

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
    url = f"https://graph.facebook.com/v18.0/me/messages"
    headers = {
        'Authorization': f'Bearer {wa_token}',
        'Content-Type': 'application/json'
    }
    data = {
        "recipient": {"phone_number": f"{phone}"},
        "message": {"text": f"{answer}"}
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
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        for entry in data["entry"]:
            for change in entry["changes"]:
                message = change["value"]["message"]
                phone = message["from"]
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
                
                if message["type"] == "text":
                    prompt = message["text"]
                    convo.send_message(prompt)
                    send(phone, convo.last.text)
                else:
                    media_url = message["attachments"][0]["url"]
                    media_response = requests.get(media_url)
                    if message["type"] == "audio":
                        filename = "/tmp/temp_audio.mp3"
                    elif message["type"] == "image":
                        filename = "/tmp/temp_image.jpg"
                    elif message["type"] == "file":
                        with open("/tmp/temp_file", "wb") as temp_file:
                            temp_file.write(media_response.content)
                        doc = fitz.open("/tmp/temp_file")
                        for page in doc:
                            pix = page.get_pixmap()
                            pix.save("/tmp/temp_image.jpg")
                        filename = "/tmp/temp_image.jpg"
                    else:
                        send(phone, "هذا النوع من الملفات غير مدعوم بواسطة البوت ☹")
                        return jsonify({"status": "ok"}), 200
                    
                    file = genai.upload_file(path=filename, display_name="tempfile")
                    response = model.generate_content(["ما هذا", file])
                    answer = response.result.candidates[0].content.parts[0].text
                    convo.send_message(f"هذه رسالة صوتية/صورة من المستخدم تم تحويلها بواسطة نموذج لغوي، الرد على المستخدم بناءً على النص المحول: {answer}")
                    send(phone, convo.last.text)
                    
                    files = genai.list_files()
                    for file in files:
                        file.delete()

                    remove("/tmp/temp_image.jpg", "/tmp/temp_audio.mp3", "/tmp/temp_file")

    except Exception as e:
        print(f"Error: {e}")

    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(debug=True, port=8000)

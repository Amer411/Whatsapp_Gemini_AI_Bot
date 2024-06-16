import google.generativeai as genai
from flask import Flask,request,jsonify
import requests
import os
import fitz

wa_token=os.environ.get("WA_TOKEN")
genai.configure(api_key=os.environ.get("GEN_API"))
phone_id=os.environ.get("PHONE_ID")
bot_name="عمرو" #This will be the name of your bot, eg: "Hello I am Astro Bot"
model_name="gemini-1.5-flash-latest" #Switch to "gemini-1.0-pro" or any free model, if "gemini-1.5-flash" becomes paid in future.

app=Flask(__name__)

generation_config = {
  "temperature": 1,
  "top_p": 0.95,
  "top_k": 0,
  "max_output_tokens": 8192,
}

safety_settings = [
  {"category": "HARM_CATEGORY_HARASSMENT","threshold": "BLOCK_MEDIUM_AND_ABOVE"},
  {"category": "HARM_CATEGORY_HATE_SPEECH","threshold": "BLOCK_MEDIUM_AND_ABOVE"},  
  {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT","threshold": "BLOCK_MEDIUM_AND_ABOVE"},
  {"category": "HARM_CATEGORY_DANGEROUS_CONTENT","threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

model = genai.GenerativeModel(model_name=model_name,
                              generation_config=generation_config,
                              safety_settings=safety_settings)

# Store conversation state for each user
conversations = {}

def send(phone, answer):
    url=f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers={
        'Authorization': f'Bearer {wa_token}',
        'Content-Type': 'application/json'
    }
    data={
          "messaging_product": "whatsapp", 
          "to": f"{phone}", 
          "type": "text",
          "text":{"body": f"{answer}"},
          }
    
    response=requests.post(url, headers=headers,json=data)
    return response

def remove(*file_paths):
    for file in file_paths:
        if os.path.exists(file):
            os.remove(file)
        else:pass

@app.route("/",methods=["GET","POST"])
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
            else:
                # Handle media messages...
                # ...
        except :pass
        return jsonify({"status": "ok"}), 200
if __name__ == "__main__":
    app.run(debug=True, port=8000)

from datetime import datetime
from flask import Flask, flash, render_template, request, redirect, url_for, send_file, send_from_directory
from google.cloud import texttospeech
from google.cloud import speech
import os
from google.cloud import language_v1

nlp_client = language_v1.LanguageServiceClient()
speech_service = texttospeech.TextToSpeechClient()
speech_to_text_service = speech.SpeechClient()

app = Flask(__name__)
app.secret_key = 'secret_key_example'

TEXT_UPLOADS = 'uploads/text_files'
AUDIO_UPLOADS = 'uploads/audio_files'
SUPPORTED_FILE_TYPES = {'wav', 'txt', 'mp3'}

app.config['TEXT_UPLOADS'] = TEXT_UPLOADS
app.config['AUDIO_UPLOADS'] = AUDIO_UPLOADS

# Helper function to check allowed file types
def is_supported_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in SUPPORTED_FILE_TYPES

# Fetch and sort files in a directory
def fetch_files(directory):
    files = []
    for filename in os.listdir(directory):
        if is_supported_file(filename):
            files.append(filename)
    files.sort(reverse=True)
    return files

@app.route('/audio/<filename>')
def serve_audio(filename):
    return send_from_directory(app.config['AUDIO_UPLOADS'], filename, mimetype='audio/mpeg')

@app.route('/')
def homepage():
    text_files = fetch_files(TEXT_UPLOADS)
    audio_files = fetch_files(AUDIO_UPLOADS)
    return render_template('index.html', text_files=text_files, audio_files=audio_files)

@app.route('/upload_audio', methods=['POST'])
def process_audio_upload():
    if 'audio_data' not in request.files:
        flash('No audio data uploaded')
        return redirect(request.url)

    file = request.files['audio_data']
    if file.filename == '':
        flash('No file selected')
        return redirect(request.url)

    if file and is_supported_file(file.filename):
        new_filename = "audio_" + datetime.now().strftime("%Y%m%d-%H%M%S") + '.wav'
        file_path = os.path.join(app.config['TEXT_UPLOADS'], new_filename)
        file.save(file_path)
        flash('File uploaded successfully')

        def convert_speech_to_text(file_path):
            with open(file_path, "rb") as audio_file:
                audio_data = audio_file.read()

            audio_config = speech.RecognitionAudio(content=audio_data)
            recognition_config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.MP3,
                sample_rate_hertz=24000,
                language_code="en-US",
            )

            response = speech_to_text_service.recognize(config=recognition_config, audio=audio_config)
            if response.results:
                return response.results[0].alternatives[0].transcript
            else:
                return "No transcription available"

        transcription = convert_speech_to_text(file_path)
        flash(transcription)

        document = language_v1.types.Document(content=transcription, type_=language_v1.types.Document.Type.PLAIN_TEXT)
        sentiment = nlp_client.analyze_sentiment(request={"document": document}).document_sentiment

        sentiment_label = "positive" if sentiment.score > 0 else "negative"
        sentiment_info = f"Sentiment: {sentiment_label}, Magnitude: {sentiment.magnitude}, Score: {sentiment.score}"

        text_file = os.path.splitext(file_path)[0] + ".txt"
        with open(text_file, "w") as txt_file:
            txt_file.write(f"{transcription}\n{sentiment_info}")

    text_files = fetch_files(TEXT_UPLOADS)
    audio_files = fetch_files(AUDIO_UPLOADS)
    return render_template('index.html', transcription=transcription, sentiment_analysis=sentiment_info, text_files=text_files, audio_files=audio_files)

@app.route('/text/<filename>')
def fetch_uploaded_text(filename):
    return send_from_directory(app.config['TEXT_UPLOADS'], filename)

@app.route('/text_to_speech', methods=['POST'])
def process_text_upload():
    user_text = request.form['text']
    
    input_text = texttospeech.SynthesisInput(text=user_text)
    voice_config = texttospeech.VoiceSelectionParams(language_code="en-US", ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL)
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)

    audio_response = speech_service.synthesize_speech(input=input_text, voice=voice_config, audio_config=audio_config)

    output_audio_filename = "synth_audio_" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".mp3"
    output_audio_path = os.path.join(AUDIO_UPLOADS, output_audio_filename)

    with open(output_audio_path, "wb") as output_audio_file:
        output_audio_file.write(audio_response.audio_content)
        flash(f'Audio generated: {output_audio_filename}')
    
    document = language_v1.types.Document(content=user_text, type_=language_v1.types.Document.Type.PLAIN_TEXT)
    sentiment = nlp_client.analyze_sentiment(request={"document": document}).document_sentiment

    sentiment_label = "positive" if sentiment.score > 0 else "negative"
    sentiment_info = f"Sentiment: {sentiment_label}, Magnitude: {sentiment.magnitude}, Score: {sentiment.score}"

    text_files = fetch_files(TEXT_UPLOADS)
    audio_files = fetch_files(AUDIO_UPLOADS)
    return render_template('index.html', transcription=user_text, sentiment_analysis=sentiment_info, text_files=text_files, audio_files=audio_files)

@app.route('/scripts.js', methods=['GET'])
def serve_js():
    return send_file('./script.js')

@app.route('/text_files/<filename>')
def serve_text_file(filename):
    return send_from_directory(app.config['TEXT_UPLOADS'], filename)

if __name__ == '__main__':
    app.run(debug=True)

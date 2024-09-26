from datetime import datetime
from flask import Flask, flash, render_template, request, redirect, url_for, send_file, send_from_directory
from google.cloud import texttospeech
from google.cloud import speech
import os

tts_client = texttospeech.TextToSpeechClient()
speech_client = speech.SpeechClient()

app = Flask(__name__)
app.secret_key = 'sandya'

UPLOAD_FOLDER = 'upload'
AUDIO_FOLDER = 'audio'
ALLOWED_EXTENSIONS = {'wav', 'txt', 'mp3'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['AUDIO_FOLDER'] = AUDIO_FOLDER


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_files(loc):
    files = []
    for filename in os.listdir(loc):
        if allowed_file(filename):
            files.append(filename)
    files.sort(reverse=True)
    return files

@app.route('/tts/<filename>')
def get_audio(filename):
    return send_from_directory(app.config['AUDIO_FOLDER'], filename, mimetype='audio/mpeg')

@app.route('/')
def index():
    files = get_files(UPLOAD_FOLDER)
    audio = get_files(AUDIO_FOLDER)
    return render_template('index.html', files=files, audios=audio)

@app.route('/upload', methods=['POST'])
def upload_audio():
    audio_file = request.files.get('audio_data')

    if not audio_file or audio_file.filename == '':
        flash('No audio file selected')
        return redirect(url_for('index'))

    timestamp = datetime.now().strftime("%Y%m%d-%I%M%S")
    filename = f"audio_{timestamp}.wav"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    audio_file.save(file_path)
    flash(f'Audio file "{filename}" uploaded successfully')

    try:
        with io.open(file_path, 'rb') as audio_file:
            content = audio_file.read()

        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.MP3,
            sample_rate_hertz=24000,
            language_code="en-US",
        )

        response = speech_client.recognize(config=config, audio=audio)

        if response.results:
            transcription_result = response.results[0].alternatives[0].transcript
        else:
            transcription_result = "No transcription available."
    except Exception as e:
        print(f"Error during transcription: {e}")
        transcription_result = "Error occurred during transcription."

    text_filename = os.path.splitext(file_path)[0] + ".txt"
    with open(text_filename, "w") as txt_file:
        txt_file.write(transcription_result)

    return render_template('index.html', transcription=transcription_result)



@app.route('/upload/<filename>')
def view_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/upload_text', methods=['POST'])
def upload_text():
    text = request.form['text']
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US", ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
    )
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)

    response = tts_client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )

    filename = "tts_" + datetime.now().strftime("%Y%m%d-%I%M%S") + ".mp3"
    audio_file_path = os.path.join(app.config['AUDIO_FOLDER'], filename)
    with open(audio_file_path, "wb") as out:
        out.write(response.audio_content)
        print(f'Audio content written to file "{filename}"')

    flash(f'Audio generated and saved as {filename}')
    return redirect('/')

@app.route('/script.js', methods=['GET'])
def scripts_js():
    return send_file('./script.js')

if __name__ == '__main__':
    app.run(debug=True)

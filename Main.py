from flask import Flask, render_template, request, jsonify, send_file
import pytchat
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import asyncio
import threading
import yt_dlp
from moviepy.editor import VideoFileClip
import os

app = Flask(__name__)

monitoring_tasks = {}

def get_video_id(url):
    parsed_url = urlparse(url)
    if parsed_url.netloc == 'youtu.be':
        return parsed_url.path[1:]
    elif parsed_url.netloc in ('www.youtube.com', 'youtube.com'):
        if parsed_url.path == '/watch':
            return parse_qs(parsed_url.query)['v'][0]
        elif parsed_url.path.startswith('/live/'):
            return parsed_url.path.split('/')[2].split('?')[0]
    return None

async def monitor_chat(url, callback):
    video_id = get_video_id(url)
    if not video_id:
        callback({"error": "Invalid YouTube live stream URL"})
        return

    try:
        chat = pytchat.create(video_id=video_id)
        callback({"message": f"Started monitoring {url}"})

        while chat.is_alive():
            for c in chat.get().sync_items():
                if c.message == '-clip':
                    timestamp = datetime.strptime(c.datetime, "%Y-%m-%d %H:%M:%S")
                    callback({
                        "timestamp": timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                        "message": "Clip command received"
                    })
            await asyncio.sleep(1)

    except Exception as e:
        callback({"error": f"Error: {str(e)}"})

def run_monitor_task(url, callback):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(monitor_chat(url, callback))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/monitor', methods=['POST'])
def monitor():
    url = request.form.get('url')
    if not url:
        return jsonify({"error": "URL is required"}), 400

    task_id = len(monitoring_tasks) + 1
    result = {"task_id": task_id, "status": "started"}

    def callback(data):
        if task_id in monitoring_tasks:
            monitoring_tasks[task_id].append(data)

    monitoring_tasks[task_id] = []
    thread = threading.Thread(target=run_monitor_task, args=(url, callback))
    thread.daemon = True
    thread.start()

    return jsonify(result)

@app.route('/status/<int:task_id>')
def status(task_id):
    if task_id in monitoring_tasks:
        return jsonify(monitoring_tasks[task_id])
    else:
        return jsonify({"error": "Task not found"}), 404

@app.route('/clip', methods=['POST'])
def clip():
    url = request.form.get('url')
    timestamp1 = request.form.get('timestamp1')
    timestamp2 = request.form.get('timestamp2')

    if not url or not timestamp1 or not timestamp2:
        return jsonify({"error": "URL, timestamp1, and timestamp2 are required"}), 400

    try:
        # Download the video
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': 'downloaded_video.%(ext)s',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info)

        # Convert timestamps to seconds
        t1 = sum(int(x) * 60 ** i for i, x in enumerate(reversed(timestamp1.split(':'))))
        t2 = sum(int(x) * 60 ** i for i, x in enumerate(reversed(timestamp2.split(':'))))

        # Extract clip
        clip = VideoFileClip(video_path).subclip(t1, t2)
        clip_path = 'clip.mp4'
        clip.write_videofile(clip_path)

        # Clean up
        os.remove(video_path)

        return send_file(clip_path, as_attachment=True)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
    

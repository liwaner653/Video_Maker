# Video_Maker
Generate 16-grid thumbnail. Extract audio from the video. Then use Whisper to generate srt file. Finally combine audio, srt file and thumbnail together into a video.

# How to run

1. Run generate_json.py and input the folder path, a **json.json** generated in the same folder.
```
python src/test/generate_json.py
```

2. Modify the **JSON_PATH** in main.py and then run it

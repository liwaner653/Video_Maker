# Video_Maker
Generate 16-grid thumbnail. Extract audio from the video. Then use Whisper to generate srt file. Finally combine audio, srt file and thumbnail together into a video.

# How to run

1. Run input_parser.py and input the folder path, a **json.json** generated in the same folder.
```
python input_parser.py
```

2. Modify the **JSON_PATH** in main.py and then run(F5) main.py
> If use ``python generate_subtitles.py``, it will return some error, but it's ok when I click **F5** in VSCode.

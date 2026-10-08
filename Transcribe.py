import os
import json
import argparse
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed
from faster_whisper import WhisperModel

MALAYSIA_TZ = ZoneInfo("Asia/Kuala_Lumpur")
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma"}

def format_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

def get_current_malaysia_time():
    return datetime.now(MALAYSIA_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")

def get_output_paths(audio_path):
    abs_path = os.path.abspath(audio_path)
    path_parts = abs_path.split(os.sep)
    
    # Preserve relative path structure if 'Audios' or general root is used
    if "Audios" in path_parts:
        audios_index = path_parts.index("Audios")
        rel_parts = path_parts[audios_index + 1:]
        rel_path = os.path.join(*rel_parts)
    else:
        # Fallback to relative from current working directory or filename
        rel_path = os.path.basename(audio_path)

    rel_no_ext, _ = os.path.splitext(rel_path)
    output_dir = os.path.join("Transcriptions", rel_no_ext)
    os.makedirs(output_dir, exist_ok=True)
    
    return {
        "json": os.path.join(output_dir, "T.json"),
        "srt": os.path.join(output_dir, "T.srt"),
        "txt": os.path.join(output_dir, "T.txt"),
        "tlog": os.path.join(output_dir, "T.tlog")
    }

def find_audio_files(target_path, max_depth):
    audio_files = []
    target_path = os.path.abspath(target_path)
    
    if os.path.isfile(target_path):
        if os.path.splitext(target_path)[1].lower() in AUDIO_EXTENSIONS:
            return [target_path]
        return []

    base_depth = len(target_path.rstrip(os.sep).split(os.sep))
    
    for root, dirs, files in os.walk(target_path):
        current_depth = len(root.rstrip(os.sep).split(os.sep)) - base_depth
        if max_depth is not -1 and current_depth > max_depth:
            # Prune directories exceeding max depth
            dirs.clear()
            continue
            
        for file in files:
            if os.path.splitext(file)[1].lower() in AUDIO_EXTENSIONS:
                audio_files.append(os.path.join(root, file))
                
    return audio_files

def process_single_audio(audio_path, model_size, device, compute_type):
    start_time_monotonic = time.time()
    start_timestamp_str = get_current_malaysia_time()
    
    paths = get_output_paths(audio_path)
    
    print(f"[START] ({start_timestamp_str}) File: {audio_path}")
    
    try:
        # Load model per thread or globally (faster-whisper is thread-safe for inference)
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
        segments_iter, info = model.transcribe(audio_path, beam_size=5, word_timestamps=True)

        segments = []
        full_text_parts = []
        
        with open(paths["tlog"], "w", encoding="utf-8") as log_file:
            log_file.write(f"Start Time (Malaysia): {start_timestamp_str}\n")
            log_file.write(f"Detected Language: {info.language} (Prob: {info.language_probability:.2f})\n")
            log_file.write("-" * 65 + "\n")

            for i, seg in enumerate(segments_iter, start=1):
                word_count = len(seg.words) if seg.words else 0
                time_badge = f"[{format_time(seg.start)} --> {format_time(seg.end)}]"
                log_line = f"Segment #{i:<3} {time_badge} | Words: {word_count:<2} | Text: {seg.text.strip()}"
                
                log_file.write(log_line + "\n")
                log_file.flush()

                segments.append({
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text,
                    "words": [{"word": w.word, "start": w.start, "end": w.end} for w in (seg.words or [])]
                })
                full_text_parts.append(seg.text.strip())

        result = {"language": info.language, "segments": segments}

        # Export JSON
        with open(paths["json"], "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=4)

        # Export TXT
        with open(paths["txt"], "w", encoding="utf-8") as f:
            f.write(" ".join(full_text_parts))

        # Export SRT
        with open(paths["srt"], "w", encoding="utf-8") as f:
            for idx, segment in enumerate(segments, start=1):
                s_str = format_time(segment["start"])
                e_str = format_time(segment["end"])
                f.write(f"{idx}\n{s_str} --> {e_str}\n{segment['text'].strip()}\n\n")

        end_time_monotonic = time.time()
        end_timestamp_str = get_current_malaysia_time()
        elapsed_seconds = end_time_monotonic - start_time_monotonic
        
        print(f"[DONE]  ({end_timestamp_str}) File: {audio_path} | Time Taken: {elapsed_seconds:.2f}s")
        return {"file": audio_path, "success": True, "elapsed": elapsed_seconds}

    except Exception as e:
        print(f"[ERROR] Failed processing {audio_path}: {str(e)}")
        return {"file": audio_path, "success": False, "error": str(e)}

def main():
    parser = argparse.ArgumentParser(description="Batch transcribe audio files in parallel with depth control.")
    parser.add_argument("paths", nargs="+", type=str, help="Directories or audio files to process")
    parser.add_argument("-d", "--depth", type=int, default=-1, help="Max search depth for directories (-1 for unlimited)")
    parser.add_argument("-w", "--workers", type=int, default=3, help="Parallel queue pool size (default: 3)")
    parser.add_argument("--model", type=str, default="base", help="Whisper model size")
    parser.add_argument("--device", type=str, default="cpu", help="Device (cpu or cuda)")
    parser.add_argument("--compute", type=str, default="int8", help="Compute type (int8, float16)")

    args = parser.parse_args()

    # Collect all unique audio files from all input arguments
    all_audio_files = []
    for p in args.paths:
        found = find_audio_files(p, args.depth)
        all_audio_files.extend(found)

    # Deduplicate
    all_audio_files = list(set(all_audio_files))

    if not all_audio_files:
        print("No audio files found matching the criteria.")
        return

    print(f"\n[Batch Start] Found {len(all_audio_files)} audio file(s). Running with concurrency pool = {args.workers}")
    print("=" * 70)

    batch_start_time = time.time()
    success_count = 0

    # Parallel Queue Pool Execution
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(process_single_audio, af, args.model, args.device, args.compute): af 
            for af in all_audio_files
        }

        for future in as_completed(futures):
            res = future.result()
            if res["success"]:
                success_count += 1

    batch_elapsed = time.time() - batch_start_time
    print("=" * 70)
    print(f"[Batch Complete] Successfully processed {success_count}/{len(all_audio_files)} files in {batch_elapsed:.2f}s.")

if __name__ == "__main__":
    main()
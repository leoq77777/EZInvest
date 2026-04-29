import json
import httpx
import time

def test():
    url = "http://127.0.0.1:8080/api/chat/stream"
    payload = {"message": "分析一下苹果公司本周的表现", "session_id": "test-terminal"}
    
    print(f"\n[Connecting to {url}...]\n")
    start_time = time.time()
    
    try:
        with httpx.stream("POST", url, json=payload, timeout=60.0) as response:
            current_event = None
            for line in response.iter_lines():
                if line.startswith("event: "):
                    current_event = line[7:].strip()
                elif line.startswith("data: ") and current_event:
                    data = json.loads(line[6:])
                    elapsed = time.time() - start_time
                    print(f"[{elapsed:4.1f}s] EVENT: {current_event:12} | DATA: {json.dumps(data, ensure_ascii=False)}")
                    current_event = None
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    test()

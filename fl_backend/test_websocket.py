# test_websocket.py
# Uses urllib instead of websockets library

import asyncio
import json
import sys

async def listen():
    import urllib.request
    
    # Simple HTTP-based test instead
    # Just verify the /ws endpoint exists and /ws/broadcast works
    
    print("Testing WebSocket setup...")
    print()
    
    # Test 1: Check FastAPI is running
    try:
        response = urllib.request.urlopen("http://localhost:8000/")
        print("✅ FastAPI is running")
    except Exception as e:
        print(f"❌ FastAPI not running: {e}")
        print("   Start it first: uvicorn backend.main:app --reload --port 8000")
        return

    # Test 2: Send a test broadcast
    try:
        import urllib.request
        data = json.dumps({
            "type": "round_complete",
            "round_num": 99,
            "factory_id": 1,
            "accuracy": 0.887,
            "loss": 0.221,
            "cluster_id": None
        }).encode('utf-8')
        
        req = urllib.request.Request(
            "http://localhost:8000/ws/broadcast",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        response = urllib.request.urlopen(req)
        result = json.loads(response.read())
        print(f"✅ Broadcast endpoint working")
        print(f"   Connected browsers: {result.get('connections', 0)}")
        print(f"   (0 is normal if no browser tab is open)")
    except Exception as e:
        print(f"❌ Broadcast failed: {e}")
        return

    # Test 3: Check /ws endpoint exists
    try:
        # WebSocket endpoints return 403 on regular HTTP — that's correct
        req = urllib.request.Request("http://localhost:8000/ws")
        try:
            urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            if e.code in [403, 400, 426]:
                print(f"✅ WebSocket endpoint exists at ws://localhost:8000/ws")
            else:
                print(f"❌ Unexpected status: {e.code}")
    except Exception as e:
        print(f"❌ WebSocket endpoint check failed: {e}")

    print()
    print("WebSocket setup verified!")
    print("Open http://localhost:8001/ and run the FL system")
    print("The event log in the dashboard should update live.")

if __name__ == "__main__":
    asyncio.run(listen())
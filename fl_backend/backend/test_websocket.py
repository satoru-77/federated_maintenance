# test_websocket.py
# Verifies WebSocket is working before wiring to dashboard
# Run: python test_websocket.py
# You should see events streaming in as FL rounds complete

import asyncio
import websockets
import json


async def listen():
    uri = "ws://localhost:8000/ws"
    print(f"Connecting to {uri}...")
    print("Waiting for FL round events...")
    print("(Start the FL system in another terminal)")
    print("-" * 40)

    async with websockets.connect(uri) as ws:
        print("Connected! Listening for events...\n")

        while True:
            try:
                message = await ws.recv()
                event = json.loads(message)

                if event.get("type") == "round_complete":
                    print(f"ROUND {event['round_num']:>3} | "
                          f"Factory {event['factory_id']} | "
                          f"Acc={event['accuracy']:.4f} | "
                          f"Cluster={event['cluster_id']}")

                elif event.get("type") == "cluster_assigned":
                    print(f"CLUSTER | Factory {event['factory_id']} "
                          f"→ Cluster {event['cluster_id']} "
                          f"(k={event['k_value']}, "
                          f"silhouette={event['silhouette_score']:.3f})")

                else:
                    print(f"EVENT: {event}")

            except Exception as e:
                print(f"Connection error: {e}")
                break


if __name__ == "__main__":
    asyncio.run(listen())
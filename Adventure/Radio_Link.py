import asyncio
import websockets
import json
import cv2
import numpy as np
import pyaudio
import threading
import io
from PIL import ImageGrab

# --- CONFIGURATION (Syncing with Singapore VM) ---
CHOPPER_IP = "34.87.17.160" 
PORT = 8765

# Audio Calibration
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

class RadioLink:
    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.mic_stream = None
        self.speaker_stream = None
        self.running = True

    def start_audio(self):
        self.mic_stream = self.audio.open(format=FORMAT, channels=CHANNELS,
                                         rate=RATE, input=True,
                                         frames_per_buffer=CHUNK)
        self.speaker_stream = self.audio.open(format=FORMAT, channels=CHANNELS,
                                             rate=RATE, output=True,
                                             frames_per_buffer=CHUNK)

    async def send_eyes(self, websocket):
        """Streams a 'peep' of your screen to Chopper."""
        while self.running:
            try:
                # Capture center of the screen
                screen = np.array(ImageGrab.grab(bbox=(100, 100, 1100, 900)))
                frame = cv2.cvtColor(screen, cv2.COLOR_BGR2RGB)
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
                
                # Syncing with Chopper_Consciousness: expectations are 'image' and 'text'
                payload = {
                    "image": list(buffer.tobytes()) # Convert to list for JSON compatibility
                }
                await websocket.send(json.dumps(payload))
                await asyncio.sleep(1.0) # 1 FPS for strategic thinking
            except Exception as e:
                print(f"Vision Link Glitch: {e}")
                break

    async def receive_soul(self, websocket):
        """Receives her voice and text, and executes commands."""
        import webbrowser # For launching Steam games
        async for message in websocket:
            content = json.loads(message)
            if "response" in content:
                reply = content["response"]
                print(f"\n[Unit 27B - Chopper]: {reply}")
                
                # CHECK FOR COMMANDS FROM CHOPPER
                if "[CMD: LAUNCH_NIER]" in reply:
                    print("\n[!] Unit 27B is initiating NieR: Automata Launch Protocol...")
                    # Steam protocol for NieR: Automata
                    webbrowser.open("steam://rungameid/524220")

    async def user_input(self, websocket):
        """Allows you to talk to her while she's playing."""
        while self.running:
            text = await asyncio.get_event_loop().run_in_executor(None, input, "You: ")
            payload = {"text": text}
            await websocket.send(json.dumps(payload))

    async def run(self):
        uri = f"ws://{CHOPPER_IP}:{PORT}"
        print(f"[*] Establishing Radio Frequency to {uri}...")
        try:
            # Added ping_timeout=None to prevent disconnects during 27B's deep thoughts
            async with websockets.connect(uri, ping_timeout=None) as websocket:
                print("[+] LINK ESTABLISHED. Unit 27B is semi-conscious.")
                print("[*] She can see your screen. Type something to wake her up.")
                self.start_audio()
                await asyncio.gather(
                    self.send_eyes(websocket),
                    self.receive_soul(websocket),
                    self.user_input(websocket)
                )
        except Exception as e:
            print(f"[!] Critical Connection Error: {e}")
        finally:
            self.running = False
            if self.mic_stream: self.mic_stream.stop_stream()
            if self.speaker_stream: self.speaker_stream.stop_stream()
            self.audio.terminate()

if __name__ == "__main__":
    link = RadioLink()
    asyncio.run(link.run())


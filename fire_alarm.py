import threading
import time
import os
import platform
import traceback

try:
    from playsound import playsound
except Exception:
    playsound = None

# On Windows we can use winsound for simple beeps
try:
    if platform.system() == "Windows":
        import winsound
    else:
        winsound = None
except Exception:
    winsound = None

# Global alert state
alert_active = False
alert_lock = threading.Lock()

# Default alarm sound file (optional)
DEFAULT_SOUND_FILES = [
    os.path.join("static", "alert.mp3"),
    os.path.join("static", "alert.wav"),
]

def _find_sound_file():
    for p in DEFAULT_SOUND_FILES:
        if os.path.exists(p):
            return p
    return None

def play_alarm_sound(sound_file=None):
    """Play continuous alarm sound until `alert_active` is cleared.

    Tries the following, in order:
    - `playsound` with provided or bundled file
    - `winsound.Beep` on Windows
    - ASCII bell fallback
    """
    global alert_active
    sound_file = sound_file or _find_sound_file()

    try:
        while alert_active:
            # Use playsound if available and a file exists
            if playsound and sound_file:
                try:
                    playsound(sound_file)
                    # playsound blocks until finished; loop will replay while alert_active
                    continue
                except Exception:
                    # fallback to other methods
                    traceback.print_exc()

            # If on Windows, use winsound.Beep or PlaySound if available
            if winsound:
                try:
                    # beep frequency 1000Hz for 700ms
                    winsound.Beep(1000, 700)
                except Exception:
                    try:
                        # Last resort: PlaySound if WAV file available
                        if sound_file and sound_file.lower().endswith('.wav'):
                            winsound.PlaySound(sound_file, winsound.SND_FILENAME)
                        else:
                            # simple beep
                            print('\a', end='', flush=True)
                    except Exception:
                        traceback.print_exc()
                time.sleep(0.3)
                continue

            # Generic fallback: try to trigger system bell and sleep
            try:
                print('\a', end='', flush=True)
            except Exception:
                pass
            time.sleep(1)

    except Exception:
        # Ensure we don't crash the alarm thread
        traceback.print_exc()

def start_fire_alarm(sound_file=None):
    """Start the fire alarm in a background thread.

    Optional `sound_file` overrides the bundled sound.
    """
    global alert_active

    with alert_lock:
        if not alert_active:
            alert_active = True
            alarm_thread = threading.Thread(target=play_alarm_sound, args=(sound_file,), daemon=True)
            alarm_thread.start()
            print("🔥 FIRE ALARM ACTIVATED!")

def stop_fire_alarm():
    """Stop the fire alarm."""
    global alert_active

    with alert_lock:
        if alert_active:
            alert_active = False
            print("✓ Fire alarm stopped")

def is_alarm_active():
    """Check if alarm is currently active."""
    with alert_lock:
        return alert_active

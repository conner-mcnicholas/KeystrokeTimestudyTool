from pynput import keyboard
import time
import csv
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Set tapping term threshold in seconds
TAPPING_TERM = 0.200  # 200 ms
# Number of words to input before triggering analysis
MAX_WORDS = 10

keydown_times = {}
durations = {}
overlaps = []
event_log = []

active_keys = {}
key_hold_periods = {}  # To help calculate overlaps more accurately

current_input = []
typed_word = ''

print(f"Type {MAX_WORDS} words. Key events are being tracked. Press ESC to abort.\n")

def on_press(key):
    global typed_word
    try:
        k = key.char
    except AttributeError:
        k = str(key)

    timestamp = time.time()
    event_log.append(['keydown', k, timestamp])

    if k not in keydown_times:
        keydown_times[k] = []
    keydown_times[k].append(timestamp)
    active_keys[k] = timestamp

def on_release(key):
    global typed_word, current_input

    try:
        k = key.char
    except AttributeError:
        k = str(key)

    timestamp = time.time()
    event_log.append(['keyup', k, timestamp])

    if k in active_keys:
        start_time = active_keys.pop(k)
        duration = timestamp - start_time
        if k not in durations:
            durations[k] = []
        durations[k].append((start_time, timestamp, duration))

        # Store hold period
        if k not in key_hold_periods:
            key_hold_periods[k] = []
        key_hold_periods[k].append((start_time, timestamp))

        # Now that we have a completed hold period, check for overlaps with other keys
        for other_key, periods in key_hold_periods.items():
            if other_key == k:
                continue
            for other_start, other_end in periods:
                overlap_start = max(start_time, other_start)
                overlap_end = min(timestamp, other_end)
                overlap_duration = overlap_end - overlap_start
                if overlap_duration > 0:
                    overlaps.append({
                        'key1': k,
                        'key2': other_key,
                        'start1': start_time,
                        'end1': timestamp,
                        'start2': other_start,
                        'end2': other_end,
                        'overlap_duration': overlap_duration
                    })

    if key == keyboard.Key.space:
        if typed_word:
            current_input.append(typed_word)
            typed_word = ''
            if len(current_input) >= MAX_WORDS:
                print("\nFinished input.")
                print("Current input:", ' '.join(current_input))
                return False
    elif key == keyboard.Key.esc:
        print("Aborted.")
        print("Current input:", ' '.join(current_input))
        return False
    elif key == keyboard.Key.enter:
        current_input.append(typed_word)
        typed_word = ''
        if len(current_input) >= MAX_WORDS:
            return False
    elif hasattr(key, 'char') and key.char is not None:
        typed_word += key.char

# Start listener
with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()

# Display results
print("\n--- Key Durations ---")
for key, entries in durations.items():
    for i, (start, end, dur) in enumerate(entries):
        print(f"{key} [{i}]: {dur:.4f} sec")

print("\n--- Overlaps with Durations ---")
for o in overlaps:
    print(f"{o['key1']} ({o['start1']:.4f}-{o['end1']:.4f}) overlapped with {o['key2']} "
          f"({o['start2']:.4f}-{o['end2']:.4f}) for {o['overlap_duration']:.4f} sec")

# Save key durations
with open('key_durations.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Key', 'Start Time', 'End Time', 'Duration (s)'])
    for key, entries in durations.items():
        for start, end, dur in entries:
            writer.writerow([key, start, end, f"{dur:.6f}"])

# Save overlaps
with open('key_overlaps.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow([
        'Key1', 'Start1', 'End1',
        'Key2', 'Start2', 'End2',
        'Overlap Duration (s)'
    ])
    for o in overlaps:
        writer.writerow([
            o['key1'], o['start1'], o['end1'],
            o['key2'], o['start2'], o['end2'],
            f"{o['overlap_duration']:.6f}"
        ])

print("\nResults saved to:")
print(" - key_durations.csv")
print(" - key_overlaps.csv")

print("\nTIMELINE PLOT OF KEYSTROKES:\n")

# Load key durations from uploaded CSV
csv_path = 'key_durations.csv'
key_durations = []
with open(csv_path, newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        key_durations.append({
            'key': row['Key'],
            'start': float(row['Start Time']),
            'end': float(row['End Time']),
            'duration': float(row['Duration (s)'])
        })

# Normalize start times to begin at 0
start_offset = min(kd['start'] for kd in key_durations)
for kd in key_durations:
    kd['start'] -= start_offset
    kd['end'] -= start_offset

# Assign each key a y-position
key_order = list(dict.fromkeys(kd['key'] for kd in key_durations))
key_positions = {k: i for i, k in enumerate(key_order)}

# Build plot with conditional coloring and black outlines for overlaps
fig, ax = plt.subplots(figsize=(12, 6))

# Plot bars and collect all time ranges per key
for kd in key_durations:
    color = 'tab:red' if kd['duration'] > TAPPING_TERM else 'tab:blue'
    ax.broken_barh(
        [(kd['start'], kd['duration'])],
        (key_positions[kd['key']], 0.8),
        facecolors=color
    )

# Check for overlapping intervals and draw black outlines for the overlap portion
for i, kd1 in enumerate(key_durations):
    for j, kd2 in enumerate(key_durations):
        if i >= j:
            continue  # Avoid duplicates
        # Check overlap
        start1, end1 = kd1['start'], kd1['end']
        start2, end2 = kd2['start'], kd2['end']
        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)
        if overlap_start < overlap_end:
            # Draw black rectangle for the overlapping portion of kd1
            rect1 = patches.Rectangle(
                (overlap_start, key_positions[kd1['key']]),
                overlap_end - overlap_start,
                0.8,
                linewidth=1,
                edgecolor='black',
                facecolor='none'
            )
            ax.add_patch(rect1)
            # Draw black rectangle for the overlapping portion of kd2
            rect2 = patches.Rectangle(
                (overlap_start, key_positions[kd2['key']]),
                overlap_end - overlap_start,
                0.8,
                linewidth=1,
                edgecolor='black',
                facecolor='none'
            )
            ax.add_patch(rect2)

# Labeling
ax.set_yticks(list(key_positions.values()))
ax.set_yticklabels(list(key_positions.keys()))
ax.set_xlabel('Time (s)')
ax.set_title(f'Key Hold Timeline (Red = Held > {int(TAPPING_TERM*1000)}ms, Black Border = Overlap)')
ax.grid(True, axis='x', linestyle='--', alpha=0.5)

plt.tight_layout()
plt.show()

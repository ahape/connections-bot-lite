#!/opt/homebrew/bin/python3.11
from flask import Flask
from flask import request
import logging, re, requests, os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_puzzle_number(puzzle_result):
  # Extract and return the puzzle number from the puzzle result string
  match = re.search(r"Puzzle #(\d+)", puzzle_result)
  return int(match.group(1)) if match else None

def is_puzzle_message(event):
  return (
    event['event']['type'] == 'message' and
    'text' in event['event'] and
    'Connections\nPuzzle #' in event['event']['text']
  )

def is_valid_score_message(text, square_dict):
  # Replace square names in text with single-character emojis
  for square_name, square_char in square_dict.items():
    text = text.replace(square_name, square_char)

  # Identify and count the squares
  squares = "🟪🟦🟨🟩"
  square_count = sum(1 for char in text if char in squares)

  # Check the conditions
  return square_count >= 16 and square_count % 4 == 0

def calculate_score(text):
  square_dict = {
    ":large_purple_square:": "🟪",
    ":large_blue_square:": "🟦",
    ":large_yellow_square:": "🟨",
    ":large_green_square:": "🟩"
  }
  score = 0

  # Replace square names in text with single-character emojis
  for square_name, square_char in square_dict.items():
    text = text.replace(square_name, square_char)

  # Filter squares from the text and chunk them into attempts of size 4
  squares = "🟪🟦🟨🟩"
  flat = [t for t in text if t in squares]
  attempts = [flat[i:i + 4] for i in range(0, len(flat), 4)]

  # Scoring logic
  for _round, guesses in enumerate(attempts):
    inc = 0
    if all(g == "🟪" for g in guesses):
      inc += 10
    elif all(g == "🟦" for g in guesses):
      inc += 8
    elif all(g == "🟨" for g in guesses):
      inc += 6
    elif all(g == "🟩" for g in guesses):
      inc += 4
    if _round <= 4:
      inc *= (4 - _round)
    score += inc

  return score

def send_slack_message(channel, message):
  url = "https://slack.com/api/chat.postMessage"
  payload = {
    "channel": channel,
    "text": message,
  }
  headers = {
    "Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}",
    "Content-Type": "application/json"
  }
  requests.post(url, data=payload, headers=headers, timeout=20)

app = Flask(__name__)

@app.post("/slack/events")
def handle_slack_event():
  # TODO
  """
  slack_signature = request.headers.get("X-Slack-Signature")
  slack_request_timestamp = request.headers.get("X-Slack-Request-Timestamp")

  # Get request body
  body = request.body()
  body_str = body.decode()

  # Validate request
  req = str.encode(f"v0:{slack_request_timestamp}:") + body
  request_hash = 'v0=' + hmac.new(SLACK_SIGNING_SECRET, req, hashlib.sha256).hexdigest()

  if not hmac.compare_digest(request_hash, slack_signature):
    raise HTTPException(status_code=400, detail="Invalid request")
  """

  # Parse Slack event data
  event_data = request.json

  # URL Verification Challenge
  if "challenge" in event_data:
    return {"challenge": event_data["challenge"]}

  return process_event(event_data)

def process_puzzle_message(event):
  message_text = event['event']['text']

  # Check for valid message
  square_dict = {
    ":large_purple_square:": "🟪",
    ":large_blue_square:": "🟦",
    ":large_yellow_square:": "🟨",
    ":large_green_square:": "🟩"
  }
  if not is_valid_score_message(message_text, square_dict):
    # Log a message or notify the user in the channel
    logger.warning(f"Invalid puzzle message from user {event['event']['user']}: {message_text}")

    return "invalid"

  # Calculate score
  return calculate_score(message_text)

def process_event(event):
  # Log the entire event payload
  logger.info(f"Received event: {event}")

  # Check if the event is a message and contains a puzzle result
  if is_puzzle_message(event):
    logger.info("Identified as a puzzle message")

    result = process_puzzle_message(event)

    logger.info(f"Processing result: {result}")

    if result == "invalid":
      send_slack_message(event['event']['channel'],
        "Invalid puzzle share. Report to Jim for his quarterly Ooni cleaning immediately.")

    # If successful, calculate and send score
    else:
      score = calculate_score(event['event']['text'])
      logger.info(f"Calculated score: {score}")

      send_slack_message(event['event']['channel'],
        f"Good job! Your score is {score}.")
  else:
    logger.info("Not identified as a puzzle message.")

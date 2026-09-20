import os
import sys
import urllib.parse

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)
    except Exception:
        pass
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/tasks',
    'https://mail.google.com/',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/contacts',
]

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
EXTERNAL_CONFIG_DIR = os.path.expanduser("~/.gemini/config/google_workspace")

def resolve_credentials_path():
    # 1. Environment variable override
    env_creds = os.environ.get("GOOGLE_WORKSPACE_CREDENTIALS_PATH")
    if env_creds and os.path.exists(env_creds):
        return env_creds
    # 2. Sovereign external quarantine location (~/.gemini/config/google_workspace/credentials.json)
    external_creds = os.path.join(EXTERNAL_CONFIG_DIR, 'credentials.json')
    if os.path.exists(external_creds):
        return external_creds
    # 3. Local working tree / legacy mirrors (fallback)
    local_creds = os.path.join(WORKSPACE_DIR, 'credentials.json')
    if os.path.exists(local_creds):
        return local_creds
    parent_creds = os.path.join(os.path.dirname(WORKSPACE_DIR), 'credentials.json')
    if os.path.exists(parent_creds):
        return parent_creds
    legacy_mcp_creds = os.path.expanduser("~/.gemini/google-workspace-mcp/credentials.json")
    if os.path.exists(legacy_mcp_creds):
        return legacy_mcp_creds
    return external_creds

def resolve_token_path():
    # 1. Environment variable override
    env_token = os.environ.get("GOOGLE_WORKSPACE_TOKEN_PATH")
    if env_token and os.path.exists(env_token):
        return env_token
    # 2. Sovereign external quarantine location (~/.gemini/config/google_workspace/token.json)
    external_token = os.path.join(EXTERNAL_CONFIG_DIR, 'token.json')
    if os.path.exists(external_token):
        return external_token
    # 3. Local working tree / legacy mirrors (fallback)
    local_token = os.path.join(WORKSPACE_DIR, 'token.json')
    if os.path.exists(local_token):
        return local_token
    parent_token = os.path.join(os.path.dirname(WORKSPACE_DIR), 'token.json')
    if os.path.exists(parent_token):
        return parent_token
    legacy_mcp_token = os.path.expanduser("~/.gemini/google-workspace-mcp/token.json")
    if os.path.exists(legacy_mcp_token):
        return legacy_mcp_token
    return external_token

CREDENTIALS_PATH = resolve_credentials_path()
TOKEN_PATH = resolve_token_path()
PORT = 8088
REDIRECT_URI = f'http://localhost:{PORT}/'

def authenticate():
    creds = None
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        refresh_succeeded = False
        if creds and creds.expired and creds.refresh_token:
            print("Attempting to refresh expired OAuth token...", flush=True)
            try:
                creds.refresh(Request())
                refresh_succeeded = True
            except Exception as e:
                print(f"Token refresh failed ({e}). Proceeding to fresh OAuth flow...", flush=True)
                creds = None

        if not refresh_succeeded:
            if not os.path.exists(CREDENTIALS_PATH):
                print(f"ERROR: credentials.json not found at {CREDENTIALS_PATH}", flush=True)
                print(f"Please place credentials.json in external quarantine:\n  {os.path.join(EXTERNAL_CONFIG_DIR, 'credentials.json')}\n(or set GOOGLE_WORKSPACE_CREDENTIALS_PATH).", flush=True)
                return None

            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH,
                scopes=SCOPES
            )

            prompt_msg = (
                "\n========================================================\n"
                "AUTH_URL: {url}\n"
                "========================================================\n"
                "Please visit the URL above in your browser to complete authorization.\n"
            )

            creds = flow.run_local_server(
                port=PORT,
                prompt='consent',
                access_type='offline',
                authorization_prompt_message=prompt_msg,
                open_browser=True
            )

        # Save to canonical token path in external quarantine
        os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
        with open(TOKEN_PATH, 'w', encoding='utf-8') as token_file:
            token_file.write(creds.to_json())
        print(f"SUCCESS: token.json saved to {TOKEN_PATH}", flush=True)

        # Sync to legacy external fallback if present, but NEVER write into git repo working tree
        legacy_mcp_token = os.path.expanduser("~/.gemini/google-workspace-mcp/token.json")
        if os.path.exists(os.path.dirname(legacy_mcp_token)) and legacy_mcp_token != TOKEN_PATH:
            try:
                with open(legacy_mcp_token, 'w', encoding='utf-8') as sf:
                    sf.write(creds.to_json())
                print(f"Synced token to legacy mirror: {legacy_mcp_token}", flush=True)
            except Exception:
                pass

    # Verify services
    print("\n--- Verifying Services ---", flush=True)
    
    # 1. Calendar
    try:
        cal = build('calendar', 'v3', credentials=creds)
        cal_list = cal.calendarList().list(maxResults=5).execute()
        print(f"1. Calendar API: OK (Found {len(cal_list.get('items', []))} calendars)", flush=True)
    except Exception as e:
        print(f"1. Calendar API: FAILED ({e})", flush=True)

    # 2. Tasks
    try:
        tasks = build('tasks', 'v1', credentials=creds)
        task_lists = tasks.tasklists().list(maxResults=5).execute()
        print(f"2. Tasks API: OK (Found {len(task_lists.get('items', []))} task lists)", flush=True)
    except Exception as e:
        print(f"2. Tasks API: FAILED ({e})", flush=True)

    # 3. Gmail
    try:
        gmail = build('gmail', 'v1', credentials=creds)
        profile = gmail.users().getProfile(userId='me').execute()
        print(f"3. Gmail API: OK (Email: {profile.get('emailAddress')}, Total Messages: {profile.get('messagesTotal')})", flush=True)
    except Exception as e:
        print(f"3. Gmail API: FAILED ({e})", flush=True)

    # 4. Drive
    try:
        drive = build('drive', 'v3', credentials=creds)
        files = drive.files().list(pageSize=5, fields="files(id, name)").execute()
        print(f"4. Drive API: OK (Found {len(files.get('files', []))} recent files)", flush=True)
    except Exception as e:
        print(f"4. Drive API: FAILED ({e})", flush=True)

    # 5. Docs
    try:
        docs = build('docs', 'v1', credentials=creds)
        print("5. Docs API: OK (Client ready)", flush=True)
    except Exception as e:
        print(f"5. Docs API: FAILED ({e})", flush=True)

    # 6. Sheets
    try:
        sheets = build('sheets', 'v4', credentials=creds)
        print("6. Sheets API: OK (Client ready)", flush=True)
    except Exception as e:
        print(f"6. Sheets API: FAILED ({e})", flush=True)

    # 7. Contacts (People)
    try:
        people = build('people', 'v1', credentials=creds)
        conns = people.people().connections().list(resourceName='people/me', pageSize=5, personFields='names,emailAddresses').execute()
        print(f"7. Contacts API: OK (Found {len(conns.get('connections', []))} contacts)", flush=True)
    except Exception as e:
        print(f"7. Contacts API: FAILED ({e})", flush=True)

    print("\n--- All checks complete! ---", flush=True)
    return creds

if __name__ == '__main__':
    authenticate()

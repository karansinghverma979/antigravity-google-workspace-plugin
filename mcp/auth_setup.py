import os
import sys
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
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

def resolve_credentials_path():
    env_creds = os.environ.get("GOOGLE_WORKSPACE_CREDENTIALS_PATH")
    if env_creds and os.path.exists(env_creds):
        return env_creds
    local_creds = os.path.join(WORKSPACE_DIR, 'credentials.json')
    if os.path.exists(local_creds):
        return local_creds
    parent_creds = os.path.join(os.path.dirname(WORKSPACE_DIR), 'credentials.json')
    if os.path.exists(parent_creds):
        return parent_creds
    return local_creds

def resolve_token_path():
    env_token = os.environ.get("GOOGLE_WORKSPACE_TOKEN_PATH")
    if env_token and os.path.exists(env_token):
        return env_token
    local_token = os.path.join(WORKSPACE_DIR, 'token.json')
    if os.path.exists(local_token):
        return local_token
    parent_token = os.path.join(os.path.dirname(WORKSPACE_DIR), 'token.json')
    if os.path.exists(parent_token):
        return parent_token
    return local_token

CREDENTIALS_PATH = resolve_credentials_path()
TOKEN_PATH = resolve_token_path()
PORT = 8088
REDIRECT_URI = f'http://localhost:{PORT}/'

auth_code = None

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        if 'code' in params:
            auth_code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = """
            <html><body style="font-family: Arial; text-align: center; padding-top: 50px;">
            <h1 style="color: #2e7d32;">Authentication Successful!</h1>
            <p>You can close this tab and return to Antigravity.</p>
            </body></html>
            """
            self.wfile.write(html.encode('utf-8'))
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Authentication failed or cancelled.")

    def log_message(self, format, *args):
        pass

def authenticate():
    global auth_code
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
                return None

            flow = Flow.from_client_secrets_file(
                CREDENTIALS_PATH,
                scopes=SCOPES,
                redirect_uri=REDIRECT_URI
            )

            auth_url, _ = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )

            print(f"\n========================================================", flush=True)
            print(f"AUTH_URL: {auth_url}", flush=True)
            print(f"========================================================\n", flush=True)

            # Open in default Windows browser
            os.system(f'cmd.exe /c start "" "{auth_url}"')

            # Start local server to capture callback
            httpd = HTTPServer(('localhost', PORT), OAuthCallbackHandler)
            print(f"Waiting for authorization on localhost:{PORT}...", flush=True)
            while not auth_code:
                httpd.handle_request()

            flow.fetch_token(code=auth_code)
            creds = flow.credentials

        with open(TOKEN_PATH, 'w', encoding='utf-8') as token_file:
            token_file.write(creds.to_json())
        print(f"SUCCESS: token.json saved to {TOKEN_PATH}", flush=True)

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

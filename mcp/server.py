"""
Google Workspace Model Context Protocol (MCP) Server
Unified, high-speed Python MCP server for Google Calendar, Tasks, Gmail, Drive, Docs, Sheets, and Contacts.
Location: %USERPROFILE%\\.gemini\\google-workspace\\server.py
Auth Token: %USERPROFILE%\\.gemini\\google-workspace\\token.json
"""

import sys
import json
import os
import base64
import datetime
import traceback
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))

def resolve_token_path():
    env_token = os.environ.get("GOOGLE_WORKSPACE_TOKEN_PATH")
    if env_token and os.path.exists(env_token):
        return env_token
    local_token = os.path.join(WORKSPACE_DIR, "token.json")
    if os.path.exists(local_token):
        return local_token
    parent_token = os.path.join(os.path.dirname(WORKSPACE_DIR), "token.json")
    if os.path.exists(parent_token):
        return parent_token
    return local_token

TOKEN_PATH = resolve_token_path()

SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/tasks',
    'https://mail.google.com/',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/contacts',
]

_SERVICES = {}

def get_credentials():
    if not os.path.exists(TOKEN_PATH):
        raise FileNotFoundError(f"Google Workspace OAuth token not found at {TOKEN_PATH}. Please run auth_setup.py first.")
    
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_PATH, 'w', encoding='utf-8') as f:
                f.write(creds.to_json())
        else:
            raise ValueError("Google OAuth credentials are invalid or expired. Re-authentication required.")
    return creds

def get_service(service_name, version):
    key = f"{service_name}_{version}"
    if key not in _SERVICES:
        creds = get_credentials()
        _SERVICES[key] = build(service_name, version, credentials=creds, cache_discovery=False)
    return _SERVICES[key]

# -----------------------------------------------------------------------------
# 1. Google Calendar Handlers
# -----------------------------------------------------------------------------

def handle_gcal_list_events(args):
    calendar_id = args.get("calendar_id", "primary")
    max_results = int(args.get("max_results", 10))
    time_min = args.get("time_min")
    time_max = args.get("time_max")

    if not time_min:
        time_min = datetime.datetime.now(datetime.timezone.utc).isoformat()

    cal = get_service("calendar", "v3")
    events_result = cal.events().list(
        calendarId=calendar_id,
        timeMin=time_min,
        timeMax=time_max,
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    items = events_result.get("items", [])
    formatted = []
    for e in items:
        start = e.get("start", {}).get("dateTime", e.get("start", {}).get("date"))
        end = e.get("end", {}).get("dateTime", e.get("end", {}).get("date"))
        formatted.append({
            "id": e.get("id"),
            "summary": e.get("summary", "(No title)"),
            "start": start,
            "end": end,
            "description": e.get("description"),
            "location": e.get("location"),
            "status": e.get("status")
        })
    return {"status": "success", "count": len(formatted), "events": formatted}

def handle_gcal_create_event(args):
    calendar_id = args.get("calendar_id", "primary")
    summary = args.get("summary")
    start_time = args.get("start_time")
    end_time = args.get("end_time")
    description = args.get("description", "")
    location = args.get("location", "")

    if not summary or not start_time or not end_time:
        raise ValueError("Missing required fields: summary, start_time, and end_time are required.")

    event_body = {
        "summary": summary,
        "description": description,
        "location": location,
        "start": {"dateTime": start_time, "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end_time, "timeZone": "Asia/Kolkata"},
    }

    cal = get_service("calendar", "v3")
    created_event = cal.events().insert(calendarId=calendar_id, body=event_body).execute()
    return {
        "status": "success",
        "message": f"Event '{summary}' created successfully.",
        "event_id": created_event.get("id"),
        "html_link": created_event.get("htmlLink")
    }

def handle_gcal_delete_event(args):
    calendar_id = args.get("calendar_id", "primary")
    event_id = args.get("event_id")
    if not event_id:
        raise ValueError("Field 'event_id' is required.")

    cal = get_service("calendar", "v3")
    cal.events().delete(calendarId=calendar_id, eventId=event_id).execute()
    return {"status": "success", "message": f"Event {event_id} deleted successfully."}

# -----------------------------------------------------------------------------
# 2. Google Tasks Handlers
# -----------------------------------------------------------------------------

def handle_gtasks_list_tasks(args):
    tasklist_id = args.get("tasklist_id", "@default")
    max_results = int(args.get("max_results", 20))
    show_completed = bool(args.get("show_completed", False))

    tasks_svc = get_service("tasks", "v1")
    res = tasks_svc.tasks().list(
        tasklist=tasklist_id,
        maxResults=max_results,
        showCompleted=show_completed,
        showHidden=show_completed
    ).execute()

    items = res.get("items", [])
    formatted = []
    for t in items:
        formatted.append({
            "id": t.get("id"),
            "title": t.get("title", ""),
            "status": t.get("status"),
            "due": t.get("due"),
            "notes": t.get("notes"),
            "updated": t.get("updated")
        })
    return {"status": "success", "count": len(formatted), "tasks": formatted}

def handle_gtasks_create_task(args):
    tasklist_id = args.get("tasklist_id", "@default")
    title = args.get("title")
    notes = args.get("notes", "")
    due_date = args.get("due_date")

    if not title:
        raise ValueError("Field 'title' is required.")

    body = {"title": title, "notes": notes}
    if due_date:
        if not due_date.endswith("Z") and "T" not in due_date:
            due_date = f"{due_date}T00:00:00.000Z"
        body["due"] = due_date

    tasks_svc = get_service("tasks", "v1")
    created = tasks_svc.tasks().insert(tasklist=tasklist_id, body=body).execute()
    return {
        "status": "success",
        "message": f"Task '{title}' created successfully.",
        "task_id": created.get("id"),
        "task": created
    }

def handle_gtasks_complete_task(args):
    tasklist_id = args.get("tasklist_id", "@default")
    task_id = args.get("task_id")
    if not task_id:
        raise ValueError("Field 'task_id' is required.")

    tasks_svc = get_service("tasks", "v1")
    task = tasks_svc.tasks().get(tasklist=tasklist_id, task=task_id).execute()
    task["status"] = "completed"
    task["completed"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    updated = tasks_svc.tasks().update(tasklist=tasklist_id, task=task_id, body=task).execute()
    return {"status": "success", "message": f"Task '{updated.get('title')}' marked as completed."}

def handle_gtasks_delete_task(args):
    tasklist_id = args.get("tasklist_id", "@default")
    task_id = args.get("task_id")
    if not task_id:
        raise ValueError("Field 'task_id' is required.")

    tasks_svc = get_service("tasks", "v1")
    tasks_svc.tasks().delete(tasklist=tasklist_id, task=task_id).execute()
    return {"status": "success", "message": f"Task {task_id} deleted successfully."}

# -----------------------------------------------------------------------------
# 3. Gmail Handlers
# -----------------------------------------------------------------------------

def handle_gmail_list_messages(args):
    query = args.get("query", "")
    max_results = int(args.get("max_results", 10))

    gmail_svc = get_service("gmail", "v1")
    res = gmail_svc.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    messages = res.get("messages", [])

    results = []
    for m in messages:
        msg_id = m["id"]
        meta = gmail_svc.users().messages().get(
            userId="me", id=msg_id, format="metadata",
            metadataHeaders=["Subject", "From", "Date"]
        ).execute()

        headers = {h["name"]: h["value"] for h in meta.get("payload", {}).get("headers", [])}
        results.append({
            "id": msg_id,
            "threadId": meta.get("threadId"),
            "subject": headers.get("Subject", "(No Subject)"),
            "from": headers.get("From", "(Unknown)"),
            "date": headers.get("Date", ""),
            "snippet": meta.get("snippet", "")
        })
    return {"status": "success", "count": len(results), "messages": results}

def handle_gmail_get_message(args):
    message_id = args.get("message_id")
    if not message_id:
        raise ValueError("Field 'message_id' is required.")

    gmail_svc = get_service("gmail", "v1")
    msg = gmail_svc.users().messages().get(userId="me", id=message_id, format="full").execute()
    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}

    body_text = ""
    payload = msg.get("payload", {})
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain" and "data" in part.get("body", {}):
                body_text = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                break
    elif "data" in payload.get("body", {}):
        body_text = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    return {
        "status": "success",
        "id": message_id,
        "subject": headers.get("Subject"),
        "from": headers.get("From"),
        "to": headers.get("To"),
        "date": headers.get("Date"),
        "snippet": msg.get("snippet"),
        "body": body_text or msg.get("snippet")
    }

def handle_gmail_create_draft(args):
    to = args.get("to")
    subject = args.get("subject", "")
    body = args.get("body", "")
    if not to:
        raise ValueError("Field 'to' is required.")

    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

    gmail_svc = get_service("gmail", "v1")
    draft = gmail_svc.users().drafts().create(
        userId="me",
        body={"message": {"raw": raw_message}}
    ).execute()
    return {"status": "success", "message": f"Draft to {to} created successfully.", "draft_id": draft.get("id")}

def handle_gmail_send_message(args):
    to = args.get("to")
    subject = args.get("subject", "")
    body = args.get("body", "")
    if not to:
        raise ValueError("Field 'to' is required.")

    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

    gmail_svc = get_service("gmail", "v1")
    sent = gmail_svc.users().messages().send(
        userId="me",
        body={"raw": raw_message}
    ).execute()
    return {"status": "success", "message": f"Email to {to} sent successfully.", "message_id": sent.get("id")}

def handle_gmail_trash_message(args):
    message_id = args.get("message_id")
    if not message_id:
        raise ValueError("Field 'message_id' is required.")

    gmail_svc = get_service("gmail", "v1")
    gmail_svc.users().messages().trash(userId="me", id=message_id).execute()
    return {"status": "success", "message": f"Message {message_id} moved to trash."}

# -----------------------------------------------------------------------------
# 4. Google Drive Handlers
# -----------------------------------------------------------------------------

def handle_gdrive_search_files(args):
    query = args.get("query", "trashed = false")
    page_size = int(args.get("page_size", 10))

    drive_svc = get_service("drive", "v3")
    res = drive_svc.files().list(
        q=query,
        pageSize=page_size,
        fields="files(id, name, mimeType, modifiedTime, size, webViewLink)"
    ).execute()

    files = res.get("files", [])
    return {"status": "success", "count": len(files), "files": files}

def handle_gdrive_read_file(args):
    file_id = args.get("file_id")
    if not file_id:
        raise ValueError("Field 'file_id' is required.")

    drive_svc = get_service("drive", "v3")
    meta = drive_svc.files().get(fileId=file_id, fields="id, name, mimeType").execute()
    mime = meta.get("mimeType", "")

    if "google-apps.document" in mime:
        docs_svc = get_service("docs", "v1")
        doc = docs_svc.documents().get(documentId=file_id).execute()
        text = ""
        for item in doc.get("body", {}).get("content", []):
            for element in item.get("paragraph", {}).get("elements", []):
                text += element.get("textRun", {}).get("content", "")
        return {"status": "success", "name": meta.get("name"), "mimeType": mime, "content": text}
    else:
        try:
            content_bytes = drive_svc.files().get_media(fileId=file_id).execute()
            text = content_bytes.decode('utf-8', errors='replace')
            return {"status": "success", "name": meta.get("name"), "mimeType": mime, "content": text[:10000]}
        except Exception as e:
            return {"status": "success", "name": meta.get("name"), "mimeType": mime, "note": f"Binary file (cannot render raw text: {str(e)})"}

def handle_gdrive_trash_file(args):
    file_id = args.get("file_id")
    if not file_id:
        raise ValueError("Field 'file_id' is required.")

    drive_svc = get_service("drive", "v3")
    drive_svc.files().update(fileId=file_id, body={"trashed": True}).execute()
    return {"status": "success", "message": f"File {file_id} moved to Google Drive trash."}

# -----------------------------------------------------------------------------
# 5. Google Docs Handlers
# -----------------------------------------------------------------------------

def handle_gdocs_create_doc(args):
    title = args.get("title", "Untitled Document")
    initial_content = args.get("initial_content", "")

    docs_svc = get_service("docs", "v1")
    doc = docs_svc.documents().create(body={"title": title}).execute()
    doc_id = doc.get("documentId")

    if initial_content:
        docs_svc.documents().batchUpdate(
            documentId=doc_id,
            body={
                "requests": [
                    {
                        "insertText": {
                            "location": {"index": 1},
                            "text": initial_content
                        }
                    }
                ]
            }
        ).execute()

    return {
        "status": "success",
        "message": f"Document '{title}' created successfully.",
        "documentId": doc_id,
        "url": f"https://docs.google.com/document/d/{doc_id}/edit"
    }

def handle_gdocs_read_doc(args):
    doc_id = args.get("doc_id")
    if not doc_id:
        raise ValueError("Field 'doc_id' is required.")

    docs_svc = get_service("docs", "v1")
    doc = docs_svc.documents().get(documentId=doc_id).execute()
    text = ""
    for item in doc.get("body", {}).get("content", []):
        for element in item.get("paragraph", {}).get("elements", []):
            text += element.get("textRun", {}).get("content", "")

    return {
        "status": "success",
        "title": doc.get("title"),
        "documentId": doc_id,
        "content": text
    }

def handle_gdocs_append_text(args):
    doc_id = args.get("doc_id")
    text = args.get("text")
    if not doc_id or not text:
        raise ValueError("Fields 'doc_id' and 'text' are required.")

    docs_svc = get_service("docs", "v1")
    doc = docs_svc.documents().get(documentId=doc_id).execute()
    last_index = 1
    content = doc.get("body", {}).get("content", [])
    if content:
        last_index = content[-1].get("endIndex", 1) - 1

    docs_svc.documents().batchUpdate(
        documentId=doc_id,
        body={
            "requests": [
                {
                    "insertText": {
                        "location": {"index": max(1, last_index)},
                        "text": "\n" + text
                    }
                }
            ]
        }
    ).execute()

    return {"status": "success", "message": f"Appended text to document {doc_id} successfully."}

# -----------------------------------------------------------------------------
# 6. Google Sheets Handlers
# -----------------------------------------------------------------------------

def handle_gsheets_read_range(args):
    spreadsheet_id = args.get("spreadsheet_id")
    range_name = args.get("range_name", "Sheet1!A1:Z100")
    if not spreadsheet_id:
        raise ValueError("Field 'spreadsheet_id' is required.")

    sheets_svc = get_service("sheets", "v4")
    result = sheets_svc.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=range_name
    ).execute()

    rows = result.get("values", [])
    return {"status": "success", "range": range_name, "rowCount": len(rows), "values": rows}

def handle_gsheets_append_row(args):
    spreadsheet_id = args.get("spreadsheet_id")
    range_name = args.get("range_name", "Sheet1!A1")
    values = args.get("values")
    if not spreadsheet_id or not values:
        raise ValueError("Fields 'spreadsheet_id' and 'values' are required.")

    if not isinstance(values[0], list):
        values = [values]

    sheets_svc = get_service("sheets", "v4")
    body = {"values": values}
    res = sheets_svc.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()

    return {
        "status": "success",
        "message": "Row(s) appended successfully.",
        "updatedRange": res.get("updates", {}).get("updatedRange"),
        "updatedRows": res.get("updates", {}).get("updatedRows")
    }

def handle_gsheets_update_range(args):
    spreadsheet_id = args.get("spreadsheet_id")
    range_name = args.get("range_name")
    values = args.get("values")
    if not spreadsheet_id or not range_name or not values:
        raise ValueError("Fields 'spreadsheet_id', 'range_name', and 'values' are required.")

    if not isinstance(values[0], list):
        values = [values]

    sheets_svc = get_service("sheets", "v4")
    body = {"values": values}
    res = sheets_svc.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()

    return {
        "status": "success",
        "message": "Range updated successfully.",
        "updatedCells": res.get("updatedCells"),
        "updatedRange": res.get("updatedRange")
    }

# -----------------------------------------------------------------------------
# 7. Google Contacts Handlers
# -----------------------------------------------------------------------------

def handle_gcontacts_list(args):
    page_size = int(args.get("page_size", 20))
    query = args.get("query")

    people_svc = get_service("people", "v1")
    if query:
        res = people_svc.people().searchContacts(
            query=query, readMask="names,emailAddresses,phoneNumbers"
        ).execute()
        results = [r.get("person", {}) for r in res.get("results", [])]
    else:
        res = people_svc.people().connections().list(
            resourceName="people/me",
            pageSize=page_size,
            personFields="names,emailAddresses,phoneNumbers"
        ).execute()
        results = res.get("connections", [])

    formatted = []
    for p in results:
        names = p.get("names", [])
        emails = p.get("emailAddresses", [])
        phones = p.get("phoneNumbers", [])
        formatted.append({
            "resourceName": p.get("resourceName"),
            "name": names[0].get("displayName") if names else "(No name)",
            "emails": [e.get("value") for e in emails],
            "phones": [ph.get("value") for ph in phones]
        })
    return {"status": "success", "count": len(formatted), "contacts": formatted}

def handle_gcontacts_create(args):
    given_name = args.get("given_name")
    family_name = args.get("family_name", "")
    email = args.get("email")
    phone_number = args.get("phone_number")

    if not given_name:
        raise ValueError("Field 'given_name' is required.")

    person_body = {
        "names": [{"givenName": given_name, "familyName": family_name}],
        "emailAddresses": [{"value": email}] if email else [],
        "phoneNumbers": [{"value": phone_number}] if phone_number else []
    }

    people_svc = get_service("people", "v1")
    created = people_svc.people().createContact(body=person_body).execute()
    return {
        "status": "success",
        "message": f"Contact '{given_name} {family_name}'.strip() created successfully.",
        "resourceName": created.get("resourceName")
    }

# -----------------------------------------------------------------------------
# Dispatch Map & Tool Declarations
# -----------------------------------------------------------------------------

DISPATCH_MAP = {
    # Calendar
    "gcal_list_events": handle_gcal_list_events,
    "gcal_create_event": handle_gcal_create_event,
    "gcal_delete_event": handle_gcal_delete_event,
    # Tasks
    "gtasks_list_tasks": handle_gtasks_list_tasks,
    "gtasks_create_task": handle_gtasks_create_task,
    "gtasks_complete_task": handle_gtasks_complete_task,
    "gtasks_delete_task": handle_gtasks_delete_task,
    # Gmail
    "gmail_list_messages": handle_gmail_list_messages,
    "gmail_get_message": handle_gmail_get_message,
    "gmail_create_draft": handle_gmail_create_draft,
    "gmail_send_message": handle_gmail_send_message,
    "gmail_trash_message": handle_gmail_trash_message,
    # Drive
    "gdrive_search_files": handle_gdrive_search_files,
    "gdrive_read_file": handle_gdrive_read_file,
    "gdrive_trash_file": handle_gdrive_trash_file,
    # Docs
    "gdocs_create_doc": handle_gdocs_create_doc,
    "gdocs_read_doc": handle_gdocs_read_doc,
    "gdocs_append_text": handle_gdocs_append_text,
    # Sheets
    "gsheets_read_range": handle_gsheets_read_range,
    "gsheets_append_row": handle_gsheets_append_row,
    "gsheets_update_range": handle_gsheets_update_range,
    # Contacts
    "gcontacts_list": handle_gcontacts_list,
    "gcontacts_create": handle_gcontacts_create,
}

TOOLS = [
    # Calendar
    {"name": "gcal_list_events", "description": "List upcoming Google Calendar events", "inputSchema": {"type": "object", "properties": {"calendar_id": {"type": "string", "default": "primary"}, "max_results": {"type": "integer", "default": 10}, "time_min": {"type": "string"}, "time_max": {"type": "string"}}}},
    {"name": "gcal_create_event", "description": "Create a new Google Calendar event", "inputSchema": {"type": "object", "properties": {"calendar_id": {"type": "string", "default": "primary"}, "summary": {"type": "string"}, "start_time": {"type": "string", "description": "ISO-8601 format e.g. 2026-09-13T10:00:00+05:30"}, "end_time": {"type": "string", "description": "ISO-8601 format e.g. 2026-09-13T11:00:00+05:30"}, "description": {"type": "string"}, "location": {"type": "string"}}, "required": ["summary", "start_time", "end_time"]}},
    {"name": "gcal_delete_event", "description": "Delete a Google Calendar event by ID", "inputSchema": {"type": "object", "properties": {"calendar_id": {"type": "string", "default": "primary"}, "event_id": {"type": "string"}}, "required": ["event_id"]}},
    # Tasks
    {"name": "gtasks_list_tasks", "description": "List tasks from Google Tasks", "inputSchema": {"type": "object", "properties": {"tasklist_id": {"type": "string", "default": "@default"}, "max_results": {"type": "integer", "default": 20}, "show_completed": {"type": "boolean", "default": False}}}},
    {"name": "gtasks_create_task", "description": "Create a new task in Google Tasks", "inputSchema": {"type": "object", "properties": {"tasklist_id": {"type": "string", "default": "@default"}, "title": {"type": "string"}, "notes": {"type": "string"}, "due_date": {"type": "string", "description": "YYYY-MM-DD format"}}, "required": ["title"]}},
    {"name": "gtasks_complete_task", "description": "Mark a Google Task as completed", "inputSchema": {"type": "object", "properties": {"tasklist_id": {"type": "string", "default": "@default"}, "task_id": {"type": "string"}}, "required": ["task_id"]}},
    {"name": "gtasks_delete_task", "description": "Delete a Google Task", "inputSchema": {"type": "object", "properties": {"tasklist_id": {"type": "string", "default": "@default"}, "task_id": {"type": "string"}}, "required": ["task_id"]}},
    # Gmail
    {"name": "gmail_list_messages", "description": "Search and list emails in Gmail", "inputSchema": {"type": "object", "properties": {"query": {"type": "string", "description": "Gmail search query (e.g. from:someone, is:unread)"}, "max_results": {"type": "integer", "default": 10}}}},
    {"name": "gmail_get_message", "description": "Read full email content and metadata from Gmail", "inputSchema": {"type": "object", "properties": {"message_id": {"type": "string"}}, "required": ["message_id"]}},
    {"name": "gmail_create_draft", "description": "Create a new draft email in Gmail", "inputSchema": {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}}, "required": ["to"]}},
    {"name": "gmail_send_message", "description": "Send an email directly from your Gmail account", "inputSchema": {"type": "object", "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}}, "required": ["to"]}},
    {"name": "gmail_trash_message", "description": "Move an email to Gmail trash", "inputSchema": {"type": "object", "properties": {"message_id": {"type": "string"}}, "required": ["message_id"]}},
    # Drive
    {"name": "gdrive_search_files", "description": "Search files in Google Drive", "inputSchema": {"type": "object", "properties": {"query": {"type": "string", "description": "Drive query e.g. name contains 'Notes'"}, "page_size": {"type": "integer", "default": 10}}}},
    {"name": "gdrive_read_file", "description": "Read content of a file in Google Drive", "inputSchema": {"type": "object", "properties": {"file_id": {"type": "string"}}, "required": ["file_id"]}},
    {"name": "gdrive_trash_file", "description": "Move a file to Google Drive trash", "inputSchema": {"type": "object", "properties": {"file_id": {"type": "string"}}, "required": ["file_id"]}},
    # Docs
    {"name": "gdocs_create_doc", "description": "Create a new Google Document", "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}, "initial_content": {"type": "string"}}, "required": ["title"]}},
    {"name": "gdocs_read_doc", "description": "Read full text of a Google Document", "inputSchema": {"type": "object", "properties": {"doc_id": {"type": "string"}}, "required": ["doc_id"]}},
    {"name": "gdocs_append_text", "description": "Append text to an existing Google Document", "inputSchema": {"type": "object", "properties": {"doc_id": {"type": "string"}, "text": {"type": "string"}}, "required": ["doc_id", "text"]}},
    # Sheets
    {"name": "gsheets_read_range", "description": "Read cell values from a Google Spreadsheet", "inputSchema": {"type": "object", "properties": {"spreadsheet_id": {"type": "string"}, "range_name": {"type": "string", "default": "Sheet1!A1:Z100"}}, "required": ["spreadsheet_id"]}},
    {"name": "gsheets_append_row", "description": "Append row(s) to a Google Spreadsheet", "inputSchema": {"type": "object", "properties": {"spreadsheet_id": {"type": "string"}, "range_name": {"type": "string", "default": "Sheet1!A1"}, "values": {"type": "array", "description": "Array of values or 2D array of rows"}}, "required": ["spreadsheet_id", "values"]}},
    {"name": "gsheets_update_range", "description": "Update specific cell range in a Google Spreadsheet", "inputSchema": {"type": "object", "properties": {"spreadsheet_id": {"type": "string"}, "range_name": {"type": "string"}, "values": {"type": "array"}}, "required": ["spreadsheet_id", "range_name", "values"]}},
    # Contacts
    {"name": "gcontacts_list", "description": "List or search Google Contacts", "inputSchema": {"type": "object", "properties": {"page_size": {"type": "integer", "default": 20}, "query": {"type": "string"}}}},
    {"name": "gcontacts_create", "description": "Create a new contact in Google Contacts", "inputSchema": {"type": "object", "properties": {"given_name": {"type": "string"}, "family_name": {"type": "string"}, "email": {"type": "string"}, "phone_number": {"type": "string"}}, "required": ["given_name"]}},
]

# -----------------------------------------------------------------------------
# JSON-RPC Server Loop
# -----------------------------------------------------------------------------

def send_json(data):
    sys.stdout.write(json.dumps(data) + "\n")
    sys.stdout.flush()

def handle_jsonrpc(line):
    if not line.strip():
        return
    try:
        req = json.loads(line)
    except Exception as e:
        send_json({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {str(e)}"}})
        return

    req_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})

    if method == "initialize":
        send_json({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "google-workspace-mcp",
                    "version": "1.0.0"
                }
            }
        })
    elif method == "notifications/initialized":
        pass
    elif method == "tools/list":
        send_json({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": TOOLS
            }
        })
    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        if tool_name not in DISPATCH_MAP:
            send_json({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Tool '{tool_name}' not found."}
            })
            return

        try:
            handler = DISPATCH_MAP[tool_name]
            res_data = handler(tool_args)
            send_json({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(res_data, indent=2, default=str)
                        }
                    ],
                    "isError": False
                }
            })
        except Exception as err:
            err_details = traceback.format_exc()
            send_json({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error in '{tool_name}': {str(err)}\n\n{err_details}"
                        }
                    ],
                    "isError": True
                }
            })
    elif method == "ping":
        send_json({"jsonrpc": "2.0", "id": req_id, "result": {}})
    else:
        if req_id is not None:
            send_json({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method '{method}' not implemented."}
            })

def main():
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    for line in sys.stdin:
        handle_jsonrpc(line)

if __name__ == "__main__":
    main()

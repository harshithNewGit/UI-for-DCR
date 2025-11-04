import os
import datetime
import re
import calendar
from flask import Flask, render_template, request, flash, redirect, url_for
import uuid
import threading
import time

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for flashing messages

# === UTILITY FUNCTIONS (from original script) ===
def timestamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def current_date_time():
    return datetime.datetime.now().strftime("%d-%B-%Y %H:%M")

def sanitize_folder_name(name):
    """Sanitize folder names to avoid Windows-invalid characters."""
    invalid_chars = r'\/:*?"<>|'
    sanitized = ''.join('_' if c in invalid_chars else c for c in name)
    return sanitized.strip()

def extract_month_year(folder_name):
    """Extracts month number, month name, and year from folder like '1. April 2025'."""
    match = re.search(r"([0-9]+)\.\s*([A-Za-z]+)\s*(\d{4})?", folder_name)
    if match:
        month_num = int(match.group(1))
        month_name = match.group(2)
        year = int(match.group(3)) if match.group(3) else None
        return month_num, month_name, year
    return None, None, None

def generate_months_from(template_num, start_month, start_year):
    """Generates 11 more months from the template month, with proper rollover."""
    months = []
    for i in range(1, 12):  # 11 additional months
        month_idx = (start_month + i - 1) % 12 + 1
        year_offset = (start_month + i - 1) // 12
        year = start_year + year_offset
        month_name = calendar.month_name[month_idx]
        months.append((template_num + i, month_name, year))
    return months

def deep_clone(node):
    return {
        "name": node['name'],
        "readme": node['readme'],
        "children": [deep_clone(child) for child in node['children']]
    }

# === FOLDER STRUCTURE BUILDER (from original script) ===
def parse_structure_file(filepath, log_lines):
    structure = []
    stack = []
    base_path = None
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if lines and lines[0].strip().lower().startswith("base_path:"):
        base_path = lines[0].strip().split(":", 1)[1].strip()
        lines = lines[1:]
    else:
        raise ValueError("The first line of Client_Structure.txt must specify BASE_PATH")

    for idx, line in enumerate(lines):
        line = line.rstrip()
        if not line.startswith("-"):
            continue

        indent = len(line) - len(line.lstrip("-"))
        content = line.lstrip("-").strip()

        if content == "...":
            template_node, template_parent_list = None, None
            for s_indent, s_node, s_parent_list in reversed(stack):
                if s_indent == indent:
                    template_node = s_node
                    template_parent_list = s_parent_list
                    break

            if not template_node:
                raise ValueError(f"No valid template found above '...' at line {idx+1}")

            template_num, start_month_name, start_year = extract_month_year(template_node['name'])
            if not (template_num and start_month_name and start_year):
                raise ValueError(f"Template folder '{template_node['name']}' is not a valid month folder format")

            start_month = list(calendar.month_name).index(start_month_name)
            if start_month == 0:
                raise ValueError(f"Invalid month name in template: '{start_month_name}'")

            month_list = generate_months_from(template_num, start_month, start_year)
            for num, m_name, y in month_list:
                new_folder_name = f"{num}. {m_name} {y}"
                clone = deep_clone(template_node)
                clone['name'] = new_folder_name
                template_parent_list.append(clone)

            continue

        if "(" in content and ")" in content:
            folder_name = content[:content.index("(")].strip()
            readme_note = content[content.index("(")+1:content.index(")")]
        else:
            folder_name = content
            readme_note = None

        sanitized_folder = sanitize_folder_name(folder_name)
        if sanitized_folder != folder_name:
            log_lines.append(f"[{timestamp()}] Sanitized folder name: '{folder_name}' -> '{sanitized_folder}'")
        node = {"name": sanitized_folder, "readme": readme_note, "children": []}

        while stack and stack[-1][0] >= indent:
            stack.pop()

        if not stack:
            structure.append(node)
            stack.append((indent, node, structure))
        else:
            parent = stack[-1][1]
            parent['children'].append(node)
            stack.append((indent, node, parent['children']))

    return base_path, structure

# === RECURSIVE FOLDER CREATOR (from original script) ===
def create_structure(base_path, nodes, log_lines, dir_lines, depth=0):
    for node in nodes:
        folder = sanitize_folder_name(node["name"])
        folder_path = os.path.join(base_path, folder)

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            log_lines.append(f"[{timestamp()}] Created folder: {folder_path}")
        else:
            log_lines.append(f"[{timestamp()}] Folder already exists: {folder_path}")

        dir_lines.append(f"{'│   ' * depth}├── {folder}/")

        if node["readme"]:
            readme_text = node["readme"]
            _, month_name, _ = extract_month_year(folder)
            if month_name:
                readme_text = re.sub(r"\b(for month of )\w+", f"\\1{month_name}", readme_text, flags=re.IGNORECASE)

            readme_path = os.path.join(folder_path, "README.txt")
            if not os.path.exists(readme_path):
                with open(readme_path, "w", encoding="utf-8") as f:
                    f.write(readme_text)
                log_lines.append(f"[{timestamp()}] Created README.txt for: {folder_path}")
            else:
                log_lines.append(f"[{timestamp()}] README.txt already exists for: {folder_path}")

        if node["children"]:
            create_structure(folder_path, node["children"], log_lines, dir_lines, depth + 1)

def write_verification_log(path_to_verify, counts, missing_items, added_items):
    """Writes a summary to log.txt and detailed changes to changes.txt."""
    # First, check if the directory exists. If not, do nothing.
    if not os.path.isdir(path_to_verify):
        return

    # 1. Append a summary to log.txt
    log_summary_content = []
    log_summary_content.append(f"\n\n=== Verification Performed on: {current_date_time()} ===")
    log_summary_content.append("\nResults Summary:")
    log_summary_content.append(f"- Items OK: {counts.get('green', 0)}")
    log_summary_content.append(f"- Items Missing: {counts.get('red', 0)}")
    log_summary_content.append(f"- Items Added: {counts.get('yellow', 0)}")
    
    log_file_path = os.path.join(path_to_verify, "log.txt")
    with open(log_file_path, "a", encoding="utf-8") as f:
        f.write("\n".join(log_summary_content))

    # 2. Overwrite changes.txt with a detailed list of changes
    changes_content = []
    changes_content.append(f"Verification Changes Detected on: {current_date_time()}\n")

    if missing_items:
        changes_content.append("--- Missing Items ---")
        changes_content.extend(missing_items)

    if added_items:
        changes_content.append("\n--- Added Items ---")
        changes_content.extend(added_items)
    
    if not missing_items and not added_items:
        changes_content.append("No changes detected. The structure is correct.")

    changes_file_path = os.path.join(path_to_verify, "changes.txt")
    with open(changes_file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(changes_content))

def get_files_in_path(path):
    """Helper to get a set of files in a given directory, returns empty set if path not found."""
    return {item for item in os.listdir(path) if os.path.isfile(os.path.join(path, item))} if os.path.isdir(path) else set()

def build_comparison_views(expected_nodes, actual_nodes, counts, base_verify_path, missing_items, added_items, depth=0):
    """Recursively builds and compares ideal and actual structures to generate color-coded ASCII trees."""
    ideal_lines = []
    actual_lines = []

    expected_names = {node['name'] for node in expected_nodes}
    actual_names = {node['name'] for node in actual_nodes}

    all_names_at_level = sorted(list(expected_names | actual_names))

    for name in all_names_at_level:
        indent = "│&nbsp;&nbsp; " * depth
        prefix = f"{indent}├── "
        current_path = os.path.join(base_verify_path, name)

        expected_node = next((n for n in expected_nodes if n['name'] == name), None)
        actual_node = next((n for n in actual_nodes if n['name'] == name), None)

        if expected_node and actual_node:
            # Green: All OK
            ideal_lines.append(f'<span class="status-green">{prefix}{name}</span>')
            actual_lines.append(f'<span class="status-green">{prefix}{name}</span>')
            counts['green'] += 1

            # Check for README.txt if expected
            if expected_node.get('readme'):
                readme_prefix = "│&nbsp;&nbsp; " * (depth + 1) + "├── "
                # Construct the full path for the current node to check for files
                full_actual_path = os.path.join(base_verify_path, *actual_node.get('path', '').split(os.sep))
                actual_files = get_files_in_path(full_actual_path)
                if 'README.txt' in actual_files:
                    ideal_lines.append(f'<span class="status-green">{readme_prefix}README.txt</span>')
                else:
                    ideal_lines.append(f'<span class="status-red">{readme_prefix}README.txt</span>')
                    counts['red'] += 1
                    missing_items.append(os.path.join(full_actual_path, 'README.txt'))
        elif expected_node and not actual_node:
            # Red: Missing (does not exist anywhere)
            ideal_lines.append(f'<span class="status-red">{prefix}{name}</span>')
            actual_lines.append(f'<span class="status-placeholder">{prefix}</span>')
            counts['red'] += 1
            missing_items.append(current_path)
        elif not expected_node and actual_node:
            # Yellow: Added
            ideal_lines.append(f'<span class="status-placeholder">{prefix}</span>')
            actual_lines.append(f'<span class="status-yellow">{prefix}{name}</span>')
            counts['yellow'] += 1
            added_items.append(current_path)

        # Recurse into children
        child_ideal, child_actual = build_comparison_views(
            expected_node.get('children', []) if expected_node else [],
            actual_node.get('children', []) if actual_node else [],
            counts, base_verify_path, missing_items, added_items, depth + 1
        )
        ideal_lines.extend(child_ideal)
        actual_lines.extend(child_actual)

    return ideal_lines, actual_lines

def get_all_names(structure_nodes, all_names):
    """This function is no longer needed and can be removed."""
    for node in structure_nodes:
        all_names.add(node["name"])
        if "children" in node:
            get_all_names(node["children"], all_names)

def get_actual_structure_tree(path, base_path_for_relative_path=""):
    """Helper to build a tree from the actual file system."""
    tree = []
    try:
        for name in sorted(os.listdir(path)):
            child_path = os.path.join(path, name)
            if os.path.isdir(child_path):
                node = {"name": name, "children": get_actual_structure_tree(child_path, base_path_for_relative_path)}
                if base_path_for_relative_path:
                    node['path'] = os.path.relpath(child_path, base_path_for_relative_path)
                tree.append(node)
    except FileNotFoundError:
        pass
    return tree

# === TASK MANAGEMENT FOR BATCH VERIFICATION ===
tasks = {} # In-memory store for background tasks

def batch_verification_worker(task_id, selected_folders, base_path, tasks):
    """The actual work of verifying folders, designed to be run in a thread."""
    task = tasks[task_id]
    task['status'] = 'Running'
    results = []
    total_folders = len(selected_folders)

    try:
        _, structure_template = parse_structure_file("Client_Structure.txt", [])
    except Exception as e:
        task['status'] = 'Failed'
        task['results'] = {'error_message': f"Error parsing structure file: {e}"}
        return

    for i, folder_name in enumerate(selected_folders):
        # Check for cancellation signal at the start of each loop
        if task['cancel_event'].is_set():
            task['status'] = 'Cancelled'
            return

        path_to_verify = os.path.join(base_path, folder_name)
        actual_tree = get_actual_structure_tree(path_to_verify, path_to_verify)
        
        counts = {'green': 0, 'red': 0, 'yellow': 0}
        missing_items = []
        added_items = []
        ideal_lines, actual_lines = build_comparison_views(structure_template, actual_tree, counts, path_to_verify, missing_items, added_items)
        
        root_name = f"<b>{folder_name}/</b>"
        ideal_lines.insert(0, root_name)
        actual_lines.insert(0, root_name)
        
        # Check for root-level files
        root_files = get_files_in_path(path_to_verify)
        for required_file in ['log.txt', 'DirectoryStructure.txt']:
            if required_file in root_files:
                ideal_lines.append(f'<span class="status-green">├── {required_file}</span>')
                actual_lines.append(f'<span class="status-green">├── {required_file}</span>')
            else:
                ideal_lines.append(f'<span class="status-red">├── {required_file}</span>')
                actual_lines.append(f'<span class="status-placeholder">├── </span>')
                counts['red'] += 1
                missing_items.append(os.path.join(path_to_verify, required_file))

        # Write verification results to the log.txt for this specific folder
        write_verification_log(path_to_verify, counts, missing_items, added_items)

        has_discrepancies = any(v > 0 for k, v in counts.items() if k != 'green')
        
        results.append({'name': folder_name, 'success': not has_discrepancies, 'ideal': ideal_lines, 'actual': actual_lines, 'counts': counts})
        task['progress'] = ((i + 1) / total_folders) * 100

    task['results'] = results
    task['status'] = 'Completed'

# === FLASK WEB ROUTES ===

@app.route('/', methods=['GET'])
def index():
    """Renders the main input page."""
    return render_template('index.html')

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """Handles viewing and updating the Client_Structure.txt file."""
    structure_file = "Client_Structure.txt"

    if request.method == 'POST':
        base_path = request.form.get('base_path', '').strip()
        structure_content = request.form.get('structure_content', '')

        if not base_path:
            flash("Base path cannot be empty.", "error")
            return render_template('settings.html', base_path=base_path, structure_content=structure_content)

        try:
            full_content = f"BASE_PATH: {base_path}\n\n{structure_content.replace(chr(13), '').strip()}"
            with open(structure_file, "w", encoding="utf-8") as f:
                f.write(full_content)
            flash("Settings saved successfully!", "success")
        except Exception as e:
            flash(f"Error saving settings: {e}", "error")

        return redirect(url_for('settings'))

    # GET request
    try:
        with open(structure_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        base_path_line = lines[0].strip()
        base_path = base_path_line.split(":", 1)[1].strip() if base_path_line.lower().startswith("base_path:") else ""
        
        # Find the start of the actual structure, skipping blank lines after BASE_PATH
        content_start_index = 1
        while content_start_index < len(lines) and not lines[content_start_index].strip():
            content_start_index += 1
        structure_content = "".join(lines[content_start_index:])
        return render_template('settings.html', base_path=base_path, structure_content=structure_content)
    except FileNotFoundError:
        return render_template('settings.html', base_path="", structure_content="# Structure file not found. Add content here and save.")

@app.route('/batch_verify', methods=['GET', 'POST'])
def batch_verify():
    """Displays a list of folders for batch verification."""
    path_to_scan = request.form.get('path_to_scan')

    if not path_to_scan:
        try:
            with open("Client_Structure.txt", "r", encoding="utf-8") as f:
                base_path_line = f.readline()
            if base_path_line.strip().lower().startswith("base_path:"):
                path_to_scan = base_path_line.strip().split(":", 1)[1].strip()
            else:
                path_to_scan = ""
        except FileNotFoundError:
            path_to_scan = ""

    subdirectories = []
    if path_to_scan and os.path.isdir(path_to_scan):
        try:
            subdirectories = sorted([d for d in os.listdir(path_to_scan) if os.path.isdir(os.path.join(path_to_scan, d))])
        except OSError as e:
            flash(f"Error reading directory: {e}", "error")

    return render_template('batch_verify.html', path_to_scan=path_to_scan, subdirectories=subdirectories)

@app.route('/start_batch_task', methods=['POST'])
def start_batch_task():
    """Starts the batch verification task in a background thread."""
    selected_folders = request.form.getlist('folders_to_verify')
    base_path = request.form.get('base_path')

    if not selected_folders:
        return {"error": "No folders selected"}, 400

    task_id = str(uuid.uuid4())
    cancel_event = threading.Event()
    
    thread = threading.Thread(target=batch_verification_worker, args=(task_id, selected_folders, base_path, tasks))
    tasks[task_id] = {
        'thread': thread,
        'cancel_event': cancel_event,
        'status': 'Pending',
        'progress': 0,
        'results': None
    }
    thread.start()
    
    return {"task_id": task_id}

@app.route('/task_status/<task_id>')
def task_status(task_id):
    """Provides the status and progress of a background task."""
    task = tasks.get(task_id)
    if not task:
        return {"status": "Not Found"}, 404
    return {"status": task['status'], "progress": task.get('progress', 0)}

@app.route('/cancel_task/<task_id>', methods=['POST'])
def cancel_task(task_id):
    """Signals a background task to cancel."""
    task = tasks.get(task_id)
    if task:
        task['cancel_event'].set()
        return {"message": "Cancellation signal sent."}
    return {"message": "Task not found."}, 404

@app.route('/task_result/<task_id>')
def task_result(task_id):
    """Renders the results page for a completed task."""
    task = tasks.pop(task_id, None) # Use pop to remove the task after fetching
    if not task or task['status'] != 'Completed':
        return redirect(url_for('batch_verify'))
    return render_template('batch_result.html', results=task['results'])

@app.route('/verify', methods=['POST'])
def verify_folders():
    """Handles the verification of an existing folder structure."""
    path_to_verify = request.form.get('verify_path', '').strip()
    if not path_to_verify:
        flash("No folder path provided for verification.", "error")
        return redirect(url_for('index'))

    structure_file = "Client_Structure.txt"
    if not os.path.exists(structure_file):
        return render_template('result.html', success=False, error_message=f"Structure file '{structure_file}' not found!")

    try:
        _, structure = parse_structure_file(structure_file, [])
    except Exception as e:
        return render_template('result.html', success=False, error_message=f"Error parsing structure file: {e}")

    # 1. Get actual structure from disk
    actual_tree = get_actual_structure_tree(path_to_verify, path_to_verify)

    # 3. Recursively build the comparison trees and count statuses
    counts = {'green': 0, 'red': 0, 'yellow': 0}
    missing_items = []
    added_items = []
    ideal_lines, actual_lines = build_comparison_views(structure, actual_tree, counts, path_to_verify, missing_items, added_items)

    # 4. Prepend the root folder name
    root_name = f"<b>{os.path.basename(os.path.normpath(path_to_verify))}/</b>"
    ideal_lines.insert(0, root_name)
    actual_lines.insert(0, root_name)

    # Check for root-level files
    root_files = get_files_in_path(path_to_verify)
    for required_file in ['log.txt', 'DirectoryStructure.txt']:
        if required_file in root_files:
            ideal_lines.append(f'<span class="status-green">├── {required_file}</span>')
            actual_lines.append(f'<span class="status-green">├── {required_file}</span>')
        else:
            ideal_lines.append(f'<span class="status-red">├── {required_file}</span>')
            actual_lines.append(f'<span class="status-placeholder">├── </span>')
            counts['red'] += 1
            missing_items.append(os.path.join(path_to_verify, required_file))

    # Write verification results to the log.txt
    write_verification_log(path_to_verify, counts, missing_items, added_items)

    # 5. Determine overall success
    has_discrepancies = any(v > 0 for k, v in counts.items() if k != 'green')

    return render_template(
        'result.html',
        is_verification=True,
        success=not has_discrepancies,
        ideal_structure=ideal_lines,
        actual_structure=actual_lines,
        counts=counts
    )
@app.route('/create', methods=['POST'])
def create_folders():
    """Handles the form submission and creates folders."""
    client_input = request.form.get('client_names')
    if not client_input:
        flash("No client name provided. Please enter at least one client name.", "error")
        return redirect(url_for('index'))

    structure_file = "Client_Structure.txt"
    if not os.path.exists(structure_file):
        return render_template('result.html', success=False, error_message=f"Structure file '{structure_file}' not found!")

    all_logs = []
    
    try:
        log_lines_parser = []
        base_path, structure = parse_structure_file(structure_file, log_lines_parser)
        if log_lines_parser:
            all_logs.extend(log_lines_parser)
            all_logs.append("-" * 20)

    except Exception as e:
        return render_template('result.html', success=False, error_message=str(e))

    clients = [c.strip() for c in client_input.split(",") if c.strip()]

    for client in clients:
        log_lines = []
        dir_lines = []

        log_lines.append(f"\n=== Run started on {current_date_time()} for client: {client} ===\n")

        client_folder = os.path.join(base_path, sanitize_folder_name(client))
        if not os.path.exists(client_folder):
            os.makedirs(client_folder)
            log_lines.append(f"[{timestamp()}] Created client main folder: {client_folder}")
        else:
            log_lines.append(f"[{timestamp()}] Client folder already exists: {client_folder}")

        dir_lines.append(f"{client}/")

        create_structure(client_folder, structure, log_lines, dir_lines, depth=1)

        # Append logs to existing log.txt
        with open(os.path.join(client_folder, "log.txt"), "a", encoding="utf-8") as f:
            f.write("\n".join(log_lines))
            f.write("\n")

        header = f"Directory Structure for Client: {client}\nGenerated on: {current_date_time()}\n\n"
        with open(os.path.join(client_folder, "DirectoryStructure.txt"), "w", encoding="utf-8") as f:
            f.write(header)
            f.write("\n".join(dir_lines))
            f.write("\n\nThis folder structure was auto-generated by the Acutant Folder Builder Tool.")
        
        all_logs.extend(log_lines)

    return render_template('result.html', success=True, logs=all_logs)

if __name__ == "__main__":
    # Use host='0.0.0.0' to make it accessible on your network
    app.run(debug=True, host='0.0.0.0')
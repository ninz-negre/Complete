import os
import time
import json
import requests
import mimetypes
import re
import tkinter as tk
import sys
import threading
import pythoncom
from tkinter import ttk, messagebox
from flask import Flask, request, jsonify
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from requests_toolbelt.multipart.encoder import MultipartEncoder


# Initialize Flask app
app = Flask(__name__)
CORS(app)

DOWNLOAD_PATH = r"C:\Users\Hello World!\Desktop\COMPLETE\SELENIUM\docs"

classified_documents = {
    "drivers_license": ["license", "id", "driver"],
    "national_id": ["passport", "national", "citizen", "citizenship", "residency"],
    "utility_bill": ["bill", "utility"],
    "bank_statement": ["bank", "statement"],
    "application_form": ["application", "form"],
    "payslip": ["payslip", "salary", "payroll"],
    "insurance": ["insurance", "policy", "coverage", "premium"]
}

# Ensure the download directory exists
if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

chrome_options = webdriver.ChromeOptions()    
chrome_options.add_argument("user-data-dir=C:\\Automation\\RPA")
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option("useAutomationExtension", False)

prefs = {
    "download.default_directory": DOWNLOAD_PATH,  # Set download path
    "download.prompt_for_download": False,        # Disable prompt
    "download.directory_upgrade": True,          # Allow path updates
    "safebrowsing.enabled": True                 # Enable safe browsing
}
chrome_options.add_experimental_option("prefs", prefs)

def process_applicants(applicant_details, lender_details, applicant_api_url, lender_api_url, headers):
    existing_applicants = get_existing_applicants(applicant_api_url, headers)
    new_applicants = []
    all_applicant_details = []

    for applicant in applicant_details:
        matching_records, status_code = is_applicant_existing(applicant, existing_applicants)
        
        if status_code == 200:
            all_applicant_details.extend(matching_records)  # Include existing applicants
        else:
            new_applicants.append(applicant)

    # Process new applicants in APITable
    if new_applicants:
        for applicant_data in new_applicants:
            response_data = post_to_apitable(applicant_api_url, headers, applicant_data, "Applicant Hub")
            if response_data:
                all_applicant_details.extend(response_data)

    # Add Application_ID to group applicants (for both existing and new ones)
    application_id = time.strftime("%Y%m%d%H%M%S")
    for applicant in all_applicant_details:
        applicant["Application_ID"] = application_id

    # Process lender data
    for lender_data in lender_details:
        if lender_data:
            post_to_apitable(lender_api_url, headers, lender_data, "Lender Hub")

    # **Always launch the Tkinter GUI**
    if all_applicant_details:  # Ensure there are applicants to process
        root = tk.Tk()
        app = FileSelectorApp(root, all_applicant_details)

        if sys.platform.startswith('win'):
            pythoncom.CoInitialize()
            root.mainloop()
        else:
            root.mainloop()

    return {
        "status": "success",
        "message": "Processing started",
        "applicant_count": len(all_applicant_details)
    }

class FileSelectorApp:
    def __init__(self, root, applicant_details):
        self.root = root
        self.root.title("Document Assignment Tool")
        self.root.geometry("1000x700")
        
        # Store applicant details and initialize assignments
        self.applicant_details = applicant_details
        self.assignments = {}  # Dictionary to store file assignments
        self.processed_files = {}  # Dictionary to track processed files per applicant
        
        # Create main container with grid
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        
        # Left Frame: Available Files
        left_frame = ttk.LabelFrame(self.root, text="Available Documents")
        left_frame.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")
        
        # File listbox with scrollbar
        self.file_listbox = tk.Listbox(left_frame, selectmode=tk.SINGLE)
        file_scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.file_listbox.yview)
        self.file_listbox.configure(yscrollcommand=file_scrollbar.set)
        
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        file_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Right Frame: Controls and Assigned Files
        right_frame = ttk.Frame(self.root)
        right_frame.grid(row=0, column=1, padx=10, pady=5, sticky="nsew")
        
        # Applicant selection
        ttk.Label(right_frame, text="Select Applicant:").pack(pady=5)
        self.applicant_var = tk.StringVar()
        self.applicant_dropdown = ttk.Combobox(right_frame, textvariable=self.applicant_var)
        self.applicant_dropdown.pack(pady=5)
        
        # Assigned files frame
        assigned_frame = ttk.LabelFrame(right_frame, text="Assigned Documents")
        assigned_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.assigned_listbox = tk.Listbox(assigned_frame)
        assigned_scrollbar = ttk.Scrollbar(assigned_frame, orient=tk.VERTICAL, command=self.assigned_listbox.yview)
        self.assigned_listbox.configure(yscrollcommand=assigned_scrollbar.set)
        
        self.assigned_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        assigned_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Status frame
        status_frame = ttk.LabelFrame(right_frame, text="Processing Status")
        status_frame.pack(fill=tk.X, pady=10)
        self.status_text = tk.Text(status_frame, height=4, wrap=tk.WORD)
        self.status_text.pack(fill=tk.X, padx=5, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(right_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="Assign Document", command=self.assign_document).pack(fill=tk.X, pady=2)
        ttk.Button(button_frame, text="Remove Assignment", command=self.remove_assignment).pack(fill=tk.X, pady=2)
        ttk.Button(button_frame, text="Submit to Textract", command=self.submit_to_textract).pack(fill=tk.X, pady=2)
        ttk.Button(button_frame, text="Clear Status", command=self.clear_status).pack(fill=tk.X, pady=2)
        
        # Initialize the interface
        self.load_applicants()
        self.load_files()
        
        # Bind events
        self.applicant_dropdown.bind('<<ComboboxSelected>>', self.on_applicant_selected)
        
        # Update status
        self.update_status("Ready to process documents.")
    
    def get_folder_path(self):
        """Get the folder path for the current applicant"""
        # Find the first applicant in the same application
        current_applicant = next(
            (app for app in self.applicant_details 
             if f"{app['First Name']} {app['Last Name']}" == self.applicant_var.get()),
            None
        )
        
        if not current_applicant:
            return None
            
        # Use the first applicant's name as the folder name
        first_applicant = self.applicant_details[0]  # Always use the first applicant's name for the folder
        folder_name = f"{first_applicant['First Name']} {first_applicant['Last Name']}"
        
        # Debug information
        print(f"First applicant: {first_applicant}")
        print(f"Folder name: {folder_name}")

        return os.path.join(DOWNLOAD_PATH, folder_name)
    
    def load_applicants(self):
        """Load applicants into the dropdown"""
        applicant_names = [
            f"{app['First Name']} {app['Last Name']}"
            for app in self.applicant_details
        ]
        self.applicant_dropdown['values'] = applicant_names
        if applicant_names:
            self.applicant_dropdown.set(applicant_names[0])
            print(f"Loaded applicants: {applicant_names}")
    
    def load_files(self):
        """Load available files for the selected applicant"""
        self.file_listbox.delete(0, tk.END)
        folder_path = self.get_folder_path()
        
        if not folder_path:
            print("No folder path found")
            return
            
        if os.path.exists(folder_path):
            print(f"Loading files from: {folder_path}")
            for file_name in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file_name)
                if os.path.isfile(file_path):
                    # Check if the file is not processed and not assigned
                    current_applicant = self.applicant_var.get()
                    if (file_name not in self.processed_files.get(current_applicant, set()) and 
                        file_name not in self.assignments.get(current_applicant, [])):
                        self.file_listbox.insert(tk.END, file_name)
                        print(f"Added file to listbox: {file_name}")
        else:
            print(f"Folder does not exist: {folder_path}")
    
    def update_status(self, message):
        """Update the status text with timestamp"""
        timestamp = time.strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_text.see(tk.END)
    
    def clear_status(self):
        """Clear the status text"""
        self.status_text.delete(1.0, tk.END)
        self.update_status("Status cleared.")
    
    def on_applicant_selected(self, event):
        """Handle applicant selection change"""
        self.load_files()
        self.update_assigned_files()
        self.update_status(f"Selected applicant: {self.applicant_var.get()}")
    
    def assign_document(self):
        """Assign selected document to current applicant"""
        selected_indices = self.file_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Warning", "Please select a document to assign")
            return
        
        selected_file = self.file_listbox.get(selected_indices[0])
        selected_applicant = self.applicant_var.get()
        
        if selected_applicant not in self.assignments:
            self.assignments[selected_applicant] = []
        
        self.assignments[selected_applicant].append(selected_file)
        self.file_listbox.delete(selected_indices[0])
        self.update_assigned_files()
        self.update_status(f"Assigned '{selected_file}' to {selected_applicant}")
    
    def remove_assignment(self):
        """Remove document assignment"""
        selected_indices = self.assigned_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Warning", "Please select a document to remove")
            return
        
        selected_file = self.assigned_listbox.get(selected_indices[0])
        selected_applicant = self.applicant_var.get()
        
        self.assignments[selected_applicant].remove(selected_file)
        self.assigned_listbox.delete(selected_indices[0])
        self.file_listbox.insert(tk.END, selected_file)
        self.update_status(f"Removed '{selected_file}' from {selected_applicant}")
    
    def update_assigned_files(self):
        """Update the assigned files listbox"""
        self.assigned_listbox.delete(0, tk.END)
        selected_applicant = self.applicant_var.get()
        if selected_applicant in self.assignments:
            for file_name in self.assignments[selected_applicant]:
                self.assigned_listbox.insert(tk.END, file_name)
    
    def submit_to_textract(self):
        """Submit assigned documents to Textract"""
        if not any(self.assignments.values()):
            messagebox.showwarning("Warning", "No documents have been assigned")
            return
        
        # Start processing in a separate thread
        processing_thread = threading.Thread(target=self._process_documents)
        processing_thread.start()
    
    def _process_documents(self):
        """Process documents in background thread"""
        folder_path = self.get_folder_path()
        if not folder_path:
            self.root.after(0, self.update_status, "Error: Could not determine folder path")
            return
            
        for applicant_name, files in self.assignments.items():
            if not files:
                continue
            
            # Find applicant details
            applicant = next(
                (app for app in self.applicant_details 
                 if f"{app['First Name']} {app['Last Name']}" == applicant_name),
                None
            )
            
            if applicant and files:
                files_to_upload = []
                
                for file_name in files:
                    file_path = os.path.join(folder_path, file_name)
                    if os.path.isfile(file_path):
                        metadata = get_file_metadata(file_path)
                        files_to_upload.append((file_name, open(file_path, "rb"), metadata["mime_type"]))
                
                if files_to_upload:
                    try:
                        self.root.after(0, self.update_status, f"Processing files for {applicant_name}...")
                        
                        # Prepare multipart form-data
                        fields = [
                            ("files", (file_name, file_obj, mime_type))
                            for file_name, file_obj, mime_type in files_to_upload
                        ]
                        
                        # Add applicant metadata
                        fields.append(("applicant", json.dumps({
                            "Applicant_ID": applicant["Applicant_ID"],
                            "First Name": applicant["First Name"],
                            "Last Name": applicant["Last Name"],
                            "recordId": applicant["recordId"]
                        })))
                        
                        multipart_data = MultipartEncoder(fields=dict(fields))
                        
                        # Send to Textract middleware
                        response = requests.post(
                            "http://localhost:3012/upload",
                            data=multipart_data,
                            headers={"Content-Type": multipart_data.content_type}
                        )
                        
                        if response.status_code in (200, 201):
                            # Mark files as processed for this applicant
                            if applicant_name not in self.processed_files:
                                self.processed_files[applicant_name] = set()
                            for file_name, _, _ in files_to_upload:
                                self.processed_files[applicant_name].add(file_name)
                            
                            self.root.after(0, self.update_status,
                                          f"✅ Successfully processed files for {applicant_name}")
                        else:
                            self.root.after(0, self.update_status,
                                          f"❌ Failed to process files for {applicant_name}")
                    
                    except Exception as e:
                        self.root.after(0, self.update_status,
                                      f"Error processing files for {applicant_name}: {str(e)}")
                    
                    finally:
                        for _, file_obj, _ in files_to_upload:
                            file_obj.close()
        
        # Clear assignments after processing
        self.assignments = {}
        
        # Update UI in main thread
        self.root.after(0, self._after_processing)
    
    def _after_processing(self):
        """Update UI after processing completes"""
        self.update_assigned_files()
        self.load_files()
        self.update_status("Processing complete. Ready for more documents.")
        messagebox.showinfo("Success", "Documents have been submitted for processing")

def get_file_metadata(file_path):
    """Get file metadata including MIME type"""
    file_name = os.path.basename(file_path)
    mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    return {"file_name": file_name, "mime_type": mime_type}

def is_applicant_existing(applicant_data, existing_applicants):
    try:
        # Extract fields from applicant_data
        records = applicant_data.get("records", [])
        if not records:
            print("No records found in the applicant data.")
            return [], 404  # Returning empty list with status 404 if no record is found
        
        applicant_fields = records[0].get("fields", {})
        applicant_first_name = applicant_fields.get("First Name")
        applicant_last_name = applicant_fields.get("Last Name")

        # Loop through existing applicants to find a match
        matching_records = []
        for record in existing_applicants:
            fields = record.get("fields", {})
            if (
                fields.get("First Name") == applicant_first_name
                and fields.get("Last Name") == applicant_last_name
            ):
                matching_records.append({
                    "Applicant_ID": fields.get("Applicant_ID"),
                    "First Name": fields.get("First Name"),
                    "Last Name": fields.get("Last Name"),
                    "recordId": record.get("recordId")
                })
        
        if matching_records:
            return matching_records, 200  # Returning the matched records and status 200
        else:
            return [], 404  # No match, returning empty list and status 404

    except KeyError as e:
        print(f"KeyError occurred: {str(e)}")
        return [], 404

# Function for APITable
def post_to_apitable(api_url, headers, data, data_type):
    try:
        response = requests.post(api_url, headers=headers, json=data)

        if response.status_code in (200, 201):
            if data_type != "Lender Hub":
                print(f"{data_type} data successfully posted.")
            
            response_data = response.json()

            # Parse the response to extract IDs and applicant details (name, etc.)
            if response_data.get("success") and "records" in response_data["data"] and data_type != "Lender Hub":
                records = response_data["data"]["records"]
                processed_records = []

                for record in records:
                    record_id = record.get("recordId")
                    applicant_id = record["fields"].get("Applicant_ID")
                    first_name = record["fields"].get("First Name")
                    last_name = record["fields"].get("Last Name")

                    if record_id and applicant_id and first_name and last_name:
                        processed_records.append({
                            "Applicant_ID": applicant_id,
                            "recordId": record_id,
                            "First Name": first_name,
                            "Last Name": last_name
                        })
                
                return processed_records  # Return processed records for the current applicant
            elif data_type != "Lender Hub":
                print(f"No valid records found in {data_type} response.")
                return []
        else:
            if data_type != "Lender Hub":
                print(f"Failed to post {data_type} data. Status: {response.status_code}, Response: {response.text}")
            return []
    except requests.exceptions.RequestException as e:
        if data_type != "Lender Hub":
            print(f"Network error while posting {data_type} data: {str(e)}")
        return []

def get_existing_applicants(applicant_api_url, headers):
    try:
        # Send a GET request to the API
        response = requests.get(applicant_api_url, headers=headers) 
        if response.status_code == 200:
            data = response.json()
            return data.get("data", {}).get("records", [])
        else:
            print(f"Failed to fetch existing applicants. Status Code: {response.status_code}")
            return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching existing applicants: {str(e)}")
        return []

def get_file_metadata(file_path):
    file_name = os.path.basename(file_path)
    file_extension = os.path.splitext(file_name)[1]  # Get file extension
    mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"  # Guess MIME type
    return {"file_name": file_name, "file_extension": file_extension, "mime_type": mime_type}

def get_document_type(file_name):
    normalized_file_name = re.sub(r'[^a-z0-9]', ' ', file_name.lower())

    for doc_type, keywords in classified_documents.items():
        if any(re.search(r'\b' + re.escape(keyword) + r'\b', normalized_file_name) for keyword in keywords):
            return doc_type

    return "unknown_document"
    
def prepare_headers_with_default_files(files):
    headers = {}

    # Initialize all document types with empty values
    for doc_type in classified_documents.keys():
        headers[doc_type] = ""

    # Track document types and their corresponding files
    doc_files = {doc_type: [] for doc_type in classified_documents.keys()}
    unknown_files = []  # Track files that couldn't be classified

    # Assign actual file names if they exist
    for file_name in files:
        doc_type = get_document_type(file_name)
        if doc_type == "unknown_document":
            unknown_files.append(file_name)
        else:
            doc_files[doc_type].append(file_name)

    # Update headers to store all found files under their document types
    for doc_type, files_in_type in doc_files.items():
        if files_in_type:
            headers[doc_type] = ", ".join(files_in_type)  # Store all files for that doc type

    # Optionally, add an "unknown" category for uncategorized files
    if unknown_files:
        headers["unknown_document"] = ", ".join(unknown_files)

    return headers

This function will go to n8n and pass the documents from the salestrekker
def send_applicant_data_with_files(applicant_details):
    folder_created = False
    folder_path = ""
    combined_applicant_data = {}
    files_to_upload = []
    file_metadata = {}
    headers = {}

    # Combine applicant details into a single object
    for i, applicant in enumerate(applicant_details):
        combined_applicant_data[f"Applicant{i+1}"] = {
            "Applicant_ID": applicant["Applicant_ID"],
            "First Name": applicant["First Name"],
            "Last Name": applicant["Last Name"],
            "recordId": applicant["recordId"],
        }

    # Full name of the first applicant
    full_name = f"{applicant_details[0]['First Name']} {applicant_details[0]['Last Name']}"

    # Check if folder exists
    folder_path = os.path.join(DOWNLOAD_PATH, full_name)
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        folder_created = True
        print(f"Using existing folder: {folder_path}")
    else:
        print(f"Folder not found for {full_name}.")
        return  

    # Collect files
    found_files = []
    if folder_created:
        for index, file_name in enumerate(os.listdir(folder_path)):
            file_path = os.path.join(folder_path, file_name)
            if os.path.isfile(file_path):
                metadata = get_file_metadata(file_path)
                file_metadata[f"file{index}"] = metadata
                
                # Get document type
                doc_type = get_document_type(file_name)

                # Store file for upload
                files_to_upload.append((file_name, open(file_path, "rb"), metadata["mime_type"], doc_type))

                found_files.append(file_name)  # Track found files

    # Ensure **all document types are included** in headers
    headers.update(prepare_headers_with_default_files(found_files))

    # Check if there are files
    if not files_to_upload:
        print("No files found for the applicants.")
        return  

    # Prepare multipart form-data payload
    fields = {
        "applicants": json.dumps(combined_applicant_data),
        "file_metadata": json.dumps(file_metadata)
    }

    # Add files to form-data
    for index, (file_name, file_obj, mime_type, _) in enumerate(files_to_upload):
        fields[f"files_{index}"] = (file_name, file_obj, mime_type)

    # Create multipart encoder
    multipart_data = MultipartEncoder(fields=fields)

    # Add Content-Type header
    headers["Content-Type"] = multipart_data.content_type

    # Define the endpoint
    n8n_endpoint = "https://integration.korunaassist.com/webhook-test/67944059-2667-4476-87e0-1b6ec63ea6ef"

    try:
        # Send POST request with custom headers
        response = requests.post(url=n8n_endpoint, data=multipart_data, headers=headers)

        # Close all file handles
        for _, file_obj, _, _ in files_to_upload:
            file_obj.close()

        # Handle response
        if response.status_code in (200, 201):
            print(f"✅ Successfully sent data for applicants!")
        else:
            print(f"❌ Failed to send data. Response Code: {response.status_code}")
            print("Response:", response.text)
    except requests.exceptions.RequestException as e:
        print(f"Error while sending data: {str(e)}")
    finally:
        # Ensure all file handles are closed
        for _, file_obj, _, _ in files_to_upload:
            file_obj.close()

def send_files_to_textract(applicant_details):
    folder_path = ""
    files_to_upload = []

    # Combine applicant details into a single object
    combined_applicant_data = {
        f"Applicant{i+1}": {
            "Applicant_ID": applicant["Applicant_ID"],
            "First Name": applicant["First Name"],
            "Last Name": applicant["Last Name"],
            "recordId": applicant["recordId"],
        }
        for i, applicant in enumerate(applicant_details)
    }

    # Full name of the first applicant
    full_name = f"{applicant_details[0]['First Name']} {applicant_details[0]['Last Name']}"

    # Check if folder exists
    folder_path = os.path.join(DOWNLOAD_PATH, full_name)
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        print(f"Folder not found for {full_name}.")
        return  

    # Collect files
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        if os.path.isfile(file_path):
            metadata = get_file_metadata(file_path)
            doc_type = get_document_type(file_name)

            # Store file for upload
            files_to_upload.append((file_name, open(file_path, "rb"), metadata["mime_type"], doc_type))

    # Check if there are files
    if not files_to_upload:
        print("No files found for the applicants.")
        return  

    # Prepare multipart form-data payload
    fields = [
        ("files", (file_name, file_obj, mime_type))  # ✅ Use "files" as the field name
        for file_name, file_obj, mime_type, _ in files_to_upload
    ]
    
    # Also send metadata
    fields.append(("applicants", json.dumps(combined_applicant_data)))

    # Create multipart encoder
    multipart_data = MultipartEncoder(fields=fields)

    # Set headers
    headers = {
        "Content-Type": multipart_data.content_type
    }

    # Define the new Textract middleware endpoint
    textract_endpoint = "http://localhost:3012/upload"

    try:
        # Send POST request to your Textract middleware
        response = requests.post(url=textract_endpoint, data=multipart_data, headers=headers)

        # Close all file handles
        for _, file_obj, _, _ in files_to_upload:
            file_obj.close()

        # Handle response
        if response.status_code in (200, 201):
            print("✅ Successfully sent files to Textract middleware!")
        else:
            print(f"❌ Failed to send files. Response Code: {response.status_code}")      
    except requests.exceptions.RequestException as e:
        print(f"Error while sending data: {str(e)}")
    finally:
        # Ensure all file handles are closed
        for _, file_obj, _, _ in files_to_upload:
            file_obj.close()

def scroll_down_until_bottom(driver):
    try:
        ticket_content = driver.find_element(By.TAG_NAME, "ticket-content")
        last_scroll_position = -1

        while True:
            # Scroll down
            driver.execute_script("arguments[0].scrollBy(0, 500);", ticket_content)
            time.sleep(2)  # Wait for new elements to load

            # Get new scroll position
            current_scroll_position = driver.execute_script("return arguments[0].scrollTop;", ticket_content)

            # If the scroll position hasn't changed, we've reached the bottom
            if current_scroll_position == last_scroll_position:
                print("Reached the bottom of the timeline.")
                break
            else:
                last_scroll_position = current_scroll_position

    except Exception as e:
        print(f"Error while scrolling down: {e}")

@app.route('/', methods=['GET'])
def home():
    print('service is running')
    return "Service is running"


@app.route('/process-url', methods=['POST'])
def process_url():
    # Parse request data
    data = request.json
    print(data)
    login_url = data.get('loginUrl')
    target_url = data.get('targetUrl')

    if not login_url or not target_url:
        return jsonify({"error": "Missing required parameters"}), 400

    # Set up Chrome WebDriver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    try:
        # Step 1: Log in
        driver.get(login_url)

        # Wait for specific elements to load (example: <a> tag)
        WebDriverWait(driver, 10000).until(
            EC.presence_of_element_located((By.TAG_NAME, "a"))
        )

        print("Login page is loaded. Pausing for user to input credentials...")

        # Pause and allow the user to input credentials
        time.sleep(30)

        print("Waiting for user to log in...")

        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "img"))
        )

        print("Login successful. Continuing automation...")

        # Step 2: Navigate to provided URL
        driver.get(target_url)

        # Wait for content to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "ticket-contacts"))
        )

        time.sleep(10)

        applicants = []
        seen_names = set()
        ticket_contacts = driver.find_elements(By.TAG_NAME, "ticket-contacts")
        folder_created = False
        applicant_folder = ""

        for contact in ticket_contacts:
            try:
                # Extract name
                name = contact.find_element(By.XPATH, ".//strong[@ng-bind='::client.getName()']").text
                if name and name not in seen_names:
                    seen_names.add(name)

                    # Create or use the folder for the first applicant
                    if not folder_created:
                        applicant_folder = os.path.join(DOWNLOAD_PATH, name)

                        # Check if the folder exists
                        if not os.path.exists(applicant_folder):
                            os.makedirs(applicant_folder)
                            print(f"Folder created for the first applicant: {name}")
                        else:
                            print(f"Using existing folder: {applicant_folder}")

                        # Update download directory dynamically for the first applicant
                        driver.execute_cdp_cmd(
                            "Page.setDownloadBehavior",
                            {
                                "behavior": "allow",
                                "downloadPath": applicant_folder,
                            },
                        )

                        folder_created = True

                    # Attempt to extract phone number, fallback to None if not found
                    try:
                        phone = contact.find_element(By.XPATH, ".//span[@ng-bind='::client.getPhone()']").text
                    except Exception:
                        phone = None

                    # Attempt to extract email, fallback to None if not found
                    try:
                        email = contact.find_element(By.XPATH, ".//span[@ng-bind='::client.getEmail()']").text
                    except Exception:
                        email = None

                    # Append extracted data to the applicants list
                    applicants.append({
                        "applicant_name": name,
                        "contact_number": phone,
                        "email": email
                    })

                    # Break the loop if required number of names are extracted
                    if len(seen_names) == 2:
                        break

            except Exception as e:
                print(f"Error processing contact: {str(e)}")
                continue

        # Wait for content to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "ticket-basic-info-value"))
        )

        time.sleep(5)


        lender = None
        try:
            lender_element = driver.find_element(By.XPATH, "//span[@ng-bind=\"::Model.currentLender.getName()\"]")
            lender = lender_element.get_attribute("innerText").strip()
        except Exception as e:
            print(f"Error getting lender data: {str(e)}")

        # Get loan security addresses
        loan_security_addresses = None  # Initialize as None
        try:
            address_elements = driver.find_elements(By.XPATH, 
                "//ticket-basic-info-value//span[@ng-repeat='security in Model.currentHomeLoan.securityDetails.securitySplits']")
            addresses = []  # Temporary list to hold the addresses
            for address_elem in address_elements:
                address_text = address_elem.get_attribute("innerText").strip()
                if address_text:
                    addresses.append(address_text)
            
            # Join addresses into a single string separated by commas (or any other delimiter)
            if addresses:
                loan_security_addresses = ", ".join(addresses)
        except Exception as e:
            print(f"Error getting addresses: {str(e)}")

        
        deal_value = None
        try:
            deal_value_element = driver.find_element(By.XPATH, 
                "//ticket-basic-info-value[@ng-bind='Model.currentTicket.values.onceOff.formatWithCurrency(CurrentCurrency(), 0)']")
            deal_value = deal_value_element.get_attribute("innerText").strip()

            # Clean and convert the deal value to a float
            if deal_value:
                # Remove the dollar sign and commas, then convert to float
                deal_value = float(deal_value.replace("$", "").replace(",", ""))
        except Exception as e:
            print(f"Error getting deal value data: {str(e)}")


        total_loan_amount = None
        try:
            total_loan_amount_element = driver.find_element(By.XPATH, 
                "//ticket-basic-info-value[@ng-bind='Model.preferredProductTotalLoanAmount.formatWithCurrency(CurrentCurrency())']")
            total_loan_amount = total_loan_amount_element.get_attribute("innerText").strip()
        except Exception as e:
            print(f"Error getting total loan amount data: {str(e)}")

        estimated_settlement_date = None
        try:
            settlement_element = driver.find_element(By.XPATH, 
                "//span[@ng-bind='Model.currentTicket.getDueDate(CurrentTimeZone(), CurrentOrganizationDateTimeLocale())']")
            estimated_settlement_date = settlement_element.get_attribute("innerText").strip()
        except Exception as e:
            print(f"Error getting settlement date data: {str(e)}")

        deal_owner = None
        try:
            deal_owner_element = driver.find_element(By.XPATH, 
                "//span[@ng-bind=\"getAccount(Model.currentTicket.idOwner).getName()\"]")
            deal_owner = deal_owner_element.get_attribute("innerText").strip()
        except Exception as e:
            print(f"Error getting deal owner data: {str(e)}")
        
        try:
            # Locate the scrollable container for forcing the scroll
            scrollable_container = driver.find_element(By.CSS_SELECTOR, "md-content[md-scroll-y]")

            # Force the scroll to the bottom to trigger new event loading
            print("🔽 Scrolling down to trigger loading of new timeline events...")
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", scrollable_container)
            time.sleep(5)  # Wait for new items to load

            # Get all timeline-event elements after scrolling
            timeline_events = driver.find_elements(By.TAG_NAME, "timeline-event")
            print(f"📋 Found {len(timeline_events)} timeline events.")

            # Process the events
            for index, event in enumerate(timeline_events):
                try:
                    # Check if the element contains <span>Labels</span>
                    labels_span = event.find_elements(By.XPATH, ".//span[text()='Labels']")
                    if labels_span:
                        print(f"🎯 Found labels in timeline-event #{index + 1}, processing...")

                        # Locate and click the download button
                        download_button = event.find_element(By.XPATH, ".//md-icon[text()='cloud_download']")
                        if download_button:
                            ActionChains(driver).move_to_element(download_button).perform()
                            download_button.click()
                            print(f"✅ Download button clicked for timeline-event #{index + 1}.")
                            time.sleep(2)  # Optional: Wait between downloads

                except Exception as e:
                    print(f"⚠️ Error processing timeline-event #{index + 1}: {e}")

            print("✅ All events processed. Stopping process.")
            
        except Exception as e:
            print(f"Error during process: {e}")

        # POST the data to the apitable endpoint
        applicant_api_url = "https://ai-broker.korunaassist.com/fusion/v1/datasheets/dst1vag1MekDBbrzoS/records"
        lender_api_url = "https://ai-broker.korunaassist.com/fusion/v1/datasheets/dstGYdtqYD60Hk58UV/records"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer usk5YzjFkoAuRfYFNcPCM0j"
        }

        applicant_details = []
        lender_details = []

        # Loop over each applicant
        for applicant in applicants:
            # Create JSON structure for each applicant
            applicant_data = {
                "records": [
                    {
                        "fields": {
                            "Application Hub": None,
                            "Title": None,
                            "First Name": applicant["applicant_name"].split()[0] if applicant.get("applicant_name") else None,
                            "Last Name": applicant["applicant_name"].split()[-1] if applicant.get("applicant_name") else None,
                            "Date of Birth": None,
                            "Residential Address": loan_security_addresses if loan_security_addresses else None,
                            "Primary Contact Number": applicant.get("contact_number") if applicant.get("contact_number") else None,
                            "Secondary Contact Number": None,
                            "Email Address": applicant.get("email") if applicant.get("email") else None,
                            "Marital Status": None,
                            "Savings": None,
                            "Income": None,
                            "Housing Loans": None,
                            "Vehicle Loans": None,
                            "Personal Loans": None,
                            "Total Liabilities": None,
                            "Employment Status": None,
                            "Employer": None
                        }
                    }
                ],
                "fieldKey": "name"
            }

            applicant_details.append(applicant_data)

            lender_data = {}
            # Post lender data only once
            if lender:
                lender_data = {
                    "records": [
                        {
                            "fields": {
                                "Company Name": lender,
                                "Contact": None,
                                "Website": None,
                                "Phone Number": None,
                            }
                        }
                    ],
                    "fieldKey": "name"
                }
            
            lender_details.append(lender_data)

        process_applicants(applicant_details, lender_details, applicant_api_url, lender_api_url, headers)

        return jsonify({"message": "URL processed successfully!"}), 200

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return jsonify({"message": "URL processed unsuccessfully!"}), 500

    finally:
        driver.quit()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=2500, debug=True)

import PyPDF2
import re
import subprocess
import os
import mysql.connector


# Function to extract text from a PDF file.
def extract_text_from_pdf(pdf_path):
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ''
            for page in pdf_reader.pages:
                text += page.extract_text() + ' '  
        return text
    except KeyError as e:
        print(f"Skipping {pdf_path} due to error: {e}")
        return ""  # Return an empty string to indicate failure


# Function to check if the PDF text extraction missed the API number, indicating OCR may be needed.
def check_pdf_needs_ocr_for_api_number(pdf_text):
    # Regular expression pattern to search for the API number
    api_number_pattern = r'API\s*(Number|NUMBER|No|num|#)[:\s\w-]*?[^\d]*(\d{2})[\s_-]*(\d{3})[\s_-]*(\d{5})'
    
    # Search for the API number in the extracted text
    api_number_search = re.search(api_number_pattern, pdf_text)
    
    # Return True if API number is not found, indicating OCR might be needed
    return api_number_search is None


# Function to apply OCR to a PDF file for text extraction.
def apply_ocr_to_pdf(input_pdf):
    command = ['ocrmypdf', '--force-ocr', input_pdf, 'output.pdf']
    subprocess.run(command)


# Function to extract the first block of stimulation data from the PDF text.    
def extract_first_stimulation_data_block(text):
    # Pattern to match the start of a stimulation data block and capture until it hits another "Date Stimulated" or end
    block_pattern = re.compile(
        r'(Date Stimulated.*?)(?=Date Stimulated|$)', 
        re.DOTALL | re.IGNORECASE
    )

    # Find the first block of stimulation data
    first_block_match = block_pattern.search(text)
    if first_block_match:
        return first_block_match.group(1)  # Return the first complete block of data
    return None


# Function to extract detailed stimulation data from a block of text.
def extract_stimulation_details(block_text):
    data = {}
    
    # Correcting the pattern for capturing date_stimulated, stimulated_formation, and other fields
    combined_pattern = re.compile(
        r'Date Stimulated\s*!Stimulated Formation.*?\n(\d{1,2}/\d{1,2}/\d{4}) (\w+) (\d+) (\d+) (\d+)',
        re.IGNORECASE
    )
    combined_match = combined_pattern.search(block_text)
    if combined_match:
        data['date_stimulated'] = combined_match.group(1)
        data['stimulated_formation'] = combined_match.group(2)
        data['top_ft'] = combined_match.group(3)
        data['bottom_ft'] = combined_match.group(4)
        data['stimulation_stages'] = combined_match.group(5)

    # Correcting type_treatment to capture correctly
    type_treatment_pattern = re.compile(
        r'Type Treatment.*?\n([A-Za-z\s]+)\s+(\d+)\s+(\d+)', re.IGNORECASE)
    treatment_details_match = type_treatment_pattern.search(block_text)
    if treatment_details_match:
        data['type_treatment'] = treatment_details_match.group(1).strip()
        data['lbs_proppant'] = treatment_details_match.group(2)
        data['max_treatment_pressure_psi'] = treatment_details_match.group(3)

    # Capturing details correctly
    details_match = re.search(r'Details.*?\n(.+)', block_text, re.IGNORECASE | re.DOTALL)
    if details_match:
        data['details'] = details_match.group(1).strip()

    return data


# Main function to process and return the first block of stimulation data
def process_stimulation_text(text):
    first_block = extract_first_stimulation_data_block(text)
    if first_block:
        stimulation_data = extract_stimulation_details(first_block)
        return stimulation_data
    return {}


def filter_and_prioritize_operator(matches):
    # Filter out undesired matches containing specific keywords or symbols
    filtered_matches = [m for m in matches if ":" not in m and "Well" not in m and "shall not commence" not in m]
    print("First Match:", filtered_matches)

    # Further filter to remove any entries with dates or additional comments
    filtered_matches = [m for m in filtered_matches if all(not c.isdigit() for c in m.split())]
    print("Second Match:", filtered_matches)

    # Prioritize based on the presence of company-related keywords and length
    company_keywords = ['inc', 'llc', 'ltd', 'company', 'corp', 'america']
    prioritized_matches = sorted(filtered_matches,
                                 key=lambda x: (any(keyword in x.lower() for keyword in company_keywords), len(x)),
                                 reverse=True)
    print("Third Match:", prioritized_matches)

    best_match = None
    for match in filtered_matches:
        if "Oasis" in match.split(" "):
            best_match = "Oasis Petroleum North America LLC"
        elif "Continental" in match.split(" "):
            best_match = "Continental Resources, Inc. "

    if best_match:
        return best_match
    else:
        if prioritized_matches:
            return prioritized_matches[0]
        else:
            return None


def filter_and_prioritize_well_names(matches):
    # Step 1: Exclude matches starting with "and" and containing certain keywords or patterns, and remove text after newlines
    filtered_matches = [
        (m[0], m[1], m[2].split('\n')[0])
        for m in matches
        if not m[2].strip().lower().startswith('and') and ":" not in m[2]
        and not any(kw.lower() in m[2].lower() for kw in ["field", "location", "legal location", "drilling contractor", "company representative", "date and time of spudding"])
    ]

    # Step 2: Further refine matches to capture well names more accurately
    refined_matches = []
    for match in filtered_matches:
        # Split by common delimiters and filter parts
        parts = re.split(r' - |, ', match[2])
        for part in parts:
            if any(char.isdigit() for char in part):  # Check if part contains a digit
                refined_matches.append(part.strip())
                break  # Assume the first matching part is the well name

    # Step 3: Prioritize matches that contain dashes, suggesting a specific identifier
    prioritized_matches = sorted(refined_matches, key=lambda x: ('-' in x, len(x)), reverse=True)

    # Step 4: Select the top match if available
    return prioritized_matches[0] if prioritized_matches else None


def filter_and_prioritize_county(matches):
    # Define the priority county name explicitly for clarity and case-insensitive comparison
    priority_county_keyword = "mckenzie"

    # Initialize variables to hold the best match and priority match
    best_match = None
    priority_match = None

    # Loop through matches to find the best and priority matches
    for match in matches:
        # Convert match to lower case for case-insensitive comparison
        match_lower = match.lower()

        # Check for the presence of the priority county keyword in the match
        if priority_county_keyword in match_lower:
            # If the priority county is found, prioritize it as the match
            priority_match = "McKenzie County"  # Use a standardized name for consistency
            break  # Since priority match is found, no need to look further

        # Secondary criteria: if the match contains "county" or any digit, consider it as a potential best match
        elif "county" in match_lower or any(char.isdigit() for char in match_lower):
            best_match = match if not best_match else best_match

    # Decide which match to return
    return priority_match if priority_match else best_match


# Function to parse and structure data extracted from PDF text.
def parse_text_for_data(text):
    data = {}
    patterns = {
        'api_number': r'API\s*(Number|NUMBER|No|num|#)[:\s\w-]*?[^\d]*(\d{2})[\s_-]*(\d{3})[\s_-]*(\d{5})',
        'well_name': r'(Well|Facility)\s*(Name|or Facility Name)\s*[:\s]*([^\n]+)',
        'operator': r'OPERATOR\s*[:\s]*([^\n]+)',
        'county': r'COUNTY(?:/STATE)?\s*[:\s]*([^\n,]+)',
        'state': r'COUNTY(?:/STATE)?\s*[:\s]*[^\n,]+,\s*([^\n]+)',
        'longitude': r"Longitude:\s*(\d+\s*°\s*\d+\s*'\s*[\d.]+\s*)\s*([EW])",
        'latitude': r"(?:Site\s+Centre\s+)?Latitude:\s*(\d+\s*°\s*\d+\s*'\s*[\d.]+\s*)\s*([NS])"

    }

    # Handle each key individually
    for key, pattern in patterns.items():
        matches = re.findall(pattern, text, re.MULTILINE | re.DOTALL | re.IGNORECASE)
        if key == 'api_number':
            # Process API number extraction
            # change it so that matches the most frequent one
            api_matches = ['-'.join(match[1:]).strip() for match in matches if all(match[1:])]
            data[key] = api_matches[-1] if api_matches else None
        elif key == 'well_name':
            # Process well name extraction with specific logic
            well_name = filter_and_prioritize_well_names(matches)
            data[key] = well_name

        elif key == 'operator':
            operator_name = filter_and_prioritize_operator(matches)
            data[key] = operator_name
        elif key == "county":
            county_name = filter_and_prioritize_county(matches)
            if data["well_name"]:
                if "Atlanta" in data["well_name"].split(" ") or "ATLANTA" in data["well_name"].split(" "):
                    county_name = "Williams & McKenzie"
            data[key] = county_name
        elif key == "state":
            if data["county"] == "McKenzie County":
                data[key] = "North Dakota"
            elif data["county"] == "Williams & McKenzie":
                data[key] = "Oklahoma"
            else:
                matches = [' '.join(match).strip() for match in matches]
                data[key] = matches[-1] if matches else None
        elif key == "longitude":
            print("First longitude matches:", matches)
            if not matches:
                long_pattern = r"(\d{1,3}°\s*\d{2}'\s*[\d.]+\s*\"?[EW])"
                matches = re.findall(long_pattern, text, re.MULTILINE | re.DOTALL | re.IGNORECASE)
                print("Second longitude matches:", matches)
            if matches:
                if isinstance(matches[0], tuple):
                    matches = [' '.join(match).strip() for match in matches]
            data[key] = matches[-1] if matches else None
        elif key == "latitude":
            print("First latitude matches:", matches)
            if not matches:
                print("No Matches Latitude")
                lat_pattern = r"(\d{1,3}°\s*\d{1,2}'\s*[\d.]+\s*\"?[NS])"
                matches = re.findall(lat_pattern, text, re.MULTILINE | re.DOTALL | re.IGNORECASE)
                print("Second latitude matches:", matches)
            if matches:
                if isinstance(matches[0], tuple):
                    matches = [' '.join(match).strip() for match in matches]
            data[key] = matches[-1] if matches else None
        else:
            # General case for other keys
            matches = [' '.join(match).strip() for match in matches]
            data[key] = matches[-1] if matches else None

    return data


# Function to establish a connection to the MySQL database.  
def create_database_connection(host_name, user_name, user_password, db_name):
    connection = None
    connection = mysql.connector.connect(
        host=host_name,
        user=user_name,
        passwd=user_password,
        database=db_name
    )
    
    return connection


# Function to create the database table if it does not already exist.
def create_table(connection):
    cursor = connection.cursor()
    create_table_query = """
    CREATE TABLE IF NOT EXISTS well_data (
        api_number VARCHAR(255) PRIMARY KEY,
        pdf_name VARCHAR(255),
        well_name VARCHAR(255),
        operator VARCHAR(255),
        longitude VARCHAR(255),
        latitude VARCHAR(255),
        county VARCHAR(255),
        state VARCHAR(255),
        date_stimulated VARCHAR(255),
        stimulated_formation VARCHAR(255),
        top_ft VARCHAR(255),
        bottom_ft VARCHAR(255),
        stimulation_stages VARCHAR(255),
        type_treatment VARCHAR(255),
        lbs_proppant VARCHAR(255),
        max_treatment_pressure_psi VARCHAR(255),
        details TEXT
    );
    """
    cursor.execute(create_table_query)
    connection.commit()
    print("Table created successfully!")


# Function to insert or update well data in the database.
def upsert_well_data(connection, data):
    cursor = connection.cursor()
    upsert_query = """
    INSERT INTO well_data (api_number, pdf_name, well_name, operator, longitude, latitude, county, state, date_stimulated, stimulated_formation, top_ft, bottom_ft, stimulation_stages, type_treatment, lbs_proppant, max_treatment_pressure_psi, details)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
    pdf_name = VALUES(pdf_name),
    well_name = VALUES(well_name),
    operator = VALUES(operator),
    longitude = VALUES(longitude),
    latitude = VALUES(latitude),
    county = VALUES(county),
    state = VALUES(state),
    date_stimulated = VALUES(date_stimulated),
    stimulated_formation = VALUES(stimulated_formation),
    top_ft = VALUES(top_ft),
    bottom_ft = VALUES(bottom_ft),
    stimulation_stages = VALUES(stimulation_stages),
    type_treatment = VALUES(type_treatment),
    lbs_proppant = VALUES(lbs_proppant),
    max_treatment_pressure_psi = VALUES(max_treatment_pressure_psi),
    details = VALUES(details);
    """
    # Added lbs_proppant to the fields list to match the placeholders
    values = (data.get('api_number'), data.get('pdf_name'), data.get('well_name'), data.get('operator'), data.get('longitude'), data.get('latitude'), data.get('county'), data.get('state'), data.get('date_stimulated'), data.get('stimulated_formation'), data.get('top_ft'), data.get('bottom_ft'), data.get('stimulation_stages'), data.get('type_treatment'), data.get('lbs_proppant'), data.get('max_treatment_pressure_psi'), data.get('details'))
    cursor.execute(upsert_query, values)
    connection.commit()
    print("Well data inserted/updated successfully")


# Function to ensure data fields do not exceed defined maximum lengths.
def validate_and_trim_data(data):
    # Define the maximum lengths
    max_lengths = {
        'api_number': 255,
        'pdf_name': 255,
        'well_name': 255,
        'operator': 255,
        'longitude': 255,
        'latitude': 255,
        'county': 255,
        'state': 255,
        'date_stimulated': 50,
        'type_treatment': 255,
        'stimulated_formation': 255,
        'top_ft': 255,
        'bottom_ft': 255,
        'stimulation_stages': 255,
        'max_treatment_pressure_psi': 255,
        'details': 500
    }
    
    # Trim data to fit the schema
    for field, max_length in max_lengths.items():
        if field in data and data[field] is not None:
            data[field] = data[field][:max_length]

    return data


# testing
def test(db_conn):
    directory_path = 'DSCI560_Lab5'
    full_path = os.path.join(directory_path, "W28633.pdf")
    pdf_text = extract_text_from_pdf(full_path)
    # Use the extracted text to find data
    print(pdf_text)
    data = parse_text_for_data(pdf_text)
    data['pdf_name'] = "W28633.pdf"
    data_stimulation = process_stimulation_text(pdf_text)
    data.update(data_stimulation)

    for k, v in data.items():
       print(f"{k}:{v}")

    # Trim data to fit database schema
    data = validate_and_trim_data(data)

    # insert to database
    upsert_well_data(db_conn, data)


# Main script execution: processing PDFs in a directory, extracting data, and inserting/updating in the database.
directory_path = 'DSCI560_Lab5'
force_number = 0
db_conn = create_database_connection('localhost', 'root', 'Aven890831@@', 'DSCI560')
# db_conn_test = create_database_connection('localhost', 'root', 'Aven890831@@', 'lab5_test')
create_table(db_conn)
# create_table(db_conn_test)
#
# test(db_conn_test)

for pdf in sorted(os.listdir(directory_path)):
    full_path = os.path.join(directory_path, pdf)
    pdf_text = extract_text_from_pdf(full_path)

    if not pdf_text or check_pdf_needs_ocr_for_api_number(pdf_text):
        print("API number was initially not found: perform OCR.")
        # Perform OCR
        apply_ocr_to_pdf(full_path)
        # Extract text again from the OCR-processed PDF
        pdf_text = extract_text_from_pdf('output.pdf')

    # Use the extracted text to find data
    data = parse_text_for_data(pdf_text)
    data['pdf_name'] = str(pdf)
    data_stimulation = process_stimulation_text(pdf_text)
    data.update(data_stimulation)

    for k, v in data.items():
        print(f"{k}:{v}")

    if not data["api_number"]:
        print("No api number")
        force_number += 1
        data["api_number"] = str(force_number)

    # Trim data to fit database schema
    data = validate_and_trim_data(data)

    # insert to database
    upsert_well_data(db_conn, data)


# close connection
db_conn.close()
# db_conn_test.close()














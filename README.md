
# PDF Extraction, Data Parsing, and Well Data Management

This project is designed to extract data from PDF files, process the extracted text, and insert or update parsed data into a MySQL database. The system is capable of handling non-OCR PDFs and applying OCR if needed. It extracts important well-related information, including API numbers, well names, operators, location details, and stimulation data.

## Features

1. **PDF Text Extraction**: Extracts text from PDFs using `PyPDF2`. If text extraction fails to locate key data (such as API numbers), it applies OCR using the `ocrmypdf` tool.
  
2. **Stimulation Data Extraction**: Captures stimulation data from extracted text, including fields such as `Date Stimulated`, `Stimulated Formation`, and `Type Treatment`.

3. **Operator, Well Name, and County Identification**: Uses pattern matching to accurately extract operator names, well names, and counties, with prioritization based on common keywords.

4. **MySQL Database Integration**: The parsed data is inserted or updated into a MySQL database with well data. The database table `well_data` includes columns for:
    - API Number
    - Well Name
    - Operator
    - Location (Longitude, Latitude, County, State)
    - Stimulation Data (Date, Formation, Top/Bottom Depth, Stages, Treatment Type, Proppant Amount, etc.)
    - PDF Filename
    - Details

## Setup and Requirements

### Dependencies

- Python 3.x
- MySQL Server
- Libraries: `PyPDF2`, `re`, `mysql.connector`, `ocrmypdf`

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/well-data-management.git
   cd well-data-management
   ```

2. Install required Python libraries:
   ```bash
   pip install PyPDF2 mysql-connector-python ocrmypdf
   ```

3. Setup MySQL database:
   - Create a MySQL database named `DSCI560`.
   - Ensure you have MySQL running and accessible.

4. Update the database connection settings in the script:
   ```python
   db_conn = create_database_connection('localhost', 'root', 'your_password', 'DSCI560')
   ```

### Running the Script

1. Place the PDFs you want to process in a directory (e.g., `DSCI560_Lab5`).

2. Run the script:
   ```bash
   python process_pdfs.py
   ```

   The script will:
   - Extract text from each PDF file.
   - Apply OCR if the initial text extraction misses important data (like API numbers).
   - Parse the extracted data for well-related information.
   - Insert or update the parsed data into the MySQL database.

### Database Table Structure

The `well_data` table contains the following fields:

| Field                        | Data Type    | Description                                |
|------------------------------|--------------|--------------------------------------------|
| `api_number`                 | VARCHAR(255) | Unique API number for the well             |
| `pdf_name`                   | VARCHAR(255) | Name of the PDF file                       |
| `well_name`                  | VARCHAR(255) | Name of the well                           |
| `operator`                   | VARCHAR(255) | Name of the operator company               |
| `longitude`                  | VARCHAR(255) | Longitude of the well location             |
| `latitude`                   | VARCHAR(255) | Latitude of the well location              |
| `county`                     | VARCHAR(255) | County where the well is located           |
| `state`                      | VARCHAR(255) | State where the well is located            |
| `date_stimulated`            | VARCHAR(255) | Date when the well was stimulated          |
| `stimulated_formation`       | VARCHAR(255) | Formation name where stimulation occurred  |
| `top_ft`                     | VARCHAR(255) | Top depth of stimulation                   |
| `bottom_ft`                  | VARCHAR(255) | Bottom depth of stimulation                |
| `stimulation_stages`         | VARCHAR(255) | Number of stimulation stages               |
| `type_treatment`             | VARCHAR(255) | Type of stimulation treatment              |
| `lbs_proppant`               | VARCHAR(255) | Amount of proppant used (in lbs)           |
| `max_treatment_pressure_psi` | VARCHAR(255) | Maximum treatment pressure (in PSI)        |
| `details`                    | TEXT         | Additional details related to the stimulation |

### Example Workflow

1. Place your PDF files in the `DSCI560_Lab5` directory.
2. The script processes each file, applying OCR when necessary, and parses data such as API numbers, well names, operator names, and stimulation details.
3. The parsed data is then inserted into the MySQL database, where it is either added as a new entry or updates existing entries based on the API number.

## Future Improvements
- Add more sophisticated OCR handling for more complex documents.
- Enhance the parsing logic to cover more edge cases.
- Add error logging for skipped or problematic PDF files.

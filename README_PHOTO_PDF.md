# Photo Location PDF Generator

A Python script for Mac that processes photos with GPS EXIF data and creates a beautiful PDF document with images grouped by location.

## Features

- Extracts GPS coordinates from photo EXIF data
- Automatically groups photos by geographic location
- Sorts photos by date within each location
- Generates a professional PDF document
- Supports both single files and entire directories
- Adjustable location clustering sensitivity

## Requirements

- Python 3.7 or higher
- macOS (tested on Mac, should work on other platforms too)

## Installation

1. Install dependencies:

```bash
pip install -r requirements.txt
```

Or install manually:

```bash
pip install Pillow reportlab
```

## Usage

### Basic Usage

Process a directory of photos:

```bash
python photo_location_pdf.py /path/to/photos output.pdf
```

Process a single photo:

```bash
python photo_location_pdf.py /path/to/photo.jpg output.pdf
```

### Advanced Options

Adjust location clustering threshold (in degrees, ~0.01° ≈ 1km):

```bash
python photo_location_pdf.py /path/to/photos output.pdf --threshold 0.05
```

Smaller threshold = more location groups
Larger threshold = fewer location groups

### Examples

```bash
# Process vacation photos
python photo_location_pdf.py ~/Pictures/Vacation2024 vacation_album.pdf

# Process with wider location grouping
python photo_location_pdf.py ~/Pictures/Trip trip_album.pdf --threshold 0.1

# Process single photo
python photo_location_pdf.py ~/Pictures/photo.jpg single_photo.pdf
```

## How It Works

1. **Scans** the input directory for JPEG and PNG images
2. **Extracts** GPS coordinates from EXIF data
3. **Clusters** photos by proximity to create location groups
4. **Sorts** photos within each group by date taken
5. **Generates** a PDF with locations as sections

## Output

The generated PDF includes:

- Title page with generation date
- Photos grouped by location
- Location coordinates for each group
- Photo filenames and timestamps
- Professional layout with proper spacing

## Notes

- Only photos with GPS EXIF data will be included
- Photos without GPS data are skipped with a notification
- Supported formats: JPEG, JPG, PNG
- Images are automatically resized to fit the page
- The script preserves image aspect ratios

## Troubleshooting

**"No GPS data found"**
- Ensure your photos contain GPS EXIF data
- Check that location services were enabled when photos were taken
- Some photo editing software removes EXIF data

**"Permission denied"**
- Make sure you have read access to the input directory
- Ensure you have write access to the output location

**"Module not found"**
- Run `pip install -r requirements.txt` to install dependencies

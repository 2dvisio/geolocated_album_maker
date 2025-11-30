#!/usr/bin/env python3

import os
import sys
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from collections import defaultdict
from datetime import datetime
import argparse


def get_exif_data(image_path):
    try:
        image = Image.open(image_path)
        exif_data = image._getexif()
        if not exif_data:
            return None

        exif = {}
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            exif[tag] = value

        return exif
    except Exception as e:
        print(f"Error reading EXIF from {image_path}: {e}")
        return None


def get_gps_info(exif_data):
    if not exif_data or 'GPSInfo' not in exif_data:
        return None

    gps_info = {}
    for key in exif_data['GPSInfo'].keys():
        decode = GPSTAGS.get(key, key)
        gps_info[decode] = exif_data['GPSInfo'][key]

    return gps_info


def convert_to_degrees(value):
    d, m, s = value
    return d + (m / 60.0) + (s / 3600.0)


def get_coordinates(gps_info):
    if not gps_info:
        return None

    try:
        lat = convert_to_degrees(gps_info['GPSLatitude'])
        if gps_info['GPSLatitudeRef'] == 'S':
            lat = -lat

        lon = convert_to_degrees(gps_info['GPSLongitude'])
        if gps_info['GPSLongitudeRef'] == 'W':
            lon = -lon

        return (lat, lon)
    except Exception as e:
        print(f"Error converting coordinates: {e}")
        return None


def get_location_name(lat, lon):
    return f"{abs(lat):.4f}°{'N' if lat >= 0 else 'S'}, {abs(lon):.4f}°{'E' if lon >= 0 else 'W'}"


def cluster_locations(photos, threshold=0.01):
    clusters = []

    for photo in photos:
        lat, lon = photo['coordinates']
        found_cluster = False

        for cluster in clusters:
            cluster_lat, cluster_lon = cluster['center']
            if abs(lat - cluster_lat) < threshold and abs(lon - cluster_lon) < threshold:
                cluster['photos'].append(photo)
                avg_lat = sum(p['coordinates'][0] for p in cluster['photos']) / len(cluster['photos'])
                avg_lon = sum(p['coordinates'][1] for p in cluster['photos']) / len(cluster['photos'])
                cluster['center'] = (avg_lat, avg_lon)
                found_cluster = True
                break

        if not found_cluster:
            clusters.append({
                'center': (lat, lon),
                'photos': [photo]
            })

    return clusters


def get_image_date(exif_data):
    if not exif_data:
        return None

    for tag in ['DateTimeOriginal', 'DateTime', 'DateTimeDigitized']:
        if tag in exif_data:
            try:
                return datetime.strptime(exif_data[tag], '%Y:%m:%d %H:%M:%S')
            except:
                pass
    return None


def create_pdf(clusters, output_path):
    doc = SimpleDocTemplate(output_path, pagesize=letter,
                          topMargin=0.5*inch, bottomMargin=0.5*inch,
                          leftMargin=0.5*inch, rightMargin=0.5*inch)

    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor='#2c3e50',
        spaceAfter=30,
        alignment=TA_CENTER
    )

    location_style = ParagraphStyle(
        'LocationTitle',
        parent=styles['Heading2'],
        fontSize=16,
        textColor='#34495e',
        spaceAfter=12,
        spaceBefore=20
    )

    caption_style = ParagraphStyle(
        'Caption',
        parent=styles['Normal'],
        fontSize=9,
        textColor='#7f8c8d',
        alignment=TA_CENTER,
        spaceAfter=20
    )

    story.append(Paragraph("Photo Album by Location", title_style))
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))

    for i, cluster in enumerate(clusters, 1):
        lat, lon = cluster['center']
        location_name = get_location_name(lat, lon)

        story.append(Paragraph(f"Location {i}: {location_name}", location_style))
        story.append(Paragraph(f"{len(cluster['photos'])} photo(s)", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))

        for photo in cluster['photos']:
            try:
                img = RLImage(photo['path'])

                available_width = 7 * inch
                available_height = 5 * inch

                aspect = img.imageWidth / img.imageHeight

                if aspect > available_width / available_height:
                    img_width = available_width
                    img_height = img_width / aspect
                else:
                    img_height = available_height
                    img_width = img_height * aspect

                img.drawWidth = img_width
                img.drawHeight = img_height

                story.append(img)

                caption_text = Path(photo['path']).name
                if photo['date']:
                    caption_text += f" - {photo['date'].strftime('%B %d, %Y %I:%M %p')}"

                story.append(Paragraph(caption_text, caption_style))
                story.append(Spacer(1, 0.2*inch))

            except Exception as e:
                print(f"Error adding image {photo['path']}: {e}")

        if i < len(clusters):
            story.append(PageBreak())

    doc.build(story)
    print(f"\nPDF created successfully: {output_path}")


def process_images(input_path, output_path, threshold):
    photos = []

    input_path = Path(input_path)

    if input_path.is_file():
        image_files = [input_path]
    elif input_path.is_dir():
        image_files = []
        for ext in ['*.jpg', '*.jpeg', '*.JPG', '*.JPEG', '*.png', '*.PNG']:
            image_files.extend(input_path.glob(ext))
    else:
        print(f"Error: {input_path} is not a valid file or directory")
        return

    print(f"Found {len(image_files)} image(s) to process...")

    for image_path in image_files:
        exif_data = get_exif_data(str(image_path))
        gps_info = get_gps_info(exif_data)
        coordinates = get_coordinates(gps_info)

        if coordinates:
            photos.append({
                'path': str(image_path),
                'coordinates': coordinates,
                'date': get_image_date(exif_data)
            })
            print(f"✓ {image_path.name} - GPS: {get_location_name(*coordinates)}")
        else:
            print(f"✗ {image_path.name} - No GPS data found")

    if not photos:
        print("\nNo photos with GPS data found!")
        return

    print(f"\nProcessing {len(photos)} photo(s) with GPS data...")

    clusters = cluster_locations(photos, threshold)

    clusters.sort(key=lambda c: len(c['photos']), reverse=True)

    for cluster in clusters:
        cluster['photos'].sort(key=lambda p: p['date'] if p['date'] else datetime.min)

    print(f"Grouped into {len(clusters)} location(s)")

    create_pdf(clusters, output_path)


def main():
    parser = argparse.ArgumentParser(
        description='Create a PDF document from photos grouped by GPS location',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python photo_location_pdf.py /path/to/photos output.pdf
  python photo_location_pdf.py /path/to/photos output.pdf --threshold 0.05
  python photo_location_pdf.py single_photo.jpg output.pdf
        """
    )

    parser.add_argument('input', help='Path to image file or directory containing images')
    parser.add_argument('output', help='Output PDF file path')
    parser.add_argument('--threshold', type=float, default=0.01,
                       help='Location clustering threshold in degrees (default: 0.01, ~1km)')

    args = parser.parse_args()

    if not args.output.lower().endswith('.pdf'):
        args.output += '.pdf'

    process_images(args.input, args.output, args.threshold)


if __name__ == '__main__':
    main()
